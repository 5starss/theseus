import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

import { resolveReadableUri, saveAssetToWorkspace } from '../assets/AssetStore';
import {
  createLocalSession,
  deleteLocalSession,
  exportLocalSession,
  listLocalSessionSummaries,
  renameLocalSession,
  switchLocalSession,
  type LocalSessionActionResult,
} from '../session/LocalSessionStore';
import { TheseusSessionManager } from '../session/SessionManager';
import {
  asHostToWebviewMessage,
  asWebviewToHostMessage,
  type HostToWebviewMessage,
  type JsonObject,
  type RunnerEvent,
} from '../shared/protocol';
import {
  loadCustomToolSummaries,
  updateCustomToolPermission,
} from '../tools/CustomToolManager';
import {
  findMentionFiles,
  getActiveCursorContext,
  getCoreRoot,
  getCustomToolSearchRoots,
  getWorkspaceCwd,
  injectCursorContext,
} from '../workspace/WorkspaceContext';
import { getChangedFile, TheseusDiffContentProvider } from './DiffProvider';
import { renderChatViewHtml } from './ChatViewHtml';

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

function makeUntitledSessionName(): string {
  const now = new Date();
  const pad = (value: number, size = 2) => String(value).padStart(size, '0');
  return [
    'session',
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
    pad(now.getMilliseconds(), 3),
  ].join('');
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

export class TheseusChatViewProvider implements vscode.WebviewViewProvider {
  static readonly viewType = 'theseus.chatView';
  private view: vscode.WebviewView | undefined;
  private readonly messageQueue = new WebviewMessageQueue(() => this.view?.webview);

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly sessionManager: TheseusSessionManager,
    private readonly diffProvider: TheseusDiffContentProvider,
    private readonly onStartRunner: () => void,
  ) {
    this.sessionManager.onEvent((event) => {
      this.postRunnerEvent(event);
      if (event.type === 'RunnerDiagnostic') {
        this.messageQueue.post({ type: 'diagnostic', diagnostic: event });
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
    void this.refreshCustomTools();
  }

  private postRunnerEvent(event: RunnerEvent): void {
    this.messageQueue.post({ type: 'runnerEvent', event });
  }

  private localSessionWorkspace(): string | undefined {
    const status = this.sessionManager.status;
    return typeof status.workspaceCwd === 'string' ? status.workspaceCwd : getWorkspaceCwd();
  }

  private currentSessionName(): string {
    const status = this.sessionManager.status;
    return typeof status.session === 'string' && status.session ? status.session : 'default';
  }

  private postLocalSessionSnapshot(snapshot: LocalSessionActionResult): void {
    this.sessionManager.setPreferredSession(snapshot.current);
    this.postRunnerEvent({
      type: 'SessionListEvent',
      source: 'local',
      current: snapshot.current,
      sessions: snapshot.sessions,
    });
    this.postRunnerEvent({
      type: 'SessionChangedEvent',
      source: 'local',
      current: snapshot.current,
      history: snapshot.history,
      planState: snapshot.planState,
    });
  }

  private postLocalSessionError(error: unknown): void {
    this.postRunnerEvent({
      type: 'RunnerDiagnostic',
      code: 'session_error',
      message: error instanceof Error ? error.message : String(error),
      state: this.sessionManager.currentState,
    });
  }

  private canRouteSessionCommandToRunner(): boolean {
    return this.sessionManager.hasProcess && ['ready', 'waiting_input'].includes(this.sessionManager.currentState);
  }

  private canHandleSessionLocally(): boolean {
    return !this.sessionManager.hasProcess || ['stopped', 'error', 'exited', 'stale'].includes(this.sessionManager.currentState);
  }

  private postSessionBusyNotice(): void {
    this.postRunnerEvent({
      type: 'RunnerDiagnostic',
      code: 'session_busy',
      message: 'Session changes are available after the current run finishes or the runner is stopped.',
      state: this.sessionManager.currentState,
    });
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
    this.messageQueue.post({
      type: 'runnerEvent',
      event: { type: 'customToolsLoaded', tools },
    });
  }

  private postHealthStatus(): void {
    const coreRoot = getCoreRoot(this.context) || '';
    const workspaceCwd = getWorkspaceCwd() || '';
    const config = vscode.workspace.getConfiguration('theseus');
    const pythonExec = config.get<string>('pythonPath') || 'python';
    const serverUrl = config.get<string>('serverUrl') || '';
    const status = this.sessionManager.status;
    const customToolRoots = getCustomToolSearchRoots();
    this.postRunnerEvent({
      type: 'healthStatus',
      settings: {
        corePath: coreRoot,
        pythonPath: pythonExec,
        serverUrl,
        workspacePath: workspaceCwd,
        coreRoot,
        workspaceCwd,
        pythonExec,
        customToolRoots,
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
          status: coreRoot ? 'ok' : 'error',
          detail: coreRoot || 'theseus.corePath를 설정하세요.',
        },
        {
          label: 'Workspace',
          status: workspaceCwd ? 'ok' : 'warn',
          detail: workspaceCwd || '워크스페이스 폴더를 열거나 theseus.workspacePath를 설정하세요.',
        },
        {
          label: 'Python',
          status: pythonExec ? 'ok' : 'warn',
          detail: pythonExec,
        },
        {
          label: 'Runner',
          status: status.lifecycle === 'error' ? 'error' : status.running ? 'ok' : 'warn',
          detail: String(status.lifecycle || 'stopped'),
        },
        {
          label: 'Custom tools',
          status: customToolRoots.length ? 'ok' : 'warn',
          detail: customToolRoots.length
            ? customToolRoots.join(' | ')
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
          if (typeof msg.text === 'string') this.sessionManager.send(this.withOptionalCursorContext(msg.text, msg.skipCursorContext));
          break;
        case 'setMode':
          if (typeof msg.mode === 'string') this.sessionManager.setMode(msg.mode);
          break;
        case 'sendWithMode':
          if (typeof msg.text === 'string') {
            this.sessionManager.send(
              this.withOptionalCursorContext(msg.text, msg.skipCursorContext),
              typeof msg.mode === 'string' ? msg.mode : undefined,
            );
          }
          break;
        case 'getSessions':
          {
            const current = this.currentSessionName();
            const workspaceCwd = this.localSessionWorkspace();
            this.postRunnerEvent({
              type: 'SessionListEvent',
              source: 'local',
              current,
              sessions: listLocalSessionSummaries(workspaceCwd, current),
            });
          }
          break;
        case 'newSession':
          {
            const name = typeof msg.name === 'string' && msg.name.trim() ? msg.name.trim() : makeUntitledSessionName();
            if (this.canRouteSessionCommandToRunner()) {
              this.sessionManager.send(`/session new ${JSON.stringify(name)}`);
            } else if (this.canHandleSessionLocally()) {
              try {
                this.postLocalSessionSnapshot(createLocalSession(this.localSessionWorkspace(), name));
              } catch (err) {
                this.postLocalSessionError(err);
              }
            } else {
              this.postSessionBusyNotice();
            }
          }
          break;
        case 'switchSession':
          if (typeof msg.name === 'string') {
            if (this.canRouteSessionCommandToRunner()) {
              this.sessionManager.send(`/session switch ${JSON.stringify(msg.name)}`);
            } else if (this.canHandleSessionLocally()) {
              try {
                this.postLocalSessionSnapshot(switchLocalSession(this.localSessionWorkspace(), msg.name));
              } catch (err) {
                this.postLocalSessionError(err);
              }
            } else {
              this.postSessionBusyNotice();
            }
          }
          break;
        case 'deleteSession':
          if (typeof msg.name === 'string') {
            if (this.canRouteSessionCommandToRunner()) {
              this.sessionManager.send(`/session delete ${JSON.stringify(msg.name)}`);
            } else if (this.canHandleSessionLocally()) {
              try {
                this.postLocalSessionSnapshot(deleteLocalSession(this.localSessionWorkspace(), msg.name, this.currentSessionName()));
              } catch (err) {
                this.postLocalSessionError(err);
              }
            } else {
              this.postSessionBusyNotice();
            }
          }
          break;
        case 'renameSession':
          if (typeof msg.oldName === 'string' && typeof msg.newName === 'string') {
            if (this.canRouteSessionCommandToRunner()) {
              this.sessionManager.send(`/session rename ${JSON.stringify(msg.oldName)} ${JSON.stringify(msg.newName)}`);
            } else if (this.canHandleSessionLocally()) {
              try {
                this.postLocalSessionSnapshot(renameLocalSession(this.localSessionWorkspace(), msg.oldName, msg.newName, this.currentSessionName()));
              } catch (err) {
                this.postLocalSessionError(err);
              }
            } else {
              this.postSessionBusyNotice();
            }
          }
          break;
        case 'exportSession':
          if (typeof msg.name === 'string' && typeof msg.format === 'string') {
            if (this.canRouteSessionCommandToRunner()) {
              this.sessionManager.send(`/session export ${JSON.stringify(msg.name)} ${msg.format}`);
            } else if (this.canHandleSessionLocally()) {
              try {
                this.postRunnerEvent({
                  type: 'SessionExportedEvent',
                  ...exportLocalSession(this.localSessionWorkspace(), msg.name, msg.format),
                });
              } catch (err) {
                this.postLocalSessionError(err);
              }
            } else {
              this.postSessionBusyNotice();
            }
          }
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
          this.postHealthStatus();
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
          const name = vscode.workspace.workspaceFolders?.[0]?.name ?? 'unknown';
          const wpath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
          this.postRunnerEvent({ type: 'workspaceInfo', name, path: wpath });
          break;
        }
        case 'getActiveFile':
          this.refreshActiveCursor();
          break;
        case 'getCustomTools':
          await this.refreshCustomTools();
          break;
        case 'updateToolPermission': {
          if (typeof msg.metadataPath === 'string') {
            const result = await updateCustomToolPermission(msg.metadataPath, Number(msg.permissionLevel));
            if (result.success) vscode.window.showInformationMessage(result.message);
            else vscode.window.showErrorMessage(result.message);
            this.postRunnerEvent({ type: 'customToolValidation', ...result });
            await this.refreshCustomTools();
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
    void this.refreshCustomTools();
    this.postSessionState();
  }
}
