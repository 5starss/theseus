export function isTransientSystemText(text) {
  const value = String(text || '');
  return [
    '에이전트가 시작되지 않았습니다',
    '에이전트가 시작 중입니다',
    '에이전트 연결 상태를 다시 확인 중입니다',
    'Runner startup is taking longer than expected',
    'Runner has not emitted RunnerReady',
    'Local daemon heartbeat is stale',
    'Runner emitted non-JSON stdout',
    'Local daemon failed to start',
    'Local daemon did not become healthy',
    'Last runner diagnostic',
    'Connected  model:',
    'Runner stopped',
    'Runner stopped gracefully',
    'Session changes are available',
    '현재 run이 끝나면',
    '현재 run이 아직 진행 중입니다',
    '세션 전환:',
    '세션 삭제:',
    '세션 이름 변경:',
    '세션 전환 대기 중',
    'Auto-compacting conversation memory',
    'Prompt too long; compacting and retrying',
    'View > Output > "Theseus"',
    'Settings changed.',
    'Custom tool validation',
    'Custom tool dependency install',
    'Dependency installation',
    'Installed dependencies:',
    'Tool registry refreshed',
    'Change review updated',
    '되돌릴 파일',
    'Dependency installation cancelled',
    'No install candidates',
    'Python path is not explicitly configured',
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
  // 기본은 펼친 상태로 노출 (사용자가 원할 때만 접도록 반전)
  const foldBtn = document.createElement('button');
  foldBtn.className = 'fold-btn';
  foldBtn.textContent = `▲ 접기 (${lines}줄)`;
  foldBtn.addEventListener('click', () => {
    const folded = body.classList.toggle('folded');
    foldBtn.textContent = folded ? `▼ 펼치기 (${lines}줄)` : `▲ 접기 (${lines}줄)`;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
  article.appendChild(foldBtn);
}

export function createTypingIndicator(messagesEl) {
  const article = document.createElement('article');
  article.className = 'message assistant';

  const labelRow = document.createElement('div');
  labelRow.className = 'label-row';
  const avatar = document.createElement('span');
  avatar.className = 'role-avatar assistant-avatar';
  avatar.textContent = '✦';
  const label = document.createElement('span');
  label.className = 'label';
  label.textContent = 'assistant';
  labelRow.append(avatar, label);

  const body = document.createElement('div');
  body.className = 'body';
  body.innerHTML = '<div class="typing-indicator"></div>';

  article.append(labelRow, body);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { article, body };
}

/** 메시지 영역의 모든 retry banner를 제거. runner가 ready/running 상태가 되었을 때 호출. */
export function clearRetryBanners(messagesEl) {
  if (!messagesEl) return;
  messagesEl.querySelectorAll('.retry-banner').forEach(el => el.remove());
}

/** runner 상태/진단성 system message는 runner가 정상화되면 채팅 흐름에서 제거한다. */
export function clearTransientSystemMessages(messagesEl) {
  if (!messagesEl) return;
  messagesEl.querySelectorAll('.message.system').forEach(el => {
    const text = el.querySelector('.body')?.textContent || el.textContent || '';
    if (isTransientSystemText(text)) el.remove();
  });
}

export function appendRetryBanner(messagesEl, onRestart) {
  // 이미 retry banner가 있으면 중복 추가하지 않음 (재시도 실패 누적 방지)
  if (messagesEl?.querySelector('.retry-banner')) return;
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
