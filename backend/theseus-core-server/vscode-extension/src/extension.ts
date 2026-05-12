import * as vscode from 'vscode';

import { TheseusChatViewProvider } from './providers/ChatViewProvider';
import { TheseusDiffContentProvider } from './providers/DiffProvider';
import { TheseusSessionManager } from './session/SessionManager';
import { createCustomToolWatchers } from './tools/CustomToolManager';
import {
  getCoreRoot,
  getWorkspaceCwd,
} from './workspace/WorkspaceContext';

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

export function activate(context: vscode.ExtensionContext): void {
  const sessionManager = new TheseusSessionManager(context);
  const diffProvider = new TheseusDiffContentProvider();
  const provider = new TheseusChatViewProvider(
    context,
    sessionManager,
    diffProvider,
    () => startRunner(context, sessionManager),
  );

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
        text: `@${rel}:${line}\n\`\`\`${lang}\n${text}\n\`\`\`\n이 코드를 설명해줘.`,
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
