import * as vscode from 'vscode';
import * as path from 'path';

export class ComposerPanel {
    public static currentPanel: ComposerPanel | undefined;
    public static readonly viewType = 'theseusComposer';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (ComposerPanel.currentPanel) {
            ComposerPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            ComposerPanel.viewType,
            'Theseus Composer',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
            }
        );

        ComposerPanel.currentPanel = new ComposerPanel(panel, extensionUri);
    }

    public static updateChanges(changes: any[]) {
        if (ComposerPanel.currentPanel) {
            ComposerPanel.currentPanel._update(changes);
        }
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Simple initial state
        this._update([]);
        
        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'acceptAll':
                        vscode.window.showInformationMessage('Accepted all changes.');
                        // In a full implementation, we'd clear the change list
                        break;
                    case 'rejectAll':
                        vscode.window.showInformationMessage('Rejected all changes.');
                        // In a full implementation, we'd call revert on all files
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    public dispose() {
        ComposerPanel.currentPanel = undefined;

        this._panel.dispose();

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private _update(changes: any[]) {
        const webview = this._panel.webview;
        this._panel.title = 'Theseus Composer';
        this._panel.webview.html = this._getHtmlForWebview(webview, changes);
    }

    private _getHtmlForWebview(webview: vscode.Webview, changes: any[]) {
        const listHtml = changes.map(c => `
            <div class="change-item">
                <h3>${c.path || 'Unknown file'}</h3>
                <p>Status: ${c.success ? 'Success' : 'Failed'}</p>
            </div>
        `).join('') || '<p>No active file changes.</p>';

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Theseus Composer</title>
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-editor-foreground); background-color: var(--vscode-editor-background); }
        h1 { font-size: 1.5em; margin-bottom: 20px; }
        .change-item { border: 1px solid var(--vscode-panel-border); padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        .btn { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 6px 12px; cursor: pointer; border-radius: 2px; margin-right: 8px; }
        .btn:hover { background: var(--vscode-button-hoverBackground); }
        .btn-danger { background: var(--vscode-errorForeground); color: white; }
    </style>
</head>
<body>
    <h1>Multi-file Changes</h1>
    <div style="margin-bottom: 20px;">
        <button class="btn" onclick="acceptAll()">Accept All</button>
        <button class="btn btn-danger" onclick="rejectAll()">Reject All</button>
    </div>
    <div id="changes-list">
        ${listHtml}
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function acceptAll() {
            vscode.postMessage({ command: 'acceptAll' });
        }
        function rejectAll() {
            vscode.postMessage({ command: 'rejectAll' });
        }
    </script>
</body>
</html>`;
    }
}
