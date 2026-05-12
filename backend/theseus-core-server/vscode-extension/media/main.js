import { createAutocompleteController } from './components/Autocomplete.js';
import {
  bindImageAttachments,
  insertMentionPath as insertMentionPathInPrompt,
} from './components/Composer.js';
import { renderCustomTools as renderCustomToolsComponent } from './components/CustomTools.js';
import {
  appendRetryBanner,
  createTypingIndicator,
  isTransientSystemText,
  maybeAddFold,
  shouldPersistMessage,
} from './components/MessageList.js';
import { renderPlanPanel as renderPlanPanelComponent } from './components/PlanPanel.js';
import {
  applyRunnerStatusEvent,
  formatAgentLoopStatus,
  setLoopStatus as renderLoopStatus,
} from './components/RunnerStatus.js';
import { renderSessionMenu as renderSessionMenuComponent } from './components/SessionMenu.js';
import { createToolPanelController } from './components/ToolPanel.js';
import { createInitialState, persistWebviewState } from './state.js';

(function () {
  'use strict';

  const rawVsCode = acquireVsCodeApi();
  const vscode = window.TheseusProtocol?.createVsCodeApi(rawVsCode) || rawVsCode;
  const normalizeHostMessage = window.TheseusProtocol?.normalizeHostMessage || (message => message);
  const webviewMarkdown = window.TheseusMarkdown;
  const runnerStatus = window.TheseusRunnerStatus;

  if (!webviewMarkdown?.renderMarkdown || !runnerStatus?.normalizeLifecycle || !runnerStatus?.runnerDiagnosticText) {
    throw new Error('Theseus WebView helper modules failed to load.');
  }

  const renderMarkdown = webviewMarkdown.renderMarkdown;
  const normalizeRunnerLifecycle = runnerStatus.normalizeLifecycle;
  const formatRunnerDiagnostic = runnerStatus.runnerDiagnosticText;

  // ── DOM refs ──────────────────────────────────────────────────────
  const messagesEl       = document.getElementById('messages');
  const toolsEl          = document.getElementById('tools');
  const customToolsEl    = document.getElementById('custom-tools');
  const planPanelEl      = document.getElementById('plan-panel');
  const promptEl         = document.getElementById('prompt');
  const composerEl       = document.getElementById('composer');
  const startBtn         = document.getElementById('start');
  const stopBtn          = document.getElementById('stop');
  const acListEl         = document.getElementById('autocomplete-list');
  const sessionEl        = document.getElementById('session-label');
  const sessionMenuEl    = document.getElementById('session-menu');
  const stopGenBtn       = document.getElementById('stop-gen');
  const loopStatusEl     = document.getElementById('loop-status');
  const activeFileEl     = document.getElementById('active-file-label');
  const workspaceLabelEl = document.getElementById('workspace-label');
  const modeChipLabel    = document.getElementById('mode-chip-label');
  const modePopupEl      = document.getElementById('mode-popup');
  const modeChipBtn      = document.getElementById('mode-chip');
  const plusBtn          = document.getElementById('plus-btn');
  const plusMenuEl       = document.getElementById('plus-menu');

  // ── 상수 (const는 선언 전 접근 불가 → 최상단에 위치) ─────────────
  const FOLD_THRESHOLD = 25;
  const TOOL_VISIBLE_LIMIT = 30;
  const LONG_RUNNING_MS = 30000;
  const MODE_LABELS    = { agent: 'AGENT', ask: 'ASK', plan: 'PLAN' };
  const MODE_SLASH_COMMANDS = new Set(['/agent', '/ask', '/plan', '/coordinator']);
  const MODE_SWITCH_GUIDANCE = '모드 전환은 입력창 아래 모드 선택을 사용하세요.';

  // ── State ─────────────────────────────────────────────────────────
  const initialState    = createInitialState(vscode);
  let savedHistory      = initialState.savedHistory;
  let savedPlan         = initialState.savedPlan;
  let currentMode       = initialState.currentMode;
  let currentSession    = initialState.currentSession;
  let sessions          = initialState.sessions;
  let toolStats         = initialState.toolStats;
  let activeRunnerMode = 'agent';

  let currentAssistantArticle = null;
  let currentAssistantEl      = null;
  let currentAssistantTxt     = '';
  let autocomplete            = null;
  let toolPanel               = null;
  let isGenerating            = false;
  let runnerState             = {
    running: false,
    processRunning: false,
    lifecycle: 'stopped',
    state: 'stopped',
    lastStatusAt: 0,
    pendingSubmitText: null,
    lastAttachRequestAt: 0,
    lastDiagnostic: null,
    sessionId: null,
    connectedSessionId: null,
    pythonExec: null,
    coreRoot: null,
    workspaceCwd: null,
    cwd: null,
    exitReason: null,
  };
  let inputHistory            = [];
  let inputHistoryIdx         = -1;
  const transientNotices      = new Map();
  let lastActiveSkillsKey     = '';

  // ── Persistence ───────────────────────────────────────────────────
  function persistState() {
    persistWebviewState(vscode, {
      savedHistory,
      savedPlan,
      currentMode,
      currentSession,
      sessions,
      toolStats,
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────

  function appendTransientMessage(role, text, tone, ttlMs = 2500) {
    const key = `${role}:${tone || ''}:${text || ''}`;
    const now = Date.now();
    if ((transientNotices.get(key) || 0) + ttlMs > now) return null;
    transientNotices.set(key, now);
    return _appendMessageEl(role, text, tone, false);
  }

  function activeSkillNames(event) {
    const skills = event?.metadata?.active_skills;
    if (!Array.isArray(skills)) return [];
    return skills.map(skill => {
      if (typeof skill === 'string') return skill;
      if (skill && typeof skill === 'object') return skill.name || skill.path || skill.description;
      return '';
    }).map(String).map(name => name.trim()).filter(Boolean);
  }

  function showActiveSkills(event) {
    const names = activeSkillNames(event);
    if (!names.length) return false;
    const key = names.join('|');
    if (key === lastActiveSkillsKey) return true;
    lastActiveSkillsKey = key;
    appendTransientMessage('system', `Active skills: ${names.join(', ')}`, 'info', 5000);
    return true;
  }

  function formatCompactProgress(event) {
    const phase = event.phase || 'compact_start';
    const labels = {
      hooks_start: 'preparing memory',
      context_collapse_start: 'compacting context',
      context_collapse_end: 'context compacted',
      session_memory_start: 'saving memory',
      session_memory_end: 'memory saved',
      compact_start: 'compacting memory',
      compact_retry: 'retrying compaction',
      compact_end: 'compaction complete',
      compact_failed: 'compaction failed',
    };
    const state = phase === 'compact_failed'
      ? 'error'
      : phase.endsWith('_end') || phase === 'compact_end'
        ? 'idle'
        : 'running';
    return { state, text: event.message || labels[phase] || phase };
  }

  function _maybeAddFold(article, body, text) {
    maybeAddFold(article, body, text, { messagesEl, threshold: FOLD_THRESHOLD });
  }

  function _appendMessageEl(role, text, tone, save = true) {
    const article = document.createElement('article');
    article.className = `message ${role}${tone ? ' ' + tone : ''}`;

    const labelRow = document.createElement('div');
    labelRow.className = 'label-row';

    const label = document.createElement('span');
    label.className = 'label';
    label.textContent = role;
    labelRow.appendChild(label);

    // 타임스탬프
    const ts = document.createElement('span');
    ts.className = 'timestamp';
    ts.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    labelRow.appendChild(ts);

    // assistant: 복사 버튼
    if (role === 'assistant') {
      const copyMsgBtn = document.createElement('button');
      copyMsgBtn.className = 'msg-action-btn copy-msg-btn';
      copyMsgBtn.title = '메시지 복사';
      copyMsgBtn.textContent = '⎘';
      copyMsgBtn.addEventListener('click', () => {
        const raw = article.querySelector('.body')?.textContent || '';
        navigator.clipboard.writeText(raw).then(() => {
          copyMsgBtn.textContent = '✓';
          setTimeout(() => { copyMsgBtn.textContent = '⎘'; }, 1500);
        }).catch(() => {});
      });
      labelRow.appendChild(copyMsgBtn);
    }

    // user: 재전송 버튼
    if (role === 'user') {
      const resendBtn = document.createElement('button');
      resendBtn.className = 'msg-action-btn resend-btn';
      resendBtn.title = '다시 전송';
      resendBtn.textContent = '↺';
      resendBtn.addEventListener('click', () => {
        if (!runnerState.running) return;
        promptEl.value = text || '';
        resizeTextarea();
        promptEl.focus();
      });
      labelRow.appendChild(resendBtn);
    }

    const body = document.createElement('div');
    body.className = 'body';
    if (role === 'assistant') {
      body.innerHTML = text ? renderMarkdown(text) : '';
    } else {
      body.textContent = text || '';
    }

    article.append(labelRow, body);

    if (text && role === 'assistant') {
      _maybeAddFold(article, body, text);
    }

    messagesEl.appendChild(article);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    if (shouldPersistMessage(role, text, save)) {
      savedHistory.push({ type: 'message', role, text, tone });
      persistState();
    }
    return { article, body };
  }

  function updateToolStats(name, success) {
    if (!name) return;
    const prev = toolStats[name] || { success: 0, failure: 0, lastRun: null };
    if (success) prev.success += 1;
    else prev.failure += 1;
    prev.lastRun = new Date().toISOString();
    toolStats[name] = prev;
    persistState();
  }

  function setLoopStatus(state, text) {
    renderLoopStatus(loopStatusEl, state, text);
  }

  function requestRunnerStatus() {
    vscode.postMessage({ type: 'getStatus' });
  }

  function requestRunnerAttach() {
    const now = Date.now();
    if (now - runnerState.lastAttachRequestAt < 1000) return false;
    runnerState.lastAttachRequestAt = now;
    vscode.postMessage({ type: 'attachSession' });
    return true;
  }

  function isRunnerStatusStale() {
    return !runnerState.lastStatusAt || Date.now() - runnerState.lastStatusAt > 3000;
  }

  function applyRunnerStatus(event) {
    runnerState = applyRunnerStatusEvent({
      event,
      runnerState,
      normalizeLifecycle: normalizeRunnerLifecycle,
      formatDiagnostic: formatRunnerDiagnostic,
      setLoopStatusText: setLoopStatus,
      updateSession,
      sendPromptText,
      appendTransientMessage,
      setGenerating,
      requestRunnerAttach,
      requestRunnerStatus,
    });
  }

  function _createTypingIndicator() {
    return createTypingIndicator(messagesEl);
  }

  function renderPlanPanel(plan) {
    renderPlanPanelComponent(plan, {
      panelEl: planPanelEl,
      canReview: !!(savedPlan && savedPlan.reviewState === 'wait'),
      onReview: action => vscode.postMessage({ type: 'reviewPlan', action }),
      onOpenMarkdown: planToOpen => vscode.postMessage({ type: 'openPlanPreview', plan: planToOpen }),
    });
  }

  function _clearChat() {
    messagesEl.innerHTML = '';
    toolPanel.clear();
    savedHistory = [];
    persistState();
  }

  function renderCustomTools(tools) {
    renderCustomToolsComponent(tools, {
      containerEl: customToolsEl,
      toolStats,
      onPermissionChange: (metadataPath, permissionLevel) => {
        vscode.postMessage({ type: 'updateToolPermission', metadataPath, permissionLevel });
      },
    });
  }

  toolPanel = createToolPanelController({
    containerEl: toolsEl,
    visibleLimit: TOOL_VISIBLE_LIMIT,
    longRunningMs: LONG_RUNNING_MS,
    onOpenDiff: event => vscode.postMessage({ type: 'openDiff', event }),
    onPersistTool: entry => {
      savedHistory.push(entry);
      persistState();
    },
    onStatsUpdate: updateToolStats,
    onOpenGeneratedTool: event => vscode.postMessage({ type: 'openGeneratedTool', event }),
    onRefreshCustomTools: () => vscode.postMessage({ type: 'getCustomTools' }),
  });

  // ── 기존 히스토리 복원 (helpers 모두 정의된 후 실행) ─────────────
  savedHistory = savedHistory.filter(m => !(m?.type === 'message' && m.role === 'system' && isTransientSystemText(m.text)));
  persistState();
  savedHistory.forEach(m => {
    try {
      if (m.type === 'message') _appendMessageEl(m.role, m.text, m.tone, false);
      else if (m.type === 'tool') toolPanel.appendTool(m.tool_name, m.tool_input, m.output, m.is_error, false);
    } catch (e) { /* 손상된 히스토리 항목 무시 */ }
  });
  renderPlanPanel(savedPlan);

  vscode.postMessage({ type: 'init' });
  vscode.postMessage({ type: 'getActiveFile' });
  vscode.postMessage({ type: 'getWorkspaceName' });
  vscode.postMessage({ type: 'getCustomTools' });
  requestRunnerStatus();

  document.addEventListener('visibilitychange', () => {
    vscode.postMessage({ type: 'visibilityChanged', visible: document.visibilityState === 'visible' });
    if (document.visibilityState === 'visible') {
      requestRunnerStatus();
      vscode.postMessage({ type: 'getActiveFile' });
    }
  });
  window.addEventListener('focus', requestRunnerStatus);

  // ── Code block copy (delegated) ───────────────────────────────────
  document.addEventListener('click', (e) => {
    if (!e.target.matches('.copy-btn')) return;
    const pre = document.getElementById(e.target.dataset.id);
    if (!pre) return;
    navigator.clipboard.writeText(pre.textContent).then(() => {
      const orig = e.target.textContent;
      e.target.textContent = 'Copied!';
      setTimeout(() => { e.target.textContent = orig; }, 1500);
    }).catch(() => {});
  });

  // ── Popup helpers ─────────────────────────────────────────────────
  function openPopup(el) {
    if (!el) return;
    el.hidden = false;
  }

  function closePopup(el) {
    if (!el) return;
    el.hidden = true;
  }

  function closeAllPopups() {
    closePopup(plusMenuEl);
    closePopup(modePopupEl);
    closePopup(sessionMenuEl);
  }

  document.addEventListener('mousedown', (e) => {
    if (!document.getElementById('plus-anchor')?.contains(e.target)) closePopup(plusMenuEl);
    if (!document.getElementById('mode-anchor')?.contains(e.target)) closePopup(modePopupEl);
    if (!document.getElementById('session-anchor')?.contains(e.target)) closePopup(sessionMenuEl);
  });

  // ── + 버튼 ───────────────────────────────────────────────────────
  plusBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (plusMenuEl && !plusMenuEl.hidden) { closePopup(plusMenuEl); return; }
    closePopup(modePopupEl);
    openPopup(plusMenuEl);
  });

  plusMenuEl?.addEventListener('click', (e) => {
    const li = e.target.closest('li[data-action]');
    if (!li) return;
    closePopup(plusMenuEl);
    const action = li.dataset.action;
    const pos = promptEl.selectionStart;
    const val = promptEl.value;
    if (action === 'at') {
      promptEl.value = val.slice(0, pos) + '@' + val.slice(pos);
      promptEl.selectionStart = promptEl.selectionEnd = pos + 1;
    } else if (action === 'slash') {
      promptEl.value = val.slice(0, pos) + '/' + val.slice(pos);
      promptEl.selectionStart = promptEl.selectionEnd = pos + 1;
    }
    promptEl.focus();
    promptEl.dispatchEvent(new Event('input'));
  });

  // ── 모드 팝업 ─────────────────────────────────────────────────────
  function applyMode(mode) {
    currentMode = mode;
    if (modeChipLabel) modeChipLabel.textContent = MODE_LABELS[mode] || mode.toUpperCase();
    document.querySelectorAll('.mode-option').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
    persistState();
  }

  applyMode(currentMode);

  modeChipBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (modePopupEl && !modePopupEl.hidden) { closePopup(modePopupEl); return; }
    closePopup(plusMenuEl);
    openPopup(modePopupEl);
  });

  document.querySelectorAll('.mode-option').forEach(btn => {
    btn.addEventListener('click', () => {
      applyMode(btn.dataset.mode);
      closePopup(modePopupEl);
      promptEl.focus();
    });
  });

  // ── Textarea auto-resize ──────────────────────────────────────────
  function resizeTextarea() {
    promptEl.style.height = 'auto';
    promptEl.style.height = Math.min(promptEl.scrollHeight, 160) + 'px';
  }

  autocomplete = createAutocompleteController({
    promptEl,
    listEl: acListEl,
    resizeTextarea,
    onMentionSearch: query => vscode.postMessage({ type: 'getFiles', query }),
  });

  // ── Keydown (Enter / history / autocomplete) ──────────────────────
  promptEl.addEventListener('keydown', (e) => {
    if (autocomplete.handleKeydown(e)) return;

    if (e.key === 'Escape') { closeAllPopups(); return; }

    if (e.key === 'ArrowUp' && !e.shiftKey && promptEl.selectionStart === 0) {
      if (inputHistory.length > 0 && inputHistoryIdx < inputHistory.length - 1) {
        inputHistoryIdx++;
        promptEl.value = inputHistory[inputHistoryIdx];
        promptEl.selectionStart = promptEl.selectionEnd = 0;
        resizeTextarea();
        e.preventDefault();
      }
      return;
    }
    if (e.key === 'ArrowDown' && !e.shiftKey && promptEl.selectionStart === promptEl.value.length) {
      if (inputHistoryIdx > 0) {
        inputHistoryIdx--;
        promptEl.value = inputHistory[inputHistoryIdx];
        resizeTextarea();
      } else if (inputHistoryIdx === 0) {
        inputHistoryIdx = -1;
        promptEl.value  = '';
        resizeTextarea();
      }
      e.preventDefault();
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitPrompt();
    }
  });

  // ── Autocomplete ──────────────────────────────────────────────────
  promptEl.addEventListener('input', () => autocomplete.handleInput());

  // ── Session label ─────────────────────────────────────────────────
  function updateSession(name) {
    currentSession = name || 'default';
    if (sessionEl) sessionEl.textContent = `${currentSession} ▾`;
    persistState();
    renderSessionMenu();
  }

  function renderSessionMenu() {
    renderSessionMenuComponent({
      menuEl: sessionMenuEl,
      sessions,
      currentSession,
      onClose: () => closePopup(sessionMenuEl),
      onSwitch: name => vscode.postMessage({ type: 'switchSession', name }),
      onNew: name => vscode.postMessage({ type: 'newSession', name }),
      onRename: (oldName, newName) => vscode.postMessage({ type: 'renameSession', oldName, newName }),
      onExport: (name, format) => vscode.postMessage({ type: 'exportSession', name, format }),
    });
  }

  sessionEl?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (sessionMenuEl && !sessionMenuEl.hidden) { closePopup(sessionMenuEl); return; }
    closeAllPopups();
    renderSessionMenu();
    openPopup(sessionMenuEl);
    vscode.postMessage({ type: 'getSessions' });
  });

  updateSession(currentSession);

  // ── Stop generation ───────────────────────────────────────────────
  stopGenBtn?.addEventListener('click', () => vscode.postMessage({ type: 'interruptSession' }));

  function setGenerating(v) {
    isGenerating = v;
    if (stopGenBtn) stopGenBtn.hidden = !v;
    if (v) {
      const { article, body } = _createTypingIndicator();
      currentAssistantArticle = article;
      currentAssistantEl      = body;
      currentAssistantTxt     = '';
    }
  }

  // ── Submit ────────────────────────────────────────────────────────
  function sendPromptText(text) {
    if (text !== inputHistory[0]) {
      inputHistory.unshift(text);
      if (inputHistory.length > 50) inputHistory.pop();
    }
    inputHistoryIdx = -1;

    _appendMessageEl('user', text);
    const isSlashCommand = text.startsWith('/');
    if (!isSlashCommand) setGenerating(true);

    if (!isSlashCommand && currentMode !== activeRunnerMode) {
      vscode.postMessage({ type: 'setMode', mode: currentMode });
      vscode.postMessage({ type: 'sendInput', text });
      activeRunnerMode = currentMode;
    } else {
      vscode.postMessage({ type: 'sendInput', text });
    }

    promptEl.value = '';
    promptEl.style.height = 'auto';
    autocomplete.close();
    closeAllPopups();
  }

  function submitPrompt() {
    const text = promptEl.value.trim();
    if (!text) return;

    const cmdLower = text.toLowerCase();
    const firstToken = cmdLower.split(/\s+/, 1)[0];

    // 로컬 전용 명령어 (runner 없이도 동작)
    if (cmdLower === '/clear') {
      _clearChat();
      promptEl.value = '';
      promptEl.style.height = 'auto';
      return;
    }
    if (cmdLower === '/quit' || cmdLower === '/exit') {
      vscode.postMessage({ type: 'stopSession' });
      promptEl.value = '';
      promptEl.style.height = 'auto';
      return;
    }
    if (MODE_SLASH_COMMANDS.has(firstToken)) {
      _appendMessageEl('system', MODE_SWITCH_GUIDANCE, 'hint');
      promptEl.value = '';
      promptEl.style.height = 'auto';
      autocomplete.close();
      closeAllPopups();
      return;
    }

    if (!runnerState.running) {
      if (isRunnerStatusStale()) {
        runnerState.pendingSubmitText = text;
        requestRunnerStatus();
        appendTransientMessage('system', '에이전트 연결 상태를 다시 확인 중입니다. 연결되어 있으면 자동으로 전송합니다.', 'hint');
        return;
      }

      if (runnerState.lifecycle === 'starting') {
        runnerState.pendingSubmitText = text;
        requestRunnerStatus();
        appendTransientMessage('system', '에이전트가 시작 중입니다. 연결되면 자동으로 전송합니다.', 'hint');
        return;
      }

      if (runnerState.processRunning) {
        runnerState.pendingSubmitText = text;
        requestRunnerAttach();
        requestRunnerStatus();
        appendTransientMessage(
          'system',
          '에이전트 프로세스에 다시 연결 중입니다. 연결되면 자동으로 전송합니다.',
          'hint',
        );
        return;
      }

      appendTransientMessage(
        'system',
        formatRunnerDiagnostic(runnerState, runnerState.lastDiagnostic) || '에이전트가 시작되지 않았습니다. ▶ Start 버튼을 눌러주세요.',
        'warn',
      );
      return;
    }

    sendPromptText(text);
  }

  // form submit은 항상 preventDefault (JS 크래시 시 폼 기본동작 방지)
  composerEl?.addEventListener('submit', (e) => { e.preventDefault(); submitPrompt(); });

  startBtn?.addEventListener('click', () => {
    if (runnerState.processRunning) {
      appendTransientMessage('system', '기존 에이전트 프로세스에 다시 연결합니다.', 'hint');
      requestRunnerAttach();
      requestRunnerStatus();
      return;
    }

    runnerState = {
      ...runnerState,
      running: false,
      processRunning: true,
      lifecycle: 'starting',
      state: 'starting',
      lastStatusAt: Date.now(),
      lastDiagnostic: null,
    };
    setLoopStatus('running', 'starting');
    vscode.postMessage({ type: 'launchSession' });
    requestRunnerStatus();
  });
  stopBtn?.addEventListener('click',  () => vscode.postMessage({ type: 'stopSession'  }));

  document.getElementById('clear-history')?.addEventListener('click', _clearChat);

  function insertMentionPath(path) {
    insertMentionPathInPrompt(promptEl, path, resizeTextarea);
  }

  bindImageAttachments({
    promptEl,
    resizeTextarea,
    onSaveImage: (name, data) => vscode.postMessage({ type: 'savePastedImage', name, data }),
    onInsertMention: insertMentionPath,
  });

  // ── Error retry ───────────────────────────────────────────────────
  function _appendRetryBanner() {
    appendRetryBanner(messagesEl, () => vscode.postMessage({ type: 'launchSession' }));
  }

  // ── Event handler ─────────────────────────────────────────────────
  window.addEventListener('message', ({ data }) => {
    data = normalizeHostMessage(data);
    if (!data) return;
    if (data?.type === 'sessionState') {
      data = { type: 'runnerEvent', event: data.state };
    } else if (data?.type === 'diagnostic') {
      data = { type: 'runnerEvent', event: data.diagnostic };
    } else if (data?.type === 'transientNotice') {
      _appendMessageEl('system', data.message || '', data.tone || 'info', false);
      return;
    } else if (data?.type === 'historySnapshot') {
      return;
    }

    const event = data.event;
    if (!event) return;

    switch (event.type) {

      case 'AssistantTextDelta':
        if (!currentAssistantEl) {
          const { article, body } = _createTypingIndicator();
          currentAssistantArticle = article;
          currentAssistantEl      = body;
          currentAssistantTxt     = '';
        }
        if (currentAssistantEl.querySelector('.typing-indicator')) {
          currentAssistantEl.innerHTML = '';
        }
        currentAssistantTxt += event.text || '';
        currentAssistantEl.innerHTML = renderMarkdown(currentAssistantTxt);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        break;

      case 'AssistantTurnComplete':
        if (currentAssistantTxt) {
          savedHistory.push({ type: 'message', role: 'assistant', text: currentAssistantTxt });
          persistState();
          if (currentAssistantArticle && currentAssistantEl) {
            _maybeAddFold(currentAssistantArticle, currentAssistantEl, currentAssistantTxt);
          }
        } else if (currentAssistantArticle) {
          currentAssistantArticle.remove();
        }
        currentAssistantArticle = null;
        currentAssistantEl      = null;
        currentAssistantTxt     = '';
        setGenerating(false);
        break;

      case 'AgentLoopStatus': {
        showActiveSkills(event);
        const status = formatAgentLoopStatus(event);
        setLoopStatus(status.state, status.text);
        break;
      }

      case 'CompactProgressEvent': {
        const status = formatCompactProgress(event);
        setLoopStatus(status.state, status.text);
        if (event.phase === 'compact_failed') {
          appendTransientMessage('system', status.text, 'warn', 5000);
        } else if (event.message || event.phase === 'compact_start' || event.phase === 'compact_end') {
          appendTransientMessage('system', status.text, 'info', 2500);
        }
        break;
      }

      case 'ToolExecutionStarted': {
        toolPanel.start(event);
        break;
      }

      case 'ToolExecutionCompleted': {
        showActiveSkills(event);
        toolPanel.complete(event);
        break;
      }

      case 'RunnerReady':
        activeRunnerMode = 'agent';
        applyRunnerStatus({ ...event, type: 'RunnerStatus', running: true, processRunning: true, lifecycle: 'ready', state: 'ready' });
        if (runnerState.connectedSessionId !== runnerState.sessionId) {
          runnerState.connectedSessionId = runnerState.sessionId;
          appendTransientMessage('system', `✅ Connected  model: ${event.model}\ncwd: ${event.cwd}`, 'info', 1000);
        }
        break;

      case 'RunnerStarting':
        applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: true, lifecycle: 'starting', state: 'starting' });
        break;

      case 'RunnerStatus':
        applyRunnerStatus(event);
        break;

      case 'RunnerDiagnostic':
        runnerState.lastDiagnostic = event;
        if (event.code === 'ready_timeout') {
          setLoopStatus('error', 'starting stale');
          appendTransientMessage('system', event.message || 'Runner startup is taking longer than expected.', 'warn');
        } else if (event.code !== 'user_stop') {
          appendTransientMessage('system', event.message || 'Runner diagnostic', 'warn');
        }
        break;

      case 'RunnerExited':
        applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'exited', state: 'exited' });
        appendTransientMessage('system', 'Runner stopped.', 'warn');
        break;

      case 'RunnerStopped':
        applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'stopped', state: 'stopped' });
        appendTransientMessage('system', 'Runner stopped gracefully.', 'warn');
        break;

      case 'RunnerError':
        runnerState.lastDiagnostic = event;
        applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'error', state: 'error', lastDiagnostic: event });
        appendTransientMessage('system', event.message || 'Unknown error', 'error');
        _appendRetryBanner();
        appendTransientMessage('system', '→ View > Output > "Theseus" for details', 'hint');
        break;

      case 'ErrorEvent':
        setGenerating(false);
        _appendMessageEl('system', event.message || 'Error', 'error');
        break;

      case 'StatusEvent':
        if (showActiveSkills(event) && /^Active skills:/i.test(event.message || '')) {
          setGenerating(false);
          break;
        }
        setGenerating(false);
        _appendMessageEl('system', event.message || '', 'info');
        break;

      case 'PermissionRequest':
        setLoopStatus('running', 'permission requested');
        appendTransientMessage(
          'system',
          `Permission requested${event.tool_name ? ` for ${event.tool_name}` : ''}: ${event.message || 'waiting for runner decision'}`,
          'warn',
          5000,
        );
        break;

      case 'filesResult':
        autocomplete.show((event.files || []).map(autocomplete.mentionValue));
        break;

      case 'PlanDraftedEvent':
        savedPlan = event.structured_plan || null;
        if (savedPlan) savedPlan.reviewState = 'wait';
        persistState();
        renderPlanPanel(savedPlan);
        _appendMessageEl('system', '📋 Plan drafted — review and approve to execute.', 'info');
        break;

      case 'PlanReviewEvent':
        if (savedPlan) {
          savedPlan.reviewState = event.action === 'approved' ? 'approved' : 'rejected';
          persistState();
          renderPlanPanel(savedPlan);
        }
        break;

      case 'SessionListEvent':
        sessions = Array.isArray(event.sessions) ? event.sessions : [];
        updateSession(event.current || currentSession);
        break;

      case 'SessionChangedEvent':
        updateSession(event.current || 'default');
        messagesEl.innerHTML = '';
        toolPanel.clear();
        savedHistory = Array.isArray(event.history) ? event.history : [];
        savedHistory.forEach(m => {
          if (m.type === 'message') _appendMessageEl(m.role, m.text, m.tone, false);
        });
        persistState();
        break;

      case 'SessionExportedEvent': {
        const preview = event.format === 'json'
          ? String(event.content || '').slice(0, 800)
          : String(event.content || '').slice(0, 1200);
        _appendMessageEl('system', `Exported ${event.name} (${event.format})\n\n${preview}`, 'info');
        break;
      }

      case 'workspaceInfo':
        if (workspaceLabelEl) {
          workspaceLabelEl.textContent = event.name || '';
          workspaceLabelEl.title       = event.path || '';
        }
        break;

      case 'activeFileChanged':
        if (activeFileEl) {
          const name = (event.file || '').split(/[/\\]/).pop();
          const line = Number.isInteger(event.line) ? `:${event.line}` : '';
          activeFileEl.textContent = name ? `📄 ${name}${line}` : '';
          activeFileEl.title       = event.file || '';
        }
        break;

      case 'customToolsLoaded':
        renderCustomTools(event.tools || []);
        break;

      case 'customToolsChanged': {
        const icons    = { created: '🔧➕', changed: '🔧✏️', deleted: '🔧🗑' };
        const icon     = icons[event.action] || '🔧';
        const fileName = (event.file || '').split(/[/\\]/).pop();
        const validation = event.validation;
        const msg = validation?.message ? ` — ${validation.message}` : '';
        _appendMessageEl('system', `${icon} Tool file ${event.action}: ${fileName}${msg}`, validation?.success === false ? 'warn' : 'info');
        vscode.postMessage({ type: 'getCustomTools' });
        break;
      }

      case 'customToolValidation':
        _appendMessageEl('system', event.message || '', event.success ? 'info' : 'warn');
        break;

      case 'assetSaved':
        insertMentionPath(event.path || '');
        _appendMessageEl('system', `Asset saved: ${event.path}`, 'info');
        break;

      case 'assetSaveFailed':
        _appendMessageEl('system', event.message || 'Failed to save asset', 'error');
        break;

      case 'settingsChanged':
        _appendMessageEl(
          'system',
          event.restartRequired
            ? 'Settings changed. Restart Theseus to apply them.'
            : 'Settings changed. They will apply on the next Start.',
          'warn',
        );
        break;

      case 'ClearChat':
        _clearChat();
        break;

      case 'injectText': {
        const injected = event.text || '';
        promptEl.value = injected + (promptEl.value ? '\n' + promptEl.value : '');
        resizeTextarea();
        promptEl.focus();
        promptEl.selectionStart = promptEl.selectionEnd = promptEl.value.length;
        break;
      }
    }
  });

}());
