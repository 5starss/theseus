import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

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
  loadCustomToolSummaries,
  updateCustomToolPermission,
} from '../tools/CustomToolManager';
import {
  findMentionFiles,
  getActiveCursorContext,
  getCoreRoot,
  getWorkspaceCwd,
  injectCursorContext,
} from '../workspace/WorkspaceContext';
import { getChangedFile, TheseusDiffContentProvider } from './DiffProvider';
import { renderChatViewHtml } from './ChatViewHtml';
import { SessionController } from './controllers/SessionController';
import { HealthController } from './controllers/HealthController';

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
  private readonly sessionController: SessionController;
  private readonly healthController: HealthController;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly sessionManager: TheseusSessionManager,
    private readonly diffProvider: TheseusDiffContentProvider,
    private readonly onStartRunner: () => void,
  ) {
    this.sessionController = new SessionController(this.sessionManager, event => this.postRunnerEvent(event));
    this.healthController = new HealthController(this.context, this.sessionManager, event => this.postRunnerEvent(event));
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
          if (msg.visible) this.postSessionState();
          break;
        case 'openExternal':
          if (typeof msg.url === 'string') {
            try {
              const uri = vscode.Uri.parse(msg.url);
              if (uri.scheme === 'http' || uri.scheme === 'https') {
                await vscode.env.openExternal(uri);
              }
            } catch (err) {
              this.postRunnerEvent({
                type: 'RunnerDiagnostic',
                code: 'open_external_failed',
                message: err instanceof Error ? err.message : String(err),
                state: this.sessionManager.currentState,
              });
            }
          }
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
          this.healthController.postHealthStatus();
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
