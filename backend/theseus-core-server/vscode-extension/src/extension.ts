import * as vscode from 'vscode';

import { TheseusChatViewProvider } from './providers/ChatViewProvider';
import { TheseusDiffContentProvider } from './providers/DiffProvider';
import { TheseusSessionManager } from './session/SessionManager';
import { createCustomToolWatchers } from './tools/CustomToolManager';
import {
  getCoreRoot,
  getWorkspaceCwd,
} from './workspace/WorkspaceContext';
import { InlineEditController } from './inline/InlineEditController';

function startRunner(context: vscode.ExtensionContext, sessionManager: TheseusSessionManager): void {
  const coreRoot = getCoreRoot(context);
  if (!coreRoot) {
    vscode.window.showErrorMessage(
      'Cannot find theseus_engine/. Set "theseus.corePath" to the theseus-core-server directory.',
      'Open Settings',
    ).then(c => {
      if (c === 'Open Settings') {
        vscode.commands.executeCommand('workbench.action.openSettings', 'theseus.corePath');
      }
    });
    return;
  }

  const workspaceCwd = getWorkspaceCwd() ?? coreRoot;

  sessionManager.output.show(true);
  void sessionManager.ensureSession(coreRoot, workspaceCwd);
}

function diagnosticAtCursor(editor: vscode.TextEditor): vscode.Diagnostic | undefined {
  const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
  const position = editor.selection.active;
  return diagnostics.find(diagnostic => diagnostic.range.contains(position)) || diagnostics[0];
}

function isDiagnosticLike(value: unknown): value is vscode.Diagnostic {
  const item = value as Partial<vscode.Diagnostic> | undefined;
  return !!item && typeof item.message === 'string' && !!item.range;
}

function uriFromCommandArgs(args: unknown[]): vscode.Uri | undefined {
  for (const arg of args) {
    if (arg instanceof vscode.Uri) return arg;
    const record = arg as { resourceUri?: unknown; uri?: unknown } | undefined;
    if (record?.resourceUri instanceof vscode.Uri) return record.resourceUri;
    if (record?.uri instanceof vscode.Uri) return record.uri;
  }
  return undefined;
}

function diagnosticFromCommandArgs(args: unknown[], uri: vscode.Uri | undefined): vscode.Diagnostic | undefined {
  for (const arg of args) {
    if (isDiagnosticLike(arg)) return arg;
    const record = arg as { diagnostic?: unknown } | undefined;
    if (isDiagnosticLike(record?.diagnostic)) return record.diagnostic;
  }
  if (uri) return vscode.languages.getDiagnostics(uri)[0];
  return undefined;
}

function diagnosticPrompt(kind: 'explain' | 'fix', uri: vscode.Uri, diagnostic: vscode.Diagnostic): string {
  const rel = vscode.workspace.asRelativePath(uri);
  const line = diagnostic.range.start.line + 1;
  const code = diagnostic.code === undefined
    ? ''
    : typeof diagnostic.code === 'object'
      ? String(diagnostic.code.value)
      : String(diagnostic.code);
  const details = [
    `file: ${rel}`,
    `line: ${line}`,
    `message: ${diagnostic.message}`,
    code ? `code: ${code}` : '',
    diagnostic.source ? `source: ${diagnostic.source}` : '',
  ].filter(Boolean).join('\n');
  const instruction = kind === 'fix'
    ? 'Fix this VSCode Problems diagnostic.'
    : 'Explain the cause of this VSCode Problems diagnostic and suggest a fix direction.';
  return `@${rel}:${line}\n${details}\n\n${instruction}`;
}

function injectProblemPrompt(
  provider: TheseusChatViewProvider,
  kind: 'explain' | 'fix',
  args: unknown[] = [],
): void {
  const editor = vscode.window.activeTextEditor;
  const uri = uriFromCommandArgs(args) || editor?.document.uri;
  const diagnostic = diagnosticFromCommandArgs(args, uri) || (editor ? diagnosticAtCursor(editor) : undefined);
  if (!uri) {
    vscode.window.showWarningMessage('Theseus: 진단을 보낼 파일을 찾지 못했습니다.');
    return;
  }
  if (!diagnostic) {
    vscode.window.showWarningMessage('Theseus: 선택한 Problems 진단을 찾지 못했습니다.');
    return;
  }
  provider.postToWebview({
    type: 'injectText',
    text: diagnosticPrompt(kind, uri, diagnostic),
    autoSubmit: false,
  });
  vscode.commands.executeCommand('theseus.chatView.focus');
}

