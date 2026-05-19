import { createAutocompleteController } from './components/Autocomplete.js';
import {
  bindImageAttachments,
  insertMentionPath as insertMentionPathInPrompt,
} from './components/Composer.js';
import { renderCustomTools as renderCustomToolsComponent } from './components/CustomTools.js';
import {
  createChangeReviewItem,
  renderChangeReviewPanel as renderChangeReviewPanelComponent,
} from './components/ChangeReviewPanel.js';
import {
  parseMentionPills,
  removeMentionFromText,
  renderContextBar as renderContextBarComponent,
} from './components/ContextBar.js';
import { renderHealthPanel as renderHealthPanelComponent } from './components/HealthPanel.js';
import {
  appendRetryBanner,
  clearRetryBanners,
  clearTransientSystemMessages,
  createTypingIndicator,
  isTransientSystemText,
  maybeAddFold,
  shouldPersistMessage,
} from './components/MessageList.js';
import { planToInlineMarkdown, renderPlanPanel as renderPlanPanelComponent } from './components/PlanPanel.js';
import {
  applyRunnerStatusEvent,
  formatAgentLoopStatus,
  renderRunnerStatusBar,
  setLoopStatus as renderLoopStatus,
} from './components/RunnerStatus.js';
import { renderSessionMenu as renderSessionMenuComponent } from './components/SessionMenu.js';
import { createActivityLogController } from './components/ActivityLog.js';
import { createInitialState, persistWebviewState } from './state.js';
import { createEventDispatcher } from './dispatcher.js';

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
  const healthPanelEl    = document.getElementById('health-panel');
  const changeReviewEl   = document.getElementById('change-review-panel');
  const planPanelEl      = document.getElementById('plan-panel');
  const promptEl         = document.getElementById('prompt');
  const composerEl       = document.getElementById('composer');
  const acListEl         = document.getElementById('autocomplete-list');
  const contextBarEl     = document.getElementById('context-bar');
  const sessionEl        = document.getElementById('session-label');
  const sessionMenuEl    = document.getElementById('session-menu');
  const stopGenBtn       = document.getElementById('stop-gen');
  const loopStatusEl     = document.getElementById('loop-status');
  const runnerDetailEl   = document.getElementById('runner-status-detail');
  const runnerActionsEl  = document.getElementById('runner-actions');
  const activeFileEl     = document.getElementById('active-file-label');
  const workspaceLabelEl = document.getElementById('workspace-label');
  const modeChipLabel    = document.getElementById('mode-chip-label');
  const modePopupEl      = document.getElementById('mode-popup');
  const modeChipBtn      = document.getElementById('mode-chip');
  const plusBtn          = document.getElementById('plus-btn');
  const plusMenuEl       = document.getElementById('plus-menu');

  // ── 상수 (const는 선언 전 접근 불가 → 최상단에 위치) ─────────────
  const FOLD_THRESHOLD = 25;
  const LONG_RUNNING_MS = 30000;
  const MODE_LABELS    = { agent: 'AGENT', ask: 'ASK', plan: 'PLAN' };
  const LOOP_STALLED_MS = 30000;
  const MODE_SWITCH_GUIDANCE = '모드 전환은 입력창 아래 모드 선택을 사용하세요.';
  const SLASH_COMMANDS = [
    { value: '/tools', description: 'Custom Tools 패널 새로고침', kind: 'local' },
    { value: '/tools custom', description: 'Custom Tools 패널 새로고침', kind: 'local' },
    { value: '/session', description: '세션 목록 열기', kind: 'local' },
    { value: '/sessions', description: '세션 목록 열기', kind: 'local' },
    { value: '/session list', description: '세션 목록 새로고침', kind: 'local' },
    { value: '/session new', description: '새 세션 생성', kind: 'local' },
    { value: '/session delete', description: '세션 삭제', kind: 'local' },
    { value: '/clear', description: '현재 채팅 화면 지우기', kind: 'local' },
    { value: '/help', description: '사용 가능한 명령어 표시', kind: 'local' },
    { value: '/?', description: '사용 가능한 명령어 표시', kind: 'local' },
    { value: '/quit', description: 'runner 중지', kind: 'local' },
    { value: '/exit', description: 'runner 중지', kind: 'local' },
    { value: '/cost', description: 'runner token/cost 통계', kind: 'runner' },
    { value: '/stats', description: 'runner 세션 통계', kind: 'runner' },
    { value: '/validate', description: 'runner에서 커스텀 도구 검증', kind: 'runner' },
    { value: '/plan approve', description: '대기 중인 PLAN 승인', kind: 'planReview' },
    { value: '/plan reject', description: '대기 중인 PLAN 거부', kind: 'planReview' },
    { value: '/plan cancel', description: '현재 세션 PLAN 취소', kind: 'localPlan' },
    { value: '/plan clear', description: '현재 세션 PLAN 취소', kind: 'localPlan' },
    { value: '/plan delete', description: '현재 세션 PLAN 삭제', kind: 'localPlan' },
    { value: '/plan remove', description: '현재 세션 PLAN 삭제', kind: 'localPlan' },
    { value: '/agent', description: '모드 선택 UI 사용', kind: 'mode' },
    { value: '/ask', description: '모드 선택 UI 사용', kind: 'mode' },
    { value: '/plan', description: '모드 선택 UI 사용', kind: 'mode' },
    { value: '/coordinator', description: '모드 선택 UI 사용', kind: 'mode' },
  ];
  const LOCAL_HELP_TEXT = [
    '사용 가능한 명령어:',
    ...SLASH_COMMANDS
      .filter(command => command.kind !== 'mode')
      .map(command => `${command.value.padEnd(18, ' ')} - ${command.description}`),
    '/agent, /ask, /plan - 모드 선택 UI를 사용하세요',
  ].join('\n');

  // ── State ─────────────────────────────────────────────────────────
  const initialState    = createInitialState(vscode);
  let savedHistory      = initialState.savedHistory;
  let savedPlan         = initialState.savedPlan;
  let planBySession     = initialState.planBySession;
  let currentMode       = initialState.currentMode;
  let currentSession    = initialState.currentSession;
  let sessions          = initialState.sessions;
  let toolStats         = initialState.toolStats;
  let customTools       = [];
  let customToolsSource = 'host';
  let customToolsCollapsed = initialState.customToolsCollapsed;
  let customToolsView   = initialState.customToolsView;
  let sessionListOpen   = initialState.sessionListOpen;
  let changeReviews     = initialState.changeReviews;
  let activeRunnerMode = 'agent';
  let latestHealth      = null;
  let healthPanelVisible = false;
  let activeFileContext = null;
  let suppressedActiveFile = '';
  let lastLoopStatus    = { state: 'idle', text: 'Idle', lastEventAt: 0 };

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
    activeRunId: null,
    activeRunStatus: null,
    activeRun: null,
    stalledReason: null,
  };
  let inputHistory            = [];
  let inputHistoryIdx         = -1;
  const transientNotices      = new Map();
  let lastActiveSkillsKey     = '';
  // 엔진이 dynamic tool retrieval로 이번 턴 활성 tool을 알려줄 때 채워짐
  // (event.metadata.active_tools 또는 active_tool_names를 수용)
  let activeTurnTools         = null;

  // ── Persistence ───────────────────────────────────────────────────
  let persistStateTimeout = null;
  function persistState() {
    if (persistStateTimeout) clearTimeout(persistStateTimeout);
    persistStateTimeout = setTimeout(() => {
      persistStateTimeout = null;
      persistWebviewState(vscode, {
        savedHistory,
        savedPlan,
        planBySession,
        currentMode,
        currentSession,
        sessions,
        toolStats,
        customToolsCollapsed,
        customToolsView,
        sessionListOpen,
        changeReviews,
      });
    }, 500);
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

  function compactStatusFromMessage(message) {
    const text = String(message || '').trim();
    if (!text) return null;
    if (/Auto-compacting conversation memory/i.test(text)) {
      return { state: 'running', label: 'compacting memory', detail: text };
    }
    if (/Prompt too long; compacting and retrying/i.test(text)) {
      return { state: 'running', label: 'compacting and retrying', detail: text };
    }
    return null;
  }

  function collapseDuplicatedHistoryText(text) {
    const raw = String(text || '');
    const lines = raw.split(/\r?\n/);
    if (lines.length > 1 && lines.length % 2 === 0) {
      const midpoint = lines.length / 2;
      const first = lines.slice(0, midpoint).join('\n');
      const second = lines.slice(midpoint).join('\n');
      if (first === second) return first;
    }
    return raw;
  }

  function normalizeSlashCommand(text) {
    return String(text || '').trim().replace(/\s+/g, ' ').toLowerCase();
  }

  function findSlashCommand(text) {
    const normalized = normalizeSlashCommand(text);
    const commands = [...SLASH_COMMANDS].sort((a, b) => b.value.length - a.value.length);
    return commands.find(command => normalized === command.value || normalized.startsWith(`${command.value} `)) || null;
  }

  function slashCommandRemainder(text, commandValue) {
    return String(text || '').trim().slice(commandValue.length).trim();
  }

  function _maybeAddFold(article, body, text) {
    maybeAddFold(article, body, text, { messagesEl, threshold: FOLD_THRESHOLD });
  }

  function _appendMessageEl(role, text, tone, save = true) {
    const article = document.createElement('article');
    article.className = `message ${role}${tone ? ' ' + tone : ''}`;

    const labelRow = document.createElement('div');
    labelRow.className = 'label-row';

    const avatar = document.createElement('span');
    avatar.className = role === 'assistant'
      ? 'role-avatar assistant-avatar'
      : role === 'user'
        ? 'role-avatar user-avatar'
        : 'role-avatar system-avatar';
    avatar.textContent = role === 'assistant' ? '✦' : role === 'user' ? '●' : '⚙';
    labelRow.appendChild(avatar);

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

  function persistToolHistory(entry) {
    if (!entry || entry.type !== 'tool') return;
    let replaceAt = -1;
    for (let i = savedHistory.length - 1; i >= 0; i -= 1) {
      const item = savedHistory[i];
      if (!item || item.type !== 'tool') continue;
      if (entry.tool_use_id && item.tool_use_id === entry.tool_use_id) {
        replaceAt = i;
        break;
      }
      if (!entry.tool_use_id && item.status === 'running' && item.tool_name === entry.tool_name) {
        replaceAt = i;
        break;
      }
    }
    if (replaceAt >= 0) savedHistory[replaceAt] = { ...savedHistory[replaceAt], ...entry };
    else savedHistory.push(entry);
    persistState();
  }

  function formatElapsed(ms) {
    if (!Number.isFinite(ms) || ms < 0) return '';
    if (ms < 2000) return 'now';
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    return `${Math.floor(seconds / 60)}m ago`;
  }

  function renderLoopStatusDisplay() {
    const base = lastLoopStatus || { state: 'idle', text: 'Idle', lastEventAt: 0 };
    const active = runnerState.processRunning || runnerState.running || isGenerating;
    const lastEventAt = base.lastEventAt || runnerState.lastEventAt || runnerState.lastStatusAt || 0;
    const elapsed = lastEventAt ? Date.now() - lastEventAt : 0;
    if (active && base.state !== 'idle' && elapsed > LOOP_STALLED_MS) {
      const text = `Stalled · ${formatElapsed(elapsed)} since ${base.text || 'last activity'}`;
      renderLoopStatus(loopStatusEl, 'stalled', text);
      return;
    }
    const suffix = base.state !== 'idle' && lastEventAt ? ` · ${formatElapsed(elapsed)}` : '';
    renderLoopStatus(loopStatusEl, base.state, `${base.text || 'Idle'}${suffix}`);
  }

  function setLoopStatus(state, text, eventAt = Date.now()) {
    lastLoopStatus = { state: state || 'idle', text: text || 'Idle', lastEventAt: eventAt };
    renderLoopStatusDisplay();
    renderRunnerStatus();
  }

  function touchLoopActivity(state = 'running', text = lastLoopStatus.text || 'Working') {
    if (lastLoopStatus.state === 'idle' && state === 'running') {
      lastLoopStatus = { state, text, lastEventAt: Date.now() };
    } else {
      lastLoopStatus = { ...lastLoopStatus, lastEventAt: Date.now() };
    }
    renderLoopStatusDisplay();
    renderRunnerStatus();
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
    renderLoopStatusDisplay();
    renderRunnerStatus();
    renderHealthPanel();
  }

  function launchOrAttachRunner() {
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
    renderRunnerStatus();
    vscode.postMessage({ type: 'launchSession' });
    requestRunnerStatus();
  }

  function restartRunner() {
    vscode.postMessage({ type: 'stopSession' });
    setTimeout(() => vscode.postMessage({ type: 'launchSession' }), 350);
  }

  function renderRunnerStatus() {
    renderRunnerStatusBar({
      detailEl: runnerDetailEl,
      actionsEl: runnerActionsEl,
      runnerState,
      loopStatus: lastLoopStatus,
      onStart: launchOrAttachRunner,
      onStop: () => vscode.postMessage({ type: 'stopSession' }),
      onReconnect: () => {
        requestRunnerAttach();
        requestRunnerStatus();
      },
      onRestart: restartRunner,
      onShowLogs: () => vscode.postMessage({ type: 'showLogs' }),
      onRefreshTools: () => vscode.postMessage({ type: 'getCustomTools' }),
      onToggleHealth: () => {
        healthPanelVisible = !healthPanelVisible;
        if (healthPanelVisible) vscode.postMessage({ type: 'getHealth' });
        renderHealthPanel();
      },
    });
  }

  setInterval(() => {
    renderLoopStatusDisplay();
    renderRunnerStatus();
  }, 1000);

  function renderHealthPanel() {
    renderHealthPanelComponent({
      panelEl: healthPanelEl,
      health: latestHealth,
      visible: healthPanelVisible,
      onOpenSettings: () => vscode.postMessage({ type: 'openSettings' }),
      onRestart: restartRunner,
      onShowLogs: () => vscode.postMessage({ type: 'showLogs' }),
      onRefresh: () => vscode.postMessage({ type: 'getHealth' }),
      onClose: () => {
        healthPanelVisible = false;
        renderHealthPanel();
      },
    });
  }

  function _createTypingIndicator() {
    const rendered = createTypingIndicator(messagesEl);
    toolPanel?.attachAssistant(rendered.article);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return rendered;
  }

  function resetCurrentAssistantDraft({ removeEmpty = true } = {}) {
    if (markdownRenderRAF) {
      cancelAnimationFrame(markdownRenderRAF);
      markdownRenderRAF = null;
    }
    const bodyText = currentAssistantEl?.textContent?.trim() || '';
    const hasTypingIndicator = !!currentAssistantEl?.querySelector?.('.typing-indicator');
    if (removeEmpty && currentAssistantArticle && (!currentAssistantTxt.trim() || hasTypingIndicator) && !bodyText) {
      currentAssistantArticle.remove();
    }
    currentAssistantArticle = null;
    currentAssistantEl = null;
    currentAssistantTxt = '';
  }

  function settleLoopStatusAfterGeneration() {
    const busy = runnerState.state === 'busy'
      || runnerState.lifecycle === 'busy'
      || !!runnerState.activeRunId;
    if (busy) return;
    if (runnerState.running || runnerState.state === 'ready' || runnerState.lifecycle === 'ready') {
      setLoopStatus('idle', 'Idle');
    }
  }

  function renderPlanPanel(plan) {
    renderPlanPanelComponent(plan, {
      panelEl: planPanelEl,
      canReview: !!(savedPlan && savedPlan.reviewState === 'wait'),
      onReview: action => {
        if (action === 'approve') setGenerating(true);
        vscode.postMessage({ type: 'reviewPlan', action });
      },
      onOpenMarkdown: planToOpen => vscode.postMessage({ type: 'openPlanPreview', plan: planToOpen }),
      onCancel: () => cancelCurrentPlan('cancel'),
      onDelete: () => cancelCurrentPlan('delete'),
    });
    // 패널은 stepper + 액션만, plan의 가독성 좋은 MD는 메인 채팅 흐름 안에 별도 메시지로 노출
    renderPlanInChat(plan);
  }

  // 메인 채팅에 표시되는 plan MD 메시지 (단일 인스턴스, 변경 시 in-place 업데이트)
  let planChatArticleEl = null;
  let planChatIdentity = '';  // 마지막으로 렌더한 plan의 식별자 (startedAt/goal 기반)

  function planIdentity(plan) {
    if (!plan) return '';
    return String(plan.startedAt || '') + '|' + String(plan.goal || plan.title || plan.pendingTitle || '');
  }

  function removePlanChatArticle() {
    if (planChatArticleEl?.parentNode) planChatArticleEl.parentNode.removeChild(planChatArticleEl);
    planChatArticleEl = null;
    planChatIdentity = '';
  }

  function renderPlanInChat(plan) {
    if (!plan) {
      removePlanChatArticle();
      return;
    }
    const md = planToInlineMarkdown(plan);
    if (!md) {
      removePlanChatArticle();
      return;
    }

    // 기존 article이 DOM에서 분리되었으면(/clear 등) 다시 만들어 추가
    if (planChatArticleEl && !planChatArticleEl.isConnected) {
      planChatArticleEl = null;
      planChatIdentity = '';
    }

    // 새 plan(다른 startedAt/goal)이면 이전 article 제거 후 새 위치에 재생성 →
    // 사용자의 가장 최근 질문 아래에 plan이 보이도록 보장
    const identity = planIdentity(plan);
    if (planChatArticleEl && planChatIdentity && identity !== planChatIdentity) {
      removePlanChatArticle();
    }

    if (!planChatArticleEl) {
      const article = document.createElement('article');
      article.className = 'message system plan-chat-message';

      const labelRow = document.createElement('div');
      labelRow.className = 'label-row';

      const avatar = document.createElement('span');
      avatar.className = 'role-avatar system-avatar';
      avatar.textContent = '📋';
      const label = document.createElement('span');
      label.className = 'label';
      label.textContent = 'PLAN';
      labelRow.append(avatar, label);

      const body = document.createElement('div');
      body.className = 'body plan-chat-body';

      article.append(labelRow, body);

      // 현재 활성 .turn(가장 최근 사용자 메시지가 속한 턴) 안에 삽입 → 사용자 질문 직후 위치
      const activeTurn = messagesEl.querySelector('.turn:last-of-type');
      const lastUser = activeTurn?.querySelector('.message.user');
      if (activeTurn && lastUser) {
        // user 메시지 바로 다음에 plan article 삽입
        activeTurn.insertBefore(article, lastUser.nextSibling);
      } else {
        messagesEl.appendChild(article);
      }
      planChatArticleEl = article;
    }
    planChatIdentity = identity;

    const body = planChatArticleEl.querySelector('.plan-chat-body');
    if (body) {
      body.innerHTML = renderMarkdown(md);
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function normalizePlanPhase(phase) {
    const value = String(phase || '').trim().toLowerCase();
    if (['waitforreview', 'wait_for_review', 'review', 'wait'].includes(value)) return 'wait';
    if (['execute', 'executing', 'approved'].includes(value)) return 'executing';
    if (['verify', 'verifying'].includes(value)) return 'verifying';
    if (['done', 'complete', 'completed'].includes(value)) return 'done';
    if (['draft', 'drafting', 'rejected'].includes(value)) return 'drafting';
    if (['cancelled', 'canceled', 'deleted', 'closed', 'stale'].includes(value)) return '';
    return value || 'drafting';
  }

  function planFromSessionState(planState) {
    if (!planState || typeof planState !== 'object') return null;
    let plan = planState.structured_plan && typeof planState.structured_plan === 'object'
      ? planState.structured_plan
      : null;
    if (!plan && typeof planState.plan_json === 'string' && planState.plan_json.trim()) {
      try {
        const parsed = JSON.parse(planState.plan_json);
        if (parsed && typeof parsed === 'object') plan = parsed;
      } catch {
        plan = null;
      }
    }
    if (!plan) return null;
    const phase = normalizePlanPhase(planState.phase || plan.phase || plan.reviewState);
    if (!phase) return null;
    return {
      ...plan,
      phase,
      reviewState: phase,
      session: currentSession,
      completedTasks: planState.completedTasks ?? plan.completedTasks,
      totalTasks: planState.totalTasks ?? plan.totalTasks,
      remainingTasks: planState.remainingTasks ?? plan.remainingTasks,
      lastError: planState.last_error || planState.lastError || plan.lastError,
    };
  }

  function setSavedPlan(plan, { render = true } = {}) {
    savedPlan = plan || null;
    if (savedPlan) {
      savedPlan.session = currentSession;
      savedPlan.updatedAt = new Date().toISOString();
      planBySession[currentSession] = savedPlan;
    } else {
      delete planBySession[currentSession];
    }
    persistState();
    if (render) renderPlanPanel(savedPlan);
  }

  function clearSavedPlan() {
    setSavedPlan(null);
  }

  function cancelCurrentPlan(action) {
    clearSavedPlan();
    vscode.postMessage({ type: 'reviewPlan', action });
    appendTransientMessage('system', action === 'delete' ? 'PLAN을 삭제했습니다.' : 'PLAN을 취소했습니다.', 'hint');
  }

  function beginPlanDraft(text) {
    const currentState = normalizePlanPhase(savedPlan?.reviewState || savedPlan?.phase);
    if (['wait', 'executing', 'verifying'].includes(currentState)) return;
    // 새 plan을 시작하므로 이전 plan article(이전 턴에 위치)을 제거 →
    // 새 article은 현재 사용자 메시지/턴 직후에 생성되도록 함
    removePlanChatArticle();
    setSavedPlan({
      goal: text,
      phase: 'drafting',
      reviewState: 'drafting',
      pendingTitle: text,
      tasks: [],
      startedAt: new Date().toISOString(),
    });
  }

  function switchSavedPlanForSession(name) {
    currentSession = name || 'default';
    savedPlan = planBySession[currentSession] || null;
    renderPlanPanel(savedPlan);
  }

  /*
   * Plan review 의사 분류는 엔진/플랜 가드에 위임한다.
   * - 명시적 의사 표현은 PlanPanel의 [승인]/[거부] 버튼이나
   *   `/plan approve`, `/plan reject` 슬래시 명령으로 처리한다.
   * - 일반 텍스트는 분류 없이 그대로 엔진에 전달해 엔진이 해석하도록 한다.
   *   (익스텐션이 사용자 의도를 가로채지 않도록)
   */
  function classifyPlanReviewText(_text) {
    return null;
  }

  function submitPlanReviewText(text, action) {
    if (text !== inputHistory[0]) {
      inputHistory.unshift(text);
      if (inputHistory.length > 50) inputHistory.pop();
    }
    inputHistoryIdx = -1;
    const rendered = _appendMessageEl('user', text);
    toolPanel.startRequest(text, rendered.article);
    if (action === 'approve') setGenerating(true);
    vscode.postMessage({ type: 'reviewPlan', action });
    promptEl.value = '';
    promptEl.style.height = 'auto';
    autocomplete.close();
    closeAllPopups();
    renderContextBar();
  }

  function _clearChat() {
    messagesEl.innerHTML = '';
    toolPanel.clear();
    savedHistory = [];
    planChatArticleEl = null; // DOM이 비워졌으므로 다음 renderPlanInChat에서 재생성
    persistState();
    // 빈 상태가 되었으므로 welcome 화면 복원
    if (typeof ensureWelcomeState === 'function') ensureWelcomeState();
  }

  function isRunnerProcessLive() {
    return Boolean(
      runnerState.processRunning
      || runnerState.running
      || ['starting', 'ready', 'busy', 'waiting_input', 'stale'].includes(runnerState.lifecycle || runnerState.state),
    );
  }

  function renderCustomTools(tools, source = 'host') {
    const nextSource = source || 'host';
    if (nextSource === 'host' && isRunnerProcessLive() && customToolsSource === 'runner') {
      return;
    }
    customTools = Array.isArray(tools) ? tools : [];
    customToolsSource = nextSource;
    renderCustomToolsComponent(tools, {
      containerEl: customToolsEl,
      toolStats,
      collapsed: customToolsCollapsed,
      view: customToolsView,
      activeToolNames: activeTurnTools,
      onViewChange: view => {
        customToolsView = view;
        persistState();
        renderCustomTools(customTools);
      },
      onToggleCollapsed: collapsed => {
        customToolsCollapsed = collapsed;
        persistState();
        renderCustomTools(customTools);
      },
      onPermissionChange: (metadataPath, permissionLevel, opts = {}) => {
        vscode.postMessage({
          type: 'updateToolPermission',
          metadataPath,
          permissionLevel,
          // permission_provider 추상화를 위한 의미적 정보
          toolName: opts.toolName || null,
          session: currentSession,
        });
      },
      onInstallDependencies: tool => {
        vscode.postMessage({
          type: 'installCustomToolDependencies',
          metadataPath: tool?.metadataPath,
          modulePath: tool?.modulePath,
          toolName: tool?.toolName || null,
        });
      },
      onRetryLoad: tool => {
        vscode.postMessage({
          type: 'retryCustomToolLoad',
          metadataPath: tool?.metadataPath,
          modulePath: tool?.modulePath,
          toolName: tool?.toolName || null,
        });
      },
      onRegisterTool: tool => {
        vscode.postMessage({
          type: 'registerCustomTool',
          metadataPath: tool?.metadataPath,
          modulePath: tool?.modulePath,
          toolName: tool?.toolName || null,
        });
      },
      onDisableTool: tool => {
        vscode.postMessage({
          type: 'disableCustomTool',
          metadataPath: tool?.metadataPath,
          modulePath: tool?.modulePath,
          toolName: tool?.toolName || null,
        });
      },
      onOpenFile: tool => {
        vscode.postMessage({ type: 'openFile', path: tool?.modulePath || tool?.metadataPath });
      },
    });
  }

  // 엔진 이벤트에서 active tool 정보를 추출 (여러 후보 키 수용)
  function extractActiveTools(event) {
    const meta = event?.metadata;
    if (!meta || typeof meta !== 'object') return null;
    const candidates = meta.active_tools || meta.active_tool_names || meta.retrieved_tools;
    if (!candidates) return null;
    const arr = Array.isArray(candidates) ? candidates : [];
    const names = arr
      .map(item => (typeof item === 'string' ? item : item?.name || item?.tool_name))
      .map(String)
      .map(s => s.trim())
      .filter(Boolean);
    return names.length ? new Set(names) : null;
  }

  function maybeUpdateActiveTurnTools(event) {
    const next = extractActiveTools(event);
    if (!next) return false;
    activeTurnTools = next;
    renderCustomTools(customTools);
    return true;
  }

  function clearPromptAfterCommand() {
    promptEl.value = '';
    promptEl.style.height = 'auto';
    autocomplete.close();
    closeAllPopups();
    renderContextBar();
  }

  function isAgentBusy() {
    const state = runnerState.state || '';
    const lifecycle = runnerState.lifecycle || '';
    return Boolean(
      isGenerating
      || state === 'busy'
      || lifecycle === 'busy'
      || runnerState.activeRunId
    );
  }

  function showRunnerRequired(command) {
    appendTransientMessage(
      'system',
      `${command} 명령은 실행 중인 runner가 필요합니다. Start 또는 Reconnect 후 다시 전송하세요.`,
      'warn',
      4000,
    );
  }

  function showRunnerBusy(command) {
    appendTransientMessage(
      'system',
      `${command} 명령은 현재 응답이 끝난 뒤 사용할 수 있습니다. 중단하려면 Stop 버튼을 사용하세요.`,
      'hint',
      4000,
    );
  }

  function ensureRunnerCommandReady(command) {
    if (!runnerState.running) {
      if (isRunnerStatusStale()) requestRunnerStatus();
      if (runnerState.processRunning) requestRunnerAttach();
      showRunnerRequired(command);
      return false;
    }
    if (isAgentBusy()) {
      showRunnerBusy(command);
      return false;
    }
    return true;
  }

  function renderContextBar() {
    renderContextBarComponent({
      containerEl: contextBarEl,
      session: currentSession,
      activeFile: activeFileContext,
      activeFileSuppressed: !!(activeFileContext?.file && activeFileContext.file === suppressedActiveFile),
      promptText: promptEl.value,
      onRemoveActiveFile: () => {
        suppressedActiveFile = activeFileContext?.file || '';
        renderContextBar();
      },
      onRemoveMention: value => {
        promptEl.value = removeMentionFromText(promptEl.value, value);
        resizeTextarea();
        renderContextBar();
      },
    });
  }

  function renderChangeReviewPanel() {
    renderChangeReviewPanelComponent({
      panelEl: changeReviewEl,
      items: changeReviews,
      onOpenDiff: item => vscode.postMessage({ type: 'openDiff', event: item.event }),
      onOpenFile: item => vscode.postMessage({ type: 'openFile', path: item.path }),
      onRevert: item => vscode.postMessage({
        type: 'revertChangedFile',
        id: item.id,
        path: item.path,
        oldContent: item.oldContent,
      }),
      onDismiss: item => {
        changeReviews = changeReviews.filter(entry => entry.id !== item.id);
        persistState();
        renderChangeReviewPanel();
      },
      onClear: () => {
        changeReviews = [];
        persistState();
        renderChangeReviewPanel();
      },
    });
  }

  if (toolsEl) toolsEl.hidden = true;
  toolPanel = createActivityLogController({
    messagesEl,
    longRunningMs: LONG_RUNNING_MS,
    onOpenDiff: event => vscode.postMessage({ type: 'openDiff', event }),
    onPersistTool: persistToolHistory,
    onStatsUpdate: updateToolStats,
    onOpenGeneratedTool: event => vscode.postMessage({ type: 'openGeneratedTool', event }),
    onRefreshCustomTools: () => vscode.postMessage({ type: 'getCustomTools' }),
  });

  // ── 기존 히스토리 복원 (helpers 모두 정의된 후 실행) ─────────────
  savedHistory = savedHistory.filter(m => !(m?.type === 'message' && m.role === 'system' && isTransientSystemText(m.text)));
  persistState();
  savedHistory.forEach(m => {
    try {
      if (m.type === 'message') {
        const text = collapseDuplicatedHistoryText(m.text);
        const rendered = _appendMessageEl(m.role, text, m.tone, false);
        if (m.role === 'user') toolPanel.startRequest(text, rendered.article);
        if (m.role === 'assistant') toolPanel.attachAssistant(rendered.article);
      }
      else if (m.type === 'tool') toolPanel.appendTool(m.tool_name, m.tool_input, m.output, m.is_error, false, m);
    } catch (e) { /* 손상된 히스토리 항목 무시 */ }
  });
  renderPlanPanel(savedPlan);
  renderRunnerStatus();
  renderContextBar();
  renderChangeReviewPanel();

  // ── Empty state (welcome screen) ─────────────────────────────────
  function ensureWelcomeState() {
    if (!messagesEl) return;
    if (messagesEl.querySelector('#empty-state')) return;          // 이미 있음
    if (messagesEl.querySelectorAll('.message').length > 0) return; // 대화 중

    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';
    emptyState.id = 'empty-state';
    emptyState.innerHTML = `
      <div class="empty-state-icon">✦</div>
      <div class="empty-state-title">Theseus Agent</div>
      <div class="empty-state-desc">무엇이든 물어보세요. 코드 분석, 리팩토링, 디버깅을 도와드립니다.</div>
      <div class="empty-state-prompts">
        <button class="empty-state-prompt" data-prompt="이 프로젝트의 구조를 분석해줘">📂 프로젝트 구조 분석</button>
        <button class="empty-state-prompt" data-prompt="@problems 현재 에러를 해결해줘">🔧 현재 에러 해결</button>
        <button class="empty-state-prompt" data-prompt="이 코드를 리팩토링해줘">✨ 코드 리팩토링</button>
      </div>
    `;
    messagesEl.appendChild(emptyState);
    emptyState.querySelectorAll('.empty-state-prompt').forEach(btn => {
      btn.addEventListener('click', () => {
        if (promptEl) {
          promptEl.value = btn.dataset.prompt || '';
          promptEl.focus();
        }
        emptyState.remove();
      });
    });
  }
  ensureWelcomeState();

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

  document.addEventListener('click', (e) => {
    const link = e.target.closest?.('.external-link[data-external-url]');
    if (!link) return;
    const url = link.getAttribute('data-external-url') || link.getAttribute('href') || '';
    if (!url) return;
    e.preventDefault();
    vscode.postMessage({ type: 'openExternal', url });
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
  function applyMode(mode, { fromUserGesture = false } = {}) {
    const prevMode = currentMode;
    currentMode = mode;
    if (modeChipLabel) modeChipLabel.textContent = MODE_LABELS[mode] || mode.toUpperCase();
    if (modeChipBtn) modeChipBtn.dataset.mode = mode;
    document.querySelectorAll('.mode-option').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === mode);
    });

    // plan → 다른 모드 전환 시 PLAN 상태별 처리
    if (fromUserGesture && prevMode === 'plan' && mode !== 'plan') {
      const planState = normalizePlanPhase(savedPlan?.reviewState || savedPlan?.phase);
      if (planState === 'wait' || planState === 'drafting') {
        // 검토 대기 / 작성 중 단계만 자동 취소 (실행 단계 cancel은 race 위험)
        cancelCurrentPlan('cancel');
        appendTransientMessage(
          'system',
          `${MODE_LABELS[mode] || mode} 모드로 전환했습니다. 검토 대기 중이던 PLAN을 취소했습니다.`,
          'hint',
          3500,
        );
      } else if (planState === 'executing' || planState === 'verifying') {
        // 실행 중인 plan은 자동 취소 위험 → 사용자에게 안내만, plan은 그대로 유지
        appendTransientMessage(
          'system',
          `${MODE_LABELS[mode] || mode} 모드로 전환했습니다. 실행 중인 PLAN은 그대로 유지됩니다. 중지하려면 PLAN 패널의 [Cancel]을 사용하세요.`,
          'warn',
          5000,
        );
      }
    }

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
      applyMode(btn.dataset.mode, { fromUserGesture: true });
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
  promptEl.addEventListener('input', () => {
    autocomplete.handleInput();
    renderContextBar();
  });

  // ── Session label ─────────────────────────────────────────────────
  function sessionDisplayName(name) {
    const session = sessions.find(item => item.name === name);
    const title = typeof session?.title === 'string' ? session.title.trim() : '';
    return title || name || 'default';
  }

  function updateSession(name) {
    if (savedPlan) planBySession[currentSession] = savedPlan;
    switchSavedPlanForSession(name || 'default');
    if (sessionEl) {
      // 버튼 텍스트는 항상 "▾" 고정, 세션명은 tooltip으로만 표시
      sessionEl.textContent = '▾';
      sessionEl.title = `세션: ${sessionDisplayName(currentSession)}`;
    }
    persistState();
    renderSessionMenu();
  }

  function renderSessionMenu() {
    renderSessionMenuComponent({
      menuEl: sessionMenuEl,
      sessions,
      currentSession,
      listOpen: sessionListOpen,
      onListToggle: open => {
        sessionListOpen = open;
        persistState();
      },
      onClose: () => closePopup(sessionMenuEl),
      onSwitch: name => vscode.postMessage({ type: 'switchSession', name }),
      onNew: name => vscode.postMessage({ type: 'newSession', name }),
      onDelete: name => vscode.postMessage({ type: 'deleteSession', name }),
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
    if (v && isGenerating && currentAssistantEl) {
      renderRunnerStatus();
      return;
    }
    isGenerating = v;
    if (stopGenBtn) stopGenBtn.hidden = !v;
    if (v) {
      const { article, body } = _createTypingIndicator();
      currentAssistantArticle = article;
      currentAssistantEl      = body;
      currentAssistantTxt     = '';
    } else {
      resetCurrentAssistantDraft();
      settleLoopStatusAfterGeneration();
    }
    renderRunnerStatus();
  }

  // ── Submit ────────────────────────────────────────────────────────
  function sendPromptText(text) {
    if (text !== inputHistory[0]) {
      inputHistory.unshift(text);
      if (inputHistory.length > 50) inputHistory.pop();
    }
    inputHistoryIdx = -1;

    // 새 턴 시작 → 이전 턴의 active tool 표시를 초기화
    if (activeTurnTools) {
      activeTurnTools = null;
      renderCustomTools(customTools);
    }

    // Remove welcome screen if present
    const emptyEl = document.getElementById('empty-state');
    if (emptyEl) emptyEl.remove();

    const rendered = _appendMessageEl('user', text);
    toolPanel.startRequest(text, rendered.article);
    const isSlashCommand = text.startsWith('/');
    if (!isSlashCommand) {
      toolPanel.note({
        key: 'request',
        label: 'thinking',
        detail: currentMode === 'plan' ? 'plan mode' : '',
        state: 'running',
      });
      setGenerating(true);
    }
    if (!isSlashCommand && currentMode === 'plan') beginPlanDraft(text);

    const skipCursorContext = isSlashCommand || !!(activeFileContext?.file && activeFileContext.file === suppressedActiveFile);
    if (!isSlashCommand) {
      vscode.postMessage({ type: 'sendWithMode', mode: currentMode, text, skipCursorContext });
      activeRunnerMode = currentMode;
    } else {
      vscode.postMessage({ type: 'sendInput', text, skipCursorContext });
    }

    promptEl.value = '';
    promptEl.style.height = 'auto';
    autocomplete.close();
    closeAllPopups();
    renderContextBar();
  }

  function submitPrompt() {
    const text = promptEl.value.trim();
    if (!text) return;

    if (text.startsWith('/') && handleSlashCommand(text)) return;

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

    if (isAgentBusy()) {
      appendTransientMessage(
        'system',
        '현재 응답이 진행 중입니다. 완료 후 다시 전송하세요. 입력 내용은 유지됩니다.',
        'hint',
        4000,
      );
      return;
    }

    // plan review는 plan 모드일 때만 트리거 (다른 모드에서 plan 잔여 상태가 남아도 무시)
    const reviewAction = (currentMode === 'plan' && savedPlan?.reviewState === 'wait')
      ? classifyPlanReviewText(text)
      : null;
    if (reviewAction) {
      submitPlanReviewText(text, reviewAction);
      return;
    }

    sendPromptText(text);
  }

  function handleSlashCommand(text) {
    const command = findSlashCommand(text);
    const normalized = normalizeSlashCommand(text);
    if (!command) {
      appendTransientMessage('system', `지원하지 않는 명령어입니다: ${normalized}\n/help로 사용 가능한 명령어를 확인하세요.`, 'warn', 5000);
      return true;
    }

    if (command.kind === 'mode') {
      _appendMessageEl('system', MODE_SWITCH_GUIDANCE, 'hint');
      clearPromptAfterCommand();
      return true;
    }

    if (normalized === '/clear') {
      _clearChat();
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/quit' || normalized === '/exit') {
      vscode.postMessage({ type: 'stopSession' });
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/help' || normalized === '/?') {
      _appendMessageEl('system', LOCAL_HELP_TEXT, 'info');
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/tools' || normalized === '/tools custom') {
      customToolsCollapsed = false;
      persistState();
      renderCustomTools(customTools);
      vscode.postMessage({ type: 'getCustomTools' });
      _appendMessageEl('system', 'Custom Tools 패널을 새로고침했습니다.', 'info');
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/session' || normalized === '/sessions' || normalized === '/session list') {
      renderSessionMenu();
      openPopup(sessionMenuEl);
      vscode.postMessage({ type: 'getSessions' });
      clearPromptAfterCommand();
      return true;
    }
    if (normalized.startsWith('/session new')) {
      if (isAgentBusy()) {
        showRunnerBusy('/session new');
        return true;
      }
      vscode.postMessage({ type: 'newSession', name: slashCommandRemainder(text, '/session new') || undefined });
      clearPromptAfterCommand();
      return true;
    }
    if (normalized.startsWith('/session delete')) {
      const name = slashCommandRemainder(text, '/session delete');
      if (!name) {
        renderSessionMenu();
        openPopup(sessionMenuEl);
        vscode.postMessage({ type: 'getSessions' });
        appendTransientMessage('system', '삭제할 세션을 목록의 x 버튼으로 선택하세요.', 'hint', 4000);
      } else if (isAgentBusy()) {
        showRunnerBusy('/session delete');
      } else {
        vscode.postMessage({ type: 'deleteSession', name });
        clearPromptAfterCommand();
      }
      return true;
    }
    if (normalized === '/plan cancel' || normalized === '/plan clear') {
      cancelCurrentPlan('cancel');
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/plan delete' || normalized === '/plan remove') {
      cancelCurrentPlan('delete');
      clearPromptAfterCommand();
      return true;
    }
    if (normalized === '/plan approve' || normalized === '/plan reject') {
      const action = normalized.endsWith('approve') ? 'approve' : 'reject';
      if (savedPlan?.reviewState !== 'wait') {
        appendTransientMessage('system', '승인/거부 가능한 PLAN이 없습니다.', 'warn', 4000);
        clearPromptAfterCommand();
        return true;
      }
      submitPlanReviewText(text, action);
      return true;
    }

    if (command.kind === 'runner') {
      if (!ensureRunnerCommandReady(command.value)) return true;
      sendPromptText(text);
      return true;
    }

    return false;
  }

  // form submit은 항상 preventDefault (JS 크래시 시 폼 기본동작 방지)
  composerEl?.addEventListener('submit', (e) => { e.preventDefault(); submitPrompt(); });

  document.getElementById('clear-history')?.addEventListener('click', _clearChat);

  // 워크트리(작업 폴더) 빠른 선택 — host의 quickPick으로 위임
  document.getElementById('select-worktree')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'selectWorktree' });
  });

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
  function _clearRetryBanners() {
    clearRetryBanners(messagesEl);
  }
  function _clearTransientSystemMessages() {
    clearTransientSystemMessages(messagesEl);
  }

  function replayHistorySnapshot(events) {
    if (!Array.isArray(events) || !events.length) return;
    const statusOnly = new Set([
      'RunnerReady',
      'RunnerStarting',
      'RunnerStatus',
      'RunnerDiagnostic',
      'RunnerExited',
      'RunnerStopped',
      'RunnerError',
    ]);

    /*
     * 보수적 정책:
     * - 로컬 savedHistory가 비어 있으면(=cold start) 전체 재생
     * - 그렇지 않으면 상태 이벤트만 재생해 현재 표시된 대화 보호
     *
     * (이전 "snapshot authoritative" 정책은 visibility change 같은 정상 케이스에서도
     *  대화 내역을 wipe해서 UX를 망가뜨렸음. 동기화는 명시적 `clearHistory` 이벤트로만 처리)
     */
    const replayAll = savedHistory.length === 0;
    for (const event of events) {
      if (!event || typeof event !== 'object') continue;
      if (!replayAll && !statusOnly.has(event.type)) continue;
      window.dispatchEvent(new MessageEvent('message', {
        data: { type: 'runnerEvent', event: { ...event, replay: true } },
      }));
    }
  }

  const dispatcherCtx = {
    get currentAssistantEl() { return currentAssistantEl; },
    set currentAssistantEl(v) { currentAssistantEl = v; },
    get currentAssistantArticle() { return currentAssistantArticle; },
    set currentAssistantArticle(v) { currentAssistantArticle = v; },
    get currentAssistantTxt() { return currentAssistantTxt; },
    set currentAssistantTxt(v) { currentAssistantTxt = v; },
    get runnerState() { return runnerState; },
    set runnerState(v) { runnerState = v; },
    get changeReviews() { return changeReviews; },
    set changeReviews(v) { changeReviews = v; },
    get latestHealth() { return latestHealth; },
    set latestHealth(v) { latestHealth = v; },
    get healthPanelVisible() { return healthPanelVisible; },
    set healthPanelVisible(v) { healthPanelVisible = v; },
    get savedPlan() { return savedPlan; },
    set savedPlan(v) { savedPlan = v; },
    get sessions() { return sessions; },
    set sessions(v) { sessions = v; },
    get savedHistory() { return savedHistory; },
    set savedHistory(v) { savedHistory = v; },
    get activeFileContext() { return activeFileContext; },
    set activeFileContext(v) { activeFileContext = v; },
    get suppressedActiveFile() { return suppressedActiveFile; },
    set suppressedActiveFile(v) { suppressedActiveFile = v; },
    get activeRunnerMode() { return activeRunnerMode; },
    set activeRunnerMode(v) { activeRunnerMode = v; },
    get currentSession() { return currentSession; },
    get planBySession() { return planBySession; },

    createTypingIndicator: _createTypingIndicator,
    renderMarkdown,
    messagesEl,
    persistState,
    maybeAddFold: _maybeAddFold,
    toolPanel,
    setGenerating,
    showActiveSkills,
    formatAgentLoopStatus,
    setLoopStatus,
    touchLoopActivity,
    formatCompactProgress,
    appendTransientMessage,
    createChangeReviewItem,
    renderChangeReviewPanel,
    applyRunnerStatus,
    formatRunnerDiagnostic,
    appendRetryBanner: _appendRetryBanner,
    clearRetryBanners: _clearRetryBanners,
    clearTransientSystemMessages: _clearTransientSystemMessages,
    appendMessageEl: _appendMessageEl,
    compactStatusFromMessage,
    clearSavedPlan,
    updateSession,
    setSavedPlan,
    planFromSessionState,
    renderPlanPanel,
    collapseDuplicatedHistoryText,
    renderContextBar,
    workspaceLabelEl,
    activeFileEl,
    renderCustomTools,
    isRunnerProcessLive,
    vscode,
    renderHealthPanel,
    insertMentionPath,
    clearChat: _clearChat,
    promptEl,
    resizeTextarea,
    autocomplete
  };
  const eventDispatcher = createEventDispatcher(dispatcherCtx);

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
      replayHistorySnapshot(data.history);
      return;
    }

    const event = data.event;
    if (!event) return;

    // 엔진이 dynamic tool retrieval로 active tool 정보를 보내면 패널에 반영
    maybeUpdateActiveTurnTools(event);

    eventDispatcher(event);
  });

}());
