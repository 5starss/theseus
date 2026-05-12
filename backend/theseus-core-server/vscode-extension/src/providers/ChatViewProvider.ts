import * as vscode from 'vscode';

import { resolveReadableUri, saveAssetToWorkspace } from '../assets/AssetStore';
import { listLocalSessionSummaries } from '../session/LocalSessionStore';
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
          if (typeof msg.text === 'string') this.sessionManager.send(injectCursorContext(msg.text));
          break;
        case 'setMode':
          if (typeof msg.mode === 'string') this.sessionManager.setMode(msg.mode);
          break;
        case 'sendWithMode':
          if (typeof msg.mode === 'string') this.sessionManager.setMode(msg.mode);
          if (typeof msg.text === 'string') this.sessionManager.send(injectCursorContext(msg.text));
          break;
        case 'getSessions':
          if (this.sessionManager.isRunning) {
            this.sessionManager.send('/session list');
          } else {
            const status = this.sessionManager.status;
            const current = typeof status.session === 'string' ? status.session : 'default';
            const workspaceCwd = typeof status.workspaceCwd === 'string' ? status.workspaceCwd : getWorkspaceCwd();
            this.postRunnerEvent({
              type: 'SessionListEvent',
              source: 'local',
              current,
              sessions: listLocalSessionSummaries(workspaceCwd, current),
            });
          }
          break;
        case 'newSession':
          if (typeof msg.name === 'string') this.sessionManager.send(`/session new ${JSON.stringify(msg.name)}`);
          break;
        case 'switchSession':
          if (typeof msg.name === 'string') this.sessionManager.send(`/session switch ${JSON.stringify(msg.name)}`);
          break;
        case 'renameSession':
          if (typeof msg.oldName === 'string' && typeof msg.newName === 'string') {
            this.sessionManager.send(`/session rename ${JSON.stringify(msg.oldName)} ${JSON.stringify(msg.newName)}`);
          }
          break;
        case 'exportSession':
          if (typeof msg.name === 'string' && typeof msg.format === 'string') {
            this.sessionManager.send(`/session export ${JSON.stringify(msg.name)} ${msg.format}`);
          }
          break;
        case 'reviewPlan':
          if (msg.action === 'approve') this.sessionManager.send('/plan approve');
          if (msg.action === 'reject') this.sessionManager.send('/plan reject');
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
            const wsFolders = vscode.workspace.workspaceFolders;
            if (wsFolders?.length) {
              const uri = vscode.Uri.joinPath(wsFolders[0].uri, msg.path);
              vscode.window.showTextDocument(uri);
            }
          }
          break;
        }
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