export function activate(context: vscode.ExtensionContext): void {
  const sessionManager = new TheseusSessionManager(context);
  const diffProvider = new TheseusDiffContentProvider();
  const provider = new TheseusChatViewProvider(
    context,
    sessionManager,
    diffProvider,
    () => startRunner(context, sessionManager),
  );

  const inlineEditController = new InlineEditController(sessionManager);

  const customToolWatchers = createCustomToolWatchers(({ action, file, validation }) => {
    provider.postToWebview({ type: 'customToolsChanged', action, file, validation });
    const validationMessage = `Theseus custom tool ${action}: ${validation.message}`;
    if (validation.success) {
      vscode.window.showInformationMessage(validationMessage);
    } else {
      vscode.window.showWarningMessage(validationMessage);
    }
    void provider.refreshCustomTools();
  });

  context.subscriptions.push(
    sessionManager,
    inlineEditController,
    ...customToolWatchers,
    vscode.workspace.registerTextDocumentContentProvider('theseus-diff', diffProvider),
    vscode.window.registerWebviewViewProvider(TheseusChatViewProvider.viewType, provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),

    vscode.commands.registerCommand('theseus.start', () => startRunner(context, sessionManager)),
    vscode.commands.registerCommand('theseus.stop', () => sessionManager.stop()),
    vscode.commands.registerCommand('theseus.showLogs', () => sessionManager.showLogs()),

    vscode.commands.registerCommand('theseus.askSelected', () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const sel = editor.selection;
      const text = editor.document.getText(sel).trim();
      if (!text) return;
      const rel = vscode.workspace.asRelativePath(editor.document.uri);
      const lang = editor.document.languageId;
      const line = sel.start.line + 1;
      provider.postToWebview({
        type: 'injectText',
        text: `@${rel}:${line}\n\`\`\`${lang}\n${text}\n\`\`\`\n`,
      });
      vscode.commands.executeCommand('theseus.chatView.focus');
    }),

    vscode.commands.registerCommand('theseus.explainProblem', (...args: unknown[]) => injectProblemPrompt(provider, 'explain', args)),
    vscode.commands.registerCommand('theseus.fixProblem', (...args: unknown[]) => injectProblemPrompt(provider, 'fix', args)),

    vscode.commands.registerCommand('theseus.explainSelected', () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;
      const sel = editor.selection;
      const text = editor.document.getText(sel).trim();
      if (!text) return;
      const rel = vscode.workspace.asRelativePath(editor.document.uri);
      const lang = editor.document.languageId;
      const line = sel.start.line + 1;
      provider.postToWebview({
        type: 'injectText',
        text: `@${rel}:${line}\n\`\`\`${lang}\n${text}\n\`\`\`\nExplain this code.`,
        autoSubmit: false,
      });
      vscode.commands.executeCommand('theseus.chatView.focus');
    }),

    vscode.commands.registerCommand('theseus.moveToSecondarySidebar', () => {
      vscode.window.showInformationMessage(
        'Drag the Theseus icon from the Activity Bar to the Secondary Side Bar (right side). ' +
        'Or right-click the icon -> "Move to Secondary Side Bar".',
      );
    }),
    vscode.commands.registerCommand('theseus.moveToPanel', () => {
      vscode.commands.executeCommand('workbench.view.extension.theseus');
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event.affectsConfiguration('theseus')) return;
      provider.postToWebview({
        type: 'settingsChanged',
        restartRequired: sessionManager.isRunning,
      });
      if (sessionManager.isRunning) {
        vscode.window.showInformationMessage('Theseus settings changed. Restart the agent to apply them.');
      }
    }),
  );
}

export function deactivate(): void {}
