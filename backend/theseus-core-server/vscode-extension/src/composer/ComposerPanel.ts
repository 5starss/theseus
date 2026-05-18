import * as vscode from 'vscode';

type ComposerChangeStatus = 'pending' | 'success' | 'failed';

export type ComposerChangeItem = {
    id?: string;
    path?: string;
    relativePath?: string;
    status?: ComposerChangeStatus;
    success?: boolean;
    createdAt?: number;
    updatedAt?: number;
    completedAt?: number;
    failedAt?: number;
    durationMs?: number;
    errorMessage?: string;
    toolName?: string;
    event?: unknown;
};

export class ComposerPanel {
    public static currentPanel: ComposerPanel | undefined;
    public static readonly viewType = 'theseusComposer';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _changes: ComposerChangeItem[] = [];

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

        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);
        this._update([]);

        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'acceptAll':
                        vscode.window.showInformationMessage('No direct accept action is available yet. Review diffs in Theseus Chat.');
                        break;
                    case 'rejectAll':
                        vscode.window.showInformationMessage('No direct reject action is available yet. Use Revert from Theseus Chat change review.');
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

    private _update(changes: ComposerChangeItem[]) {
        this._changes = Array.isArray(changes) ? changes : [];
        this._panel.title = 'Theseus Composer';
        this._panel.webview.postMessage({ type: 'changes', changes: this._changes });
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Theseus Composer</title>
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-editor-foreground); background-color: var(--vscode-editor-background); }
        h1 { font-size: 1.5em; margin-bottom: 20px; }
        .toolbar { align-items: center; display: flex; gap: 8px; margin-bottom: 16px; }
        .summary { color: var(--vscode-descriptionForeground); font-size: 12px; margin-left: auto; }
        .change-item { border: 1px solid var(--vscode-panel-border); padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        .change-item.failed { border-color: var(--vscode-errorForeground); }
        .change-item.success { border-color: var(--vscode-testing-iconPassed, #3fb950); }
        .change-title { align-items: baseline; display: flex; gap: 8px; justify-content: space-between; min-width: 0; }
        .change-title h3 { font-size: 13px; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .status { border-radius: 999px; font-size: 11px; padding: 2px 7px; text-transform: capitalize; }
        .status.failed { background: var(--vscode-inputValidation-errorBackground); color: var(--vscode-errorForeground); }
        .status.success { background: var(--vscode-inputValidation-infoBackground); color: var(--vscode-testing-iconPassed, #3fb950); }
        .status.pending { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
        .meta { color: var(--vscode-descriptionForeground); font-size: 12px; line-height: 1.5; margin-top: 6px; }
        .error { color: var(--vscode-errorForeground); margin-top: 6px; white-space: pre-wrap; }
        .btn { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 6px 12px; cursor: pointer; border-radius: 2px; margin-right: 8px; }
        .btn:hover { background: var(--vscode-button-hoverBackground); }
        .btn:disabled { cursor: not-allowed; opacity: 0.5; }
        .btn-danger { background: var(--vscode-errorForeground); color: white; }
    </style>
</head>
<body>
    <h1>Multi-file Changes</h1>
    <div class="toolbar">
        <button id="accept-all" class="btn" onclick="acceptAll()" disabled title="Use Theseus Chat change review for file-level actions.">Accept All</button>
        <button id="reject-all" class="btn btn-danger" onclick="rejectAll()" disabled title="Use Theseus Chat change review for file-level actions.">Reject All</button>
        <span id="summary" class="summary">No active file changes.</span>
    </div>
    <div id="changes-list"></div>

    <script>
        const vscode = acquireVsCodeApi();
        const list = document.getElementById('changes-list');
        const summary = document.getElementById('summary');

        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>"']/g, ch => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[ch]));
        }

        function formatTime(value) {
            if (!value) return '';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return '';
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }

        function formatDuration(ms) {
            if (!Number.isFinite(ms) || ms < 0) return '';
            if (ms < 1000) return ms + 'ms';
            return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + 's';
        }

        function normalizeStatus(change) {
            if (change.status) return String(change.status);
            if (change.success === true) return 'success';
            if (change.success === false) return 'failed';
            return 'pending';
        }

        function render(changes) {
            const items = Array.isArray(changes) ? changes : [];
            const counts = items.reduce((acc, item) => {
                acc[normalizeStatus(item)] = (acc[normalizeStatus(item)] || 0) + 1;
                return acc;
            }, {});
            summary.textContent = items.length
                ? [
                    items.length + ' change' + (items.length === 1 ? '' : 's'),
                    counts.failed ? counts.failed + ' failed' : '',
                    counts.success ? counts.success + ' success' : '',
                    counts.pending ? counts.pending + ' pending' : '',
                  ].filter(Boolean).join(' · ')
                : 'No active file changes.';

            if (!items.length) {
                list.innerHTML = '<p>No active file changes.</p>';
                return;
            }

            list.innerHTML = items.map(change => {
                const status = normalizeStatus(change);
                const statusAt = status === 'failed'
                    ? change.failedAt || change.updatedAt || change.completedAt
                    : status === 'success'
                        ? change.completedAt || change.updatedAt
                        : change.updatedAt || change.createdAt;
                const duration = formatDuration(change.durationMs);
                const meta = [
                    change.toolName ? 'tool: ' + change.toolName : '',
                    statusAt ? status + ' at ' + formatTime(statusAt) : '',
                    duration ? 'duration ' + duration : '',
                ].filter(Boolean).join(' · ');
                return [
                    '<div class="change-item ' + escapeHtml(status) + '">',
                    '  <div class="change-title">',
                    '    <h3 title="' + escapeHtml(change.path || '') + '">' + escapeHtml(change.relativePath || change.path || 'Unknown file') + '</h3>',
                    '    <span class="status ' + escapeHtml(status) + '">' + escapeHtml(status) + '</span>',
                    '  </div>',
                    meta ? '  <div class="meta">' + escapeHtml(meta) + '</div>' : '',
                    change.errorMessage ? '  <div class="error">' + escapeHtml(change.errorMessage) + '</div>' : '',
                    '</div>',
                ].join('');
            }).join('');
        }

        window.addEventListener('message', event => {
            if (event.data?.type === 'changes') render(event.data.changes);
        });

        function acceptAll() {
            vscode.postMessage({ command: 'acceptAll' });
        }
        function rejectAll() {
            vscode.postMessage({ command: 'rejectAll' });
        }
        render([]);
    </script>
</body>
</html>`;
    }
}
