export function isTransientSystemText(text) {
  const value = String(text || '');
  return [
    '에이전트가 시작되지 않았습니다',
    '에이전트가 시작 중입니다',
    '에이전트 연결 상태를 다시 확인 중입니다',
    'Runner startup is taking longer than expected',
    'Runner emitted non-JSON stdout',
    'Last runner diagnostic',
    'Connected  model:',
    'Runner stopped',
    'Runner stopped gracefully',
    'Auto-compacting conversation memory',
    'Prompt too long; compacting and retrying',
    'View > Output > "Theseus"',
    'Settings changed.',
  ].some(fragment => value.includes(fragment));
}

export function shouldPersistMessage(role, text, save) {
  if (!save) return false;
  if (role === 'system' && isTransientSystemText(text)) return false;
  return true;
}

export function maybeAddFold(article, body, text, { messagesEl, threshold }) {
  const lines = (text || '').split('\n').length;
  if (lines < threshold) return;
  if (article.querySelector('.fold-btn')) return;
  body.classList.add('folded');
  const foldBtn = document.createElement('button');
  foldBtn.className = 'fold-btn';
  foldBtn.textContent = `▼ 더 보기 (${lines}줄)`;
  foldBtn.addEventListener('click', () => {
    const folded = body.classList.toggle('folded');
    foldBtn.textContent = folded ? `▼ 더 보기 (${lines}줄)` : '▲ 접기';
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
  article.appendChild(foldBtn);
}

export function createTypingIndicator(messagesEl) {
  const article = document.createElement('article');
  article.className = 'message assistant';

  const labelRow = document.createElement('div');
  labelRow.className = 'label-row';
  const label = document.createElement('span');
  label.className = 'label';
  label.textContent = 'assistant';
  labelRow.appendChild(label);

  const body = document.createElement('div');
  body.className = 'body';
  body.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  article.append(labelRow, body);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { article, body };
}

export function appendRetryBanner(messagesEl, onRestart) {
  const banner = document.createElement('div');
  banner.className = 'retry-banner';
  const btn = document.createElement('button');
  btn.textContent = '↺ Restart Agent';
  btn.addEventListener('click', () => {
    banner.remove();
    onRestart();
  });
  banner.appendChild(btn);
  messagesEl.appendChild(banner);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
