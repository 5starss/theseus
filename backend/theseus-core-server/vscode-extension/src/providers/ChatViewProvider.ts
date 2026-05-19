import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';
import * as https from 'https';

import { resolveReadableUri, saveAssetToWorkspace } from '../assets/AssetStore';
import { TheseusSessionManager } from '../session/SessionManager';
import {
  asHostToWebviewMessage,
  asWebviewToHostMessage,
  type HostToWebviewMessage,
  type JsonObject,
  type RunnerEvent,
} from '../shared/protocol';
import {
  disableCustomTool,
  installCustomToolDependencies,
  loadCustomToolSummaries,
  registerCustomTool,
  updateCustomToolPermission,
} from '../tools/CustomToolManager';
import {
  expandTheseusPath,
  findMentionFiles,
  getActiveCursorContext,
  getCoreRoot,
  getCustomToolSearchRoots,
  getPythonPath,
  getRunnerPath,
  getRuntimeModeSetting,
  getWorkspaceCwd,
  injectCursorContext,
  resolveContextMentions,
} from '../workspace/WorkspaceContext';
import { getChangedFile, TheseusDiffContentProvider } from './DiffProvider';
import { renderChatViewHtml } from './ChatViewHtml';
import { SessionController } from './controllers/SessionController';

async function openChangedFileDiff(
  diffProvider: TheseusDiffContentProvider,
  event: RunnerEvent,
): Promise<void> {
  if (event.type !== 'ToolExecutionCompleted' || event.is_error) return;
  const changed = getChangedFile(event);
  if (!changed?.path || typeof changed.old_content !== 'string') return;

  const label = changed.relative_path || changed.path;
  const oldUri = diffProvider.createUri(label, changed.old_content);
  const newUri = vscode.Uri.file(changed.path);
  await vscode.commands.executeCommand(
    'vscode.diff',
    oldUri,
    newUri,
    `Theseus Diff: ${label}`,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function planLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function scalarText(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2);
}

function toolEventKey(event: RunnerEvent): string {
  const id = typeof event.tool_use_id === 'string' ? event.tool_use_id : '';
  const name = typeof event.tool_name === 'string' ? event.tool_name : 'tool';
  return id || name;
}

function requestWithTimeout(url: URL, timeoutMs: number): Promise<{ statusCode: number; statusMessage: string }> {
  return new Promise((resolve, reject) => {
    const client = url.protocol === 'https:' ? https : http;
    const request = client.request(url, { method: 'GET', timeout: timeoutMs }, response => {
      response.resume();
      response.on('end', () => resolve({
        statusCode: response.statusCode || 0,
        statusMessage: response.statusMessage || '',
      }));
    });
    request.on('timeout', () => {
      request.destroy(new Error(`timeout after ${timeoutMs}ms`));
    });
    request.on('error', reject);
    request.end();
  });
}

async function probeExternalServer(serverUrl: string): Promise<JsonObject> {
  const raw = String(serverUrl || '').trim();
  if (!raw) {
    return { status: 'standalone', url: '', detail: 'Standalone mode; no external Theseus server URL configured.' };
  }
  let healthUrl: URL;
  try {
    const base = new URL(raw.endsWith('/') ? raw : `${raw}/`);
    healthUrl = new URL('health', base);
  } catch (err) {
    return { status: 'unreachable', url: raw, detail: `Invalid serverUrl: ${err instanceof Error ? err.message : String(err)}` };
  }
  try {
    const response = await requestWithTimeout(healthUrl, 1500);
    const ok = response.statusCode >= 200 && response.statusCode < 500;
    return {
      status: ok ? 'connected' : 'unreachable',
      url: raw,
      healthUrl: healthUrl.toString(),
      detail: `GET /health -> ${response.statusCode}${response.statusMessage ? ` ${response.statusMessage}` : ''}`,
    };
  } catch (err) {
    return {
      status: 'unreachable',
      url: raw,
      healthUrl: healthUrl.toString(),
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

function isInsidePath(child: string, parent: string): boolean {
  const resolvedChild = path.resolve(child);
  const resolvedParent = path.resolve(parent);
  const relative = path.relative(resolvedParent, resolvedChild);
  return relative === '' || (!!relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}

function withoutUiState(plan: JsonObject): JsonObject {
  const copy: JsonObject = {};
  for (const [key, value] of Object.entries(plan)) {
    if (key === 'reviewState') continue;
    copy[key] = value;
  }
  return copy;
}

function appendMarkdownValue(lines: string[], key: string, value: unknown, level: number): void {
  if (value === undefined || key === 'reviewState') return;
  const heading = '#'.repeat(Math.min(level, 6));
  const label = planLabel(key);

  if (Array.isArray(value)) {
    if (!value.length) return;
    lines.push(`${heading} ${label}`, '');
    for (const [index, item] of value.entries()) {
      if (isRecord(item)) {
        const title = scalarText(item.title || item.name || item.description || item.id || `Item ${index + 1}`);
        lines.push(`${'#'.repeat(Math.min(level + 1, 6))} ${title}`, '');
        for (const [childKey, childValue] of Object.entries(item)) {
          if (['title', 'name'].includes(childKey)) continue;
          appendMarkdownValue(lines, childKey, childValue, level + 2);
        }
      } else {
        lines.push(`- ${scalarText(item)}`);
      }
    }
    lines.push('');
    return;
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([childKey, childValue]) => childKey !== 'reviewState' && childValue !== undefined);
    if (!entries.length) return;
    lines.push(`${heading} ${label}`, '');
    for (const [childKey, childValue] of entries) {
      appendMarkdownValue(lines, childKey, childValue, level + 1);
    }
    return;
  }

  const rendered = scalarText(value).trim();
  if (!rendered) return;
  if (rendered.includes('\n')) {
    lines.push(`${heading} ${label}`, '', rendered, '');
  } else {
    lines.push(`- **${label}**: ${rendered}`);
  }
}

function planTaskTitle(task: Record<string, unknown>, index: number): string {
  const id = task.id ? `[${scalarText(task.id)}] ` : '';
  return `${id}${scalarText(task.title || task.description || `Task ${index + 1}`)}`;
}

function formatPlanMarkdown(plan: JsonObject): string {
  const sanitized = withoutUiState(plan);
  const lines = [
    '# Theseus Plan',
    '',
    `Generated: ${new Date().toLocaleString()}`,
    '',
  ];

  const tasks = Array.isArray(sanitized.tasks) ? sanitized.tasks : [];
  if (tasks.length) {
    lines.push('## Tasks', '');
    for (const [index, task] of tasks.entries()) {
      if (!isRecord(task)) {
        lines.push(`${index + 1}. ${scalarText(task)}`);
        continue;
      }
      lines.push(`${index + 1}. ${planTaskTitle(task, index)}`);
      for (const [key, value] of Object.entries(task)) {
        if (['id', 'title', 'description'].includes(key) || value === undefined) continue;
        lines.push(`   - **${planLabel(key)}**: ${scalarText(value)}`);
      }
    }
    lines.push('');
  }

  for (const [key, value] of Object.entries(sanitized)) {
    if (key === 'tasks') continue;
    appendMarkdownValue(lines, key, value, 2);
  }

  lines.push('## Full Plan JSON', '', '```json', JSON.stringify(sanitized, null, 2), '```', '');
  return lines.join('\n');
}

/**
 * 워크트리(작업 폴더) 선택 picker — VSCode 작업 폴더 목록 + Browse + Clear.
 * 선택 결과는 `theseus.workspacePath` workspace 설정에 저장된다.
 *
 * @param sessionManager 변경 후 runner가 실행 중이면 재시작 안내/자동 재시작을 위해 전달.
 *                       전달하지 않으면 안내만 표시하지 않음.
 */
export async function pickWorktree(sessionManager?: TheseusSessionManager): Promise<string | undefined> {
  const cfg = vscode.workspace.getConfiguration('theseus');
  const current = expandTheseusPath(cfg.get<string>('workspacePath')) || '';
  const folders = vscode.workspace.workspaceFolders ?? [];

  type Item = vscode.QuickPickItem & { value?: string; action?: 'browse' | 'clear' };
  const items: Item[] = [];

  for (const folder of folders) {
    const fsPath = folder.uri.fsPath;
    items.push({
      label: `$(folder) ${folder.name}`,
      description: fsPath === current ? '(current)' : undefined,
      detail: fsPath,
      value: fsPath,
    });
  }

  if (current && !folders.some(f => f.uri.fsPath === current)) {
    items.push({
      label: `$(folder-active) Custom path`,
      description: '(current, not in VSCode folders)',
      detail: current,
      value: current,
    });
  }

  items.push({ label: '$(folder-opened) Browse...', detail: 'OS 파일 선택 대화상자로 폴더 선택', action: 'browse' });
  if (current) {
    items.push({ label: '$(clear-all) Clear', detail: '설정을 비우고 첫 번째 VSCode 작업 폴더로 자동 사용', action: 'clear' });
  }

  const picked = await vscode.window.showQuickPick(items, {
    title: 'Theseus 워크트리 선택',
    placeHolder: current || '작업 폴더를 선택하세요',
    matchOnDescription: true,
    matchOnDetail: true,
  });
  if (!picked) return undefined;

  let nextValue: string | undefined;

  if (picked.action === 'browse') {
    const uri = await vscode.window.showOpenDialog({
      canSelectFiles: false,
      canSelectFolders: true,
      canSelectMany: false,
      openLabel: 'Use as Workspace',
    });
    if (!uri?.length) return undefined;
    nextValue = uri[0].fsPath;
  } else if (picked.action === 'clear') {
    nextValue = '';
  } else if (typeof picked.value === 'string') {
    nextValue = picked.value;
  } else {
    return undefined;
  }

  // 이전 워크트리 (변경 여부 판단용)
  const previousResolved = current || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';

  // workspace 범위가 있으면 workspace 단위로, 없으면 user 범위로 저장
  const target = vscode.workspace.workspaceFolders?.length
    ? vscode.ConfigurationTarget.Workspace
    : vscode.ConfigurationTarget.Global;
  await cfg.update('workspacePath', nextValue || '', target);

  const resolved = nextValue || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
  const changed = resolved !== previousResolved;

  // runner가 옛 경로로 동작 중이면 재시작 권유
  if (changed && sessionManager?.hasProcess) {
    const action = await vscode.window.showWarningMessage(
      resolved
        ? `Theseus 워크트리가 ${resolved}로 변경되었습니다. 실행 중인 runner는 옛 경로를 사용 중입니다.`
        : 'Theseus 워크트리 설정이 비워졌습니다. 실행 중인 runner는 옛 경로를 사용 중입니다.',
      { modal: false },
      'Restart Runner',
      'Later',
    );
    if (action === 'Restart Runner') {
      sessionManager.stop('worktree_changed');
      // start는 호출 측 또는 사용자에 위임 (자동 재시작은 컨텍스트 의존성 큼)
      vscode.window.showInformationMessage('Runner를 재시작하려면 Start 버튼을 눌러주세요.');
    }
  } else if (changed) {
    if (resolved) {
      vscode.window.showInformationMessage(`Theseus 워크트리가 ${resolved}로 설정되었습니다.`);
    } else {
      vscode.window.showInformationMessage('Theseus 워크트리 설정이 비워졌습니다.');
    }
  }
  return resolved;
}

async function openPlanMarkdownPreview(plan: JsonObject): Promise<void> {
  const doc = await vscode.workspace.openTextDocument({
    content: formatPlanMarkdown(plan),
    language: 'markdown',
  });
  await vscode.window.showTextDocument(doc, {
    preview: true,
    viewColumn: vscode.ViewColumn.Beside,
  });
}

class WebviewMessageQueue {
  private queue: HostToWebviewMessage[] = [];
  private flushing = false;

  constructor(private readonly getWebview: () => vscode.Webview | undefined) {}

  post(message: HostToWebviewMessage): void {
    const normalized = asHostToWebviewMessage(message);
    if (!normalized) return;
    this.queue.push(normalized);
    void this.flush();
  }

  private async flush(): Promise<void> {
    if (this.flushing) return;
    this.flushing = true;
    try {
      while (this.queue.length) {
        const webview = this.getWebview();
        if (!webview) {
          this.queue = this.queue.slice(-20);
          return;
        }
        const message = this.queue.shift();
        if (message) await webview.postMessage(message);
      }
    } finally {
      this.flushing = false;
    }
  }
}

import { ComposerPanel, type ComposerChangeItem } from '../composer/ComposerPanel';

export class TheseusChatViewProvider implements vscode.WebviewViewProvider {
  static readonly viewType = 'theseus.chatView';
  private view: vscode.WebviewView | undefined;
  private readonly messageQueue = new WebviewMessageQueue(() => this.view?.webview);
  private readonly sessionController: SessionController;
  private activeChanges: ComposerChangeItem[] = [];
  private readonly toolStarts = new Map<string, number>();
  private latestCustomToolInventory: unknown[] = [];
  private latestCustomToolSource = '';
  private runtimeRefreshTimer: NodeJS.Timeout | undefined;
  private runtimeRefreshReason = '';
  private hostRefreshTimer: NodeJS.Timeout | undefined;
  private hostRefreshReason = '';

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly sessionManager: TheseusSessionManager,
    private readonly diffProvider: TheseusDiffContentProvider,
    private readonly onStartRunner: () => void,
  ) {
    this.sessionController = new SessionController(
      this.sessionManager,
      event => this.postRunnerEvent(event),
    );
    this.sessionManager.onEvent((event) => {
      if (event.type === 'customToolInventoryUpdated' && Array.isArray(event.tools)) {
        this.latestCustomToolInventory = event.tools;
        this.latestCustomToolSource = typeof event.source === 'string' ? event.source : 'runner';
      }
      this.postRunnerEvent(event);
      if (event.type === 'RunnerReady') {
        this.refreshRuntimeToolRegistry('runner_ready');
      }
      if (event.type === 'RunnerDiagnostic') {
        this.messageQueue.post({ type: 'diagnostic', diagnostic: event });
      }

      if (event.type === 'ToolExecutionStarted') {
        this.toolStarts.set(toolEventKey(event), Date.now());
      }

      const changed = getChangedFile(event);
      if (changed && event.type === 'ToolExecutionCompleted') {
        const now = Date.now();
        const startedAt = this.toolStarts.get(toolEventKey(event)) || now;
        this.toolStarts.delete(toolEventKey(event));
        const isFailed = event.is_error === true;
        const item: ComposerChangeItem = {
          id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
          path: changed.path,
          relativePath: changed.relative_path,
          status: isFailed ? 'failed' : 'success',
          success: !isFailed,
          createdAt: startedAt,
          updatedAt: now,
          completedAt: isFailed ? undefined : now,
          failedAt: isFailed ? now : undefined,
          durationMs: Math.max(0, now - startedAt),
          errorMessage: isFailed ? String(event.output || event.message || 'Tool execution failed.') : undefined,
          toolName: typeof event.tool_name === 'string' ? event.tool_name : 'tool',
          event,
        };
        this.activeChanges = [item, ...this.activeChanges].slice(0, 50);
        ComposerPanel.createOrShow(this.context.extensionUri);
        ComposerPanel.updateChanges(this.activeChanges);
      }

      void openChangedFileDiff(this.diffProvider, event);
    });
  }

  postToWebview(event: RunnerEvent): void {
    this.postRunnerEvent(event);
  }

  postSessionState(): void {
    this.sessionManager.reattachIfPossible('post_session_state');
    this.postRunnerEvent(this.sessionManager.status);
    this.messageQueue.post({ type: 'historySnapshot', history: this.sessionManager.historySnapshot });
    if (this.sessionManager.hasProcess) {
      this.refreshRuntimeToolRegistry('webview_attach');
    } else {
      this.refreshCustomToolsOnce('webview_attach');
    }
  }

  private postRunnerEvent(event: RunnerEvent): void {
    this.messageQueue.post({ type: 'runnerEvent', event });
  }

  refreshActiveCursor(): void {
    const cursor = getActiveCursorContext();
    this.messageQueue.post({
      type: 'runnerEvent',
      event: {
        type: 'activeFileChanged',
        file: cursor?.file || '',
        line: cursor?.line,
      },
    });
  }

  async refreshCustomTools(): Promise<void> {
    const tools = await loadCustomToolSummaries();
    this.latestCustomToolInventory = tools;
    this.latestCustomToolSource = 'host';
    this.messageQueue.post({
      type: 'runnerEvent',
      event: { type: 'customToolsLoaded', source: 'host', tools },
    });
  }

  queueCustomToolRefresh(reason = 'watcher'): void {
    if (this.sessionManager.hasProcess) {
      this.refreshRuntimeToolRegistry(reason);
    } else {
      this.refreshCustomToolsOnce(reason);
    }
  }

  private refreshCustomToolsOnce(reason: string, debounceMs = 650): void {
    this.hostRefreshReason = reason;
    if (this.hostRefreshTimer) clearTimeout(this.hostRefreshTimer);
    this.hostRefreshTimer = setTimeout(() => {
      this.hostRefreshTimer = undefined;
      const scheduledReason = this.hostRefreshReason;
      void this.refreshCustomTools().catch(err => {
        this.postRunnerEvent({
          type: 'customToolValidation',
          success: false,
          message: `Custom tool inventory refresh failed (${scheduledReason}): ${err instanceof Error ? err.message : String(err)}`,
        });
      });
    }, debounceMs);
  }

  private refreshRuntimeToolRegistry(reason: string, debounceMs = 650): void {
    if (!this.sessionManager.hasProcess) {
      this.refreshCustomToolsOnce(reason, debounceMs);
      return;
    }
    this.runtimeRefreshReason = reason;
    if (this.runtimeRefreshTimer) clearTimeout(this.runtimeRefreshTimer);
    this.runtimeRefreshTimer = setTimeout(() => {
      this.runtimeRefreshTimer = undefined;
      this.sessionManager.refreshToolRegistry(this.runtimeRefreshReason);
    }, debounceMs);
  }

  private async postHealthStatus(): Promise<void> {
    const coreRoot = getCoreRoot(this.context) || '';
    const workspaceCwd = getWorkspaceCwd() || '';
    const config = vscode.workspace.getConfiguration('theseus');
    const pythonExec = getPythonPath();
    const runnerPath = getRunnerPath();
    const runtimeModeSetting = getRuntimeModeSetting();
    const usingBundledRunner = !!runnerPath && runtimeModeSetting !== 'source-python';
    const serverUrl = config.get<string>('serverUrl') || '';
    const status = this.sessionManager.status;
    const customToolRoots = getCustomToolSearchRoots();
    const server = await probeExternalServer(serverUrl);
    const serverRuntimeNote = status.processRunning && serverUrl
      ? 'serverUrl changes apply to the active daemon after runner restart.'
      : '';
    const serverForHealth: JsonObject = {
      ...server,
      runtimeNote: serverRuntimeNote,
      detail: [server.detail, serverRuntimeNote].filter(Boolean).join(' · '),
    };
    const serverHealthStatus = String(serverForHealth.status || server.status || 'standalone');
    const toolInventory = Array.isArray(this.latestCustomToolInventory) ? this.latestCustomToolInventory : [];
    const availableCount = toolInventory.filter(item => isRecord(item) && item.loadState === 'available').length;
    const unavailableCount = toolInventory.filter(item => isRecord(item) && item.loadState === 'unavailable').length;
    const inactiveCount = toolInventory.filter(item => isRecord(item) && item.loadState === 'inactive').length;
    const daemonStatus = status.processRunning
      ? status.lifecycle === 'busy'
        ? 'Running'
        : status.lifecycle === 'starting' || status.lifecycle === 'starting_stale'
          ? 'Starting'
          : 'Ready'
      : 'Stopped';
    this.postRunnerEvent({
      type: 'healthStatus',
      settings: {
        corePath: coreRoot,
        pythonPath: pythonExec,
        runnerPath,
        runtimeModeSetting,
        serverUrl,
        workspacePath: workspaceCwd,
        coreRoot,
        workspaceCwd,
        pythonExec,
        customToolRoots,
      },
      localDaemon: {
        status: daemonStatus,
        pid: status.daemonPid,
        port: status.daemonPort,
        workspace: status.workspaceCwd || workspaceCwd,
        session: status.session,
        startedAt: status.daemonStartedAt,
        runtimeMode: status.runtimeMode,
      },
      server: serverForHealth,
      customTools: {
        source: this.latestCustomToolSource || (status.processRunning ? 'runner' : 'host'),
        availableCount,
        unavailableCount,
        inactiveCount,
        totalCount: toolInventory.length,
      },
      runner: {
        running: status.running,
        processRunning: status.processRunning,
        lifecycle: status.lifecycle,
        runtimeMode: status.runtimeMode,
        daemonPid: status.daemonPid,
        daemonPort: status.daemonPort,
        sessionId: status.sessionId,
        lastDiagnostic: status.lastDiagnostic,
      },
      checks: [
        {
          label: 'Core path',
          status: coreRoot ? 'ok' : usingBundledRunner ? 'warn' : 'error',
          detail: coreRoot || (usingBundledRunner ? 'bundled runner 사용 중' : 'theseus.corePath를 설정하세요.'),
        },
        {
          label: 'Workspace',
          status: workspaceCwd ? 'ok' : 'warn',
          detail: workspaceCwd || '워크스페이스 폴더를 열거나 theseus.workspacePath를 설정하세요.',
        },
        {
          label: usingBundledRunner ? 'Runner binary' : 'Python',
          status: usingBundledRunner ? 'ok' : pythonExec ? 'ok' : 'warn',
          detail: usingBundledRunner ? runnerPath : pythonExec,
        },
        {
          label: 'Runner',
          status: status.lifecycle === 'error' ? 'error' : status.running ? 'ok' : 'warn',
          detail: String(status.lifecycle || 'stopped'),
        },
        {
          label: 'Local daemon',
          status: status.processRunning ? 'ok' : 'warn',
          detail: [
            daemonStatus,
            status.daemonPid ? `pid ${status.daemonPid}` : '',
            status.daemonPort ? `port ${status.daemonPort}` : '',
          ].filter(Boolean).join(' · '),
        },
        {
          label: 'Server URL',
          status: serverHealthStatus === 'unreachable' ? 'warn' : 'ok',
          detail: String(serverForHealth.detail || serverHealthStatus),
        },
        {
          label: 'Custom tools',
          status: customToolRoots.length ? unavailableCount ? 'warn' : 'ok' : 'warn',
          detail: customToolRoots.length
            ? `${availableCount} available, ${unavailableCount} unavailable${inactiveCount ? `, ${inactiveCount} inactive` : ''}`
            : 'corePath 또는 workspacePath를 확인하세요.',
        },
      ],
    });
  }

  private withOptionalCursorContext(text: string, skipCursorContext?: boolean): string {
    if (skipCursorContext || text.trimStart().startsWith('/')) return text;
    return injectCursorContext(text);
  }

  private allowedFileRoots(): string[] {
    const roots = new Set<string>();
    const workspaceCwd = getWorkspaceCwd();
    const coreRoot = getCoreRoot(this.context);
    if (workspaceCwd) roots.add(workspaceCwd);
    if (coreRoot) roots.add(coreRoot);
    for (const folder of vscode.workspace.workspaceFolders ?? []) {
      roots.add(folder.uri.fsPath);
    }
    return [...roots].filter(Boolean);
  }

  private isAllowedFilePath(filePath: string): boolean {
    if (!path.isAbsolute(filePath)) return true;
    return this.allowedFileRoots().some(root => isInsidePath(filePath, root));
  }

  private resolveUserFilePath(filePath: string): vscode.Uri | undefined {
    if (!filePath) return undefined;
    if (path.isAbsolute(filePath)) return vscode.Uri.file(filePath);
    const workspaceRoot = getWorkspaceCwd() || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) return undefined;
    return vscode.Uri.file(path.resolve(workspaceRoot, filePath));
  }

  private async openUserFile(filePath: string): Promise<void> {
    const uri = this.resolveUserFilePath(filePath);
    if (!uri) return;
    await vscode.window.showTextDocument(uri, { preview: false });
  }

  private async revertChangedFile(id: string | undefined, filePath: string | undefined, oldContent: string | undefined): Promise<void> {
    if (!filePath || typeof oldContent !== 'string') {
      this.postRunnerEvent({
        type: 'changeReviewUpdated',
        id,
        path: filePath,
        success: false,
        message: '되돌릴 파일 정보가 부족합니다.',
      });
      return;
    }

    const uri = this.resolveUserFilePath(filePath);
    if (!uri || !this.isAllowedFilePath(uri.fsPath)) {
      this.postRunnerEvent({
        type: 'changeReviewUpdated',
        id,
        path: filePath,
        success: false,
        message: '워크스페이스 밖의 파일은 되돌릴 수 없습니다.',
      });
      return;
    }

    try {
      await fs.promises.writeFile(uri.fsPath, oldContent, 'utf8');
      this.postRunnerEvent({
        type: 'changeReviewUpdated',
        id,
        path: uri.fsPath,
        success: true,
        message: `파일을 이전 스냅샷으로 되돌렸습니다: ${vscode.workspace.asRelativePath(uri, false)}`,
      });
    } catch (err) {
      this.postRunnerEvent({
        type: 'changeReviewUpdated',
        id,
        path: uri.fsPath,
        success: false,
        message: `파일 되돌리기 실패: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.context.extensionUri, 'media')],
    };
    webviewView.webview.html = renderChatViewHtml(webviewView.webview, this.context.extensionUri);
    this.context.subscriptions.push(
      webviewView.onDidChangeVisibility(() => {
        this.messageQueue.post({ type: 'visibilityChanged', visible: webviewView.visible });
        if (!webviewView.visible) return;
        this.postSessionState();
        this.refreshActiveCursor();
      }),
    );

    webviewView.webview.onDidReceiveMessage(async (rawMsg) => {
      const msg = asWebviewToHostMessage(rawMsg);
      if (!msg) return;
      switch (msg.type) {
        case 'init':
        case 'attachSession':
        case 'getStatus':
        case 'getRunnerStatus':
          this.postSessionState();
          break;
        case 'visibilityChanged':
          this.messageQueue.post({ type: 'visibilityChanged', visible: !!msg.visible });
          break;
        case 'send':
        case 'sendInput':
          if (typeof msg.text === 'string') {
            const resolvedText = await resolveContextMentions(msg.text);
            this.sessionManager.send(this.withOptionalCursorContext(resolvedText, msg.skipCursorContext));
          }
          break;
        case 'setMode':
          if (typeof msg.mode === 'string') this.sessionManager.setMode(msg.mode);
          break;
        case 'sendWithMode':
          if (typeof msg.text === 'string') {
            const resolvedText = await resolveContextMentions(msg.text);
            this.sessionManager.send(
              this.withOptionalCursorContext(resolvedText, msg.skipCursorContext),
              typeof msg.mode === 'string' ? msg.mode : undefined,
            );
          }
          break;
        case 'getSessions':
          this.sessionController.postList();
          break;
        case 'newSession':
          this.sessionController.newSession(msg.name);
          break;
        case 'switchSession':
          this.sessionController.switchSession(msg.name);
          break;
        case 'deleteSession':
          this.sessionController.deleteSession(msg.name);
          break;
        case 'renameSession':
          this.sessionController.renameSession(msg.oldName, msg.newName);
          break;
        case 'exportSession':
          this.sessionController.exportSession(msg.name, msg.format);
          break;
        case 'reviewPlan':
          if (msg.action === 'approve') this.sessionManager.send('/plan approve');
          if (msg.action === 'reject') this.sessionManager.send('/plan reject');
          if (msg.action === 'cancel' || msg.action === 'delete') {
            this.sessionManager.interrupt();
            this.sessionManager.send(`/plan ${msg.action}`);
          }
          break;
        case 'openPlanPreview':
          if (msg.plan) await openPlanMarkdownPreview(msg.plan);
          break;
        case 'launchSession':
        case 'start':
          this.onStartRunner();
          break;
        case 'stopSession':
        case 'stop':
          this.sessionManager.stop();
          break;
        case 'interruptSession':
        case 'stopGen':
          this.sessionManager.interrupt();
          break;
        case 'showLogs':
          this.sessionManager.showLogs();
          break;
        case 'openSettings':
          vscode.commands.executeCommand('workbench.action.openSettings', 'theseus');
          break;
        case 'getHealth':
          void this.postHealthStatus();
          break;
        case 'explainProblem':
          vscode.commands.executeCommand('theseus.explainProblem');
          break;
        case 'fixProblem':
          vscode.commands.executeCommand('theseus.fixProblem');
          break;
        case 'getFiles': {
          const q = typeof msg.query === 'string' ? msg.query : '';
          try {
            const files = await findMentionFiles(q);
            this.postRunnerEvent({ type: 'filesResult', files });
          } catch {
            this.postRunnerEvent({ type: 'filesResult', files: [] });
          }
          break;
        }
        case 'getWorkspaceName': {
          // 실제 활성 워크스페이스 경로 = setting(workspacePath)이 있으면 그것, 없으면 첫 번째 폴더
          const resolved = getWorkspaceCwd() ?? '';
          const folder = vscode.workspace.workspaceFolders?.find(
            f => f.uri.fsPath === resolved,
          );
          const name = folder?.name
            || (resolved ? path.basename(resolved) : '')
            || vscode.workspace.workspaceFolders?.[0]?.name
            || 'unknown';
          this.postRunnerEvent({ type: 'workspaceInfo', name, path: resolved });
          break;
        }
        case 'selectWorktree': {
          const next = await pickWorktree(this.sessionManager);
          if (next !== undefined) {
            // 변경된 워크트리 정보를 webview에 알리고 활성 파일 컨텍스트도 갱신
            const folder = vscode.workspace.workspaceFolders?.find(f => f.uri.fsPath === next);
            const name = folder?.name || (next ? path.basename(next) : 'unknown');
            this.postRunnerEvent({ type: 'workspaceInfo', name, path: next });
            this.refreshActiveCursor();
          }
          break;
        }
        case 'getActiveFile':
          this.refreshActiveCursor();
          break;
        case 'getCustomTools':
          if (this.sessionManager.hasProcess) {
            this.refreshRuntimeToolRegistry('inventory_request');
          } else {
            this.refreshCustomToolsOnce('inventory_request', 150);
          }
          break;
        case 'refreshToolRegistry':
          this.refreshRuntimeToolRegistry('manual_refresh');
          break;
        case 'updateToolPermission': {
          if (typeof msg.metadataPath === 'string') {
            const result = await updateCustomToolPermission(msg.metadataPath, Number(msg.permissionLevel));
            if (result.success) vscode.window.showInformationMessage(result.message);
            else vscode.window.showErrorMessage(result.message);
            this.postRunnerEvent({ type: 'customToolValidation', ...result });
            await this.refreshCustomTools();
            if (result.success) this.sessionManager.refreshToolRegistry('permission_changed');
          }
          break;
        }
        case 'installCustomToolDependencies': {
          const result = await installCustomToolDependencies(msg.metadataPath, msg.modulePath);
          this.postRunnerEvent({
            type: 'customToolInstallProgress',
            success: result.success,
            message: result.message,
            packages: result.packages || [],
          });
          if (result.success) {
            vscode.window.showInformationMessage(result.message);
            this.refreshRuntimeToolRegistry('dependencies_installed');
          } else {
            vscode.window.showWarningMessage(result.message);
            await this.refreshCustomTools();
          }
          break;
        }
        case 'retryCustomToolLoad': {
          this.refreshRuntimeToolRegistry('retry_load');
          break;
        }
        case 'registerCustomTool': {
          if (typeof msg.metadataPath === 'string') {
            const result = await registerCustomTool(msg.metadataPath);
            this.postRunnerEvent({ type: 'customToolValidation', ...result });
            if (result.success) this.refreshRuntimeToolRegistry('register_custom_tool');
            else await this.refreshCustomTools();
          }
          break;
        }
        case 'disableCustomTool': {
          if (typeof msg.metadataPath === 'string') {
            const result = await disableCustomTool(msg.metadataPath);
            this.postRunnerEvent({ type: 'customToolValidation', ...result });
            if (result.success) this.refreshRuntimeToolRegistry('disable_custom_tool');
            else await this.refreshCustomTools();
          }
          break;
        }
        case 'savePastedImage': {
          try {
            const relativePath = await saveAssetToWorkspace(String(msg.name || 'image.png'), msg.data);
            this.postRunnerEvent({ type: 'assetSaved', path: relativePath });
          } catch (err) {
            this.postRunnerEvent({ type: 'assetSaveFailed', message: err instanceof Error ? err.message : String(err) });
          }
          break;
        }
        case 'openFile': {
          if (typeof msg.path === 'string') {
            await this.openUserFile(msg.path);
          }
          break;
        }
        case 'revertChangedFile':
          await this.revertChangedFile(msg.id, msg.path, msg.oldContent);
          break;
        case 'openGeneratedTool': {
          const event = msg.event as RunnerEvent | undefined;
          const metadata = event?.metadata || {};
          let uri = await resolveReadableUri(metadata.module_path || metadata.modulePath);
          if (!uri && typeof event?.output === 'string') {
            const match = event.output.match(/^File:\s*(.+)$/m);
            uri = await resolveReadableUri(match?.[1]);
          }
          if (uri) await vscode.window.showTextDocument(uri, { preview: false });
          break;
        }
        case 'openDiff': {
          const event = msg.event as RunnerEvent | undefined;
          if (event) await openChangedFileDiff(this.diffProvider, event);
          break;
        }
      }
    });

    const editorDisposable = vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (!editor) return;
      this.refreshActiveCursor();
    });
    const selectionDisposable = vscode.window.onDidChangeTextEditorSelection((event) => {
      if (event.textEditor === vscode.window.activeTextEditor) {
        this.refreshActiveCursor();
      }
    });
    webviewView.onDidDispose(() => {
      editorDisposable.dispose();
      selectionDisposable.dispose();
    });

    this.refreshActiveCursor();
    this.postSessionState();
  }
}
