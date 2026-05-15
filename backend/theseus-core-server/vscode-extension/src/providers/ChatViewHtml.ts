import * as vscode from 'vscode';
import * as fs from 'fs';

export function renderChatViewHtml(webview: vscode.Webview, extensionUri: vscode.Uri): string {
  const protocolUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'protocol.js')).toString();
  const markdownUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'markdown.js')).toString();
  const runnerStatusUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'runnerStatus.js')).toString();
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'main.js')).toString();
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'styles.css')).toString();
  const nonce = String(Date.now());
  const cspSource = webview.cspSource;

  const htmlPath = vscode.Uri.joinPath(extensionUri, 'media', 'index.html').fsPath;
  let html = fs.readFileSync(htmlPath, 'utf8');

  html = html.replace(/\{\{cspSource\}\}/g, cspSource)
             .replace(/\{\{nonce\}\}/g, nonce)
             .replace(/\{\{styleUri\}\}/g, styleUri)
             .replace(/\{\{protocolUri\}\}/g, protocolUri)
             .replace(/\{\{markdownUri\}\}/g, markdownUri)
             .replace(/\{\{runnerStatusUri\}\}/g, runnerStatusUri)
             .replace(/\{\{scriptUri\}\}/g, scriptUri);

  return html;
}
