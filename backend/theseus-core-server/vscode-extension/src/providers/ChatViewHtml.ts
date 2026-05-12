import * as vscode from 'vscode';

export function renderChatViewHtml(webview: vscode.Webview, extensionUri: vscode.Uri): string {
  const protocolUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'protocol.js'));
  const markdownUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'markdown.js'));
  const runnerStatusUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'runnerStatus.js'));
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'main.js'));
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'styles.css'));
  const nonce = String(Date.now());

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src ${webview.cspSource}; script-src ${webview.cspSource} 'nonce-${nonce}';">
  <link href="${styleUri}" rel="stylesheet">
  <title>Theseus</title>
</head>
<body>
  <main class="shell">

    <!-- ── 툴바 ── -->
    <div class="toolbar">
      <button id="start"         title="Start agent">▶</button>
      <button id="stop"          title="Stop agent">■</button>
      <button id="clear-history" title="Clear chat">🗑</button>
      <span id="loop-status" class="loop-status idle" title="Agent loop status">idle</span>
      <span id="workspace-label" class="workspace-label" title="Active workspace"></span>
      <span id="active-file-label" class="active-file-label" title=""></span>
      <div class="popup-anchor session-anchor" id="session-anchor">
        <button type="button" id="session-label" class="session-label" title="Session">default ▾</button>
        <div id="session-menu" class="session-menu" hidden></div>
      </div>
    </div>

    <!-- ── 메시지 영역 ── -->
    <section id="plan-panel" class="plan-panel" hidden></section>
    <section id="messages" class="messages"></section>

    <!-- ── 툴 실행 패널 ── -->
    <section id="tools" class="tools"></section>

    <!-- ── 커스텀 툴 목록 패널 ── -->
    <section id="custom-tools" class="custom-tools"></section>

    <!-- ── 입력 영역 ── -->
    <div class="composer-wrap">
      <!-- 자동완성 드롭다운 -->
      <ul id="autocomplete-list" hidden></ul>

      <form id="composer">
        <div class="composer-box">
          <textarea id="prompt" rows="1"
            placeholder="Ask anything, @ to mention, / for commands…"></textarea>

          <div class="composer-footer">
            <!-- + 메뉴 -->
            <div class="popup-anchor" id="plus-anchor">
              <button type="button" id="plus-btn" class="icon-btn" title="Add">+</button>
              <ul id="plus-menu" class="popup-menu" hidden>
                <li data-action="at"><span class="menu-icon">@</span>파일 멘션</li>
                <li data-action="slash"><span class="menu-icon">/</span>슬래시 명령어</li>
              </ul>
            </div>

            <!-- 모드 칩 -->
            <div class="popup-anchor" id="mode-anchor">
              <button type="button" id="mode-chip" class="mode-chip" title="모드 선택">
                <span id="mode-chip-label">AGENT</span>
                <span class="chip-arrow">▾</span>
              </button>
              <div id="mode-popup" class="mode-popup" hidden>
                <div class="mode-popup-title">모드</div>
                <button class="mode-option active" data-mode="agent">
                  <span class="mode-option-icon">🤖</span>
                  <div class="mode-option-info">
                    <strong>Agent</strong>
                    <span>자율 실행 · 툴 사용</span>
                  </div>
                  <span class="mode-option-check">✓</span>
                </button>
                <button class="mode-option" data-mode="ask">
                  <span class="mode-option-icon">💬</span>
                  <div class="mode-option-info">
                    <strong>Ask</strong>
                    <span>Q&amp;A 전용 · 툴 미사용</span>
                  </div>
                  <span class="mode-option-check">✓</span>
                </button>
                <button class="mode-option" data-mode="plan">
                  <span class="mode-option-icon">📋</span>
                  <div class="mode-option-info">
                    <strong>Plan</strong>
                    <span>계획 수립 → 검토 → 실행</span>
                  </div>
                  <span class="mode-option-check">✓</span>
                </button>
              </div>
            </div>

            <!-- 생성 중단 -->
            <button type="button" id="stop-gen" class="icon-btn stop-gen-btn" hidden title="Stop generation">⏹</button>

            <!-- 전송 -->
            <button type="submit" id="send-btn" class="send-btn" title="Send (Enter)">↵</button>
          </div>
        </div>
      </form>

      <div class="hint-bar">@ 파일멘션 &nbsp;·&nbsp; / 명령어 &nbsp;·&nbsp; Shift+Enter 줄바꿈</div>
    </div>

  </main>
  <script nonce="${nonce}" src="${protocolUri}"></script>
  <script nonce="${nonce}" src="${markdownUri}"></script>
  <script nonce="${nonce}" src="${runnerStatusUri}"></script>
  <script nonce="${nonce}" type="module" src="${scriptUri}"></script>
</body>
</html>`;
}
