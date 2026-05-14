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
  createTypingIndicator,
  isTransientSystemText,
  maybeAddFold,
  shouldPersistMessage,
} from './components/MessageList.js';
import { renderPlanPanel as renderPlanPanelComponent } from './components/PlanPanel.js';
import {
  applyRunnerStatusEvent,
  formatAgentLoopStatus,
  renderRunnerStatusBar,
  setLoopStatus as renderLoopStatus,
} from './components/RunnerStatus.js';
import { renderSessionMenu as renderSessionMenuComponent } from './components/SessionMenu.js';
import { createActivityLogController } from './components/ActivityLog.js';
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
  let customToolsCollapsed = initialState.customToolsCollapsed;
  let customToolsView   = initialState.customToolsView;
  let sessionListOpen   = initialState.sessionListOpen;
  let changeReviews     = initialState.changeReviews;
  let activeRunnerMode = 'agent';
  let latestHealth      = null;
  let healthPanelVisible = false;
  let activeFileContext = null;
  let suppressedActiveFile = '';
  let lastLoopStatus    = { state: 'idle', text: 'idle' };

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

  function setLoopStatus(state, text) {
    lastLoopStatus = { state: state || 'idle', text: text || 'idle' };
    renderLoopStatus(loopStatusEl, state, text);
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

  function classifyPlanReviewText(text) {
    const normalized = text.trim().replace(/^["'`]+|["'`]+$/g, '').toLowerCase()
      .replace(/[.!?。！？]+$/g, '')
      .replace(/\s+/g, ' ');
    const approvals = new Set([
      'approve', 'approved', 'accept', 'accepted', 'ok', 'okay', 'yes', 'y',
      'go', 'proceed', 'continue', 'looks good',
      '승인', '승인해', '승인해줘', '승인합니다', '허가', '허가해',
      '좋아', '좋습니다', '진행', '진행해', '진행해줘', '계속', '계속해',
    ]);
    const rejections = new Set([
      'reject', 'rejected', 'deny', 'denied', 'cancel', 'no', 'n',
      '거부', '반려', '취소', '중단', '안돼', '아니', '아니요',
    ]);
    if (approvals.has(normalized)) return 'approve';
    if (rejections.has(normalized)) return 'reject';
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
    persistState();
  }

  function renderCustomTools(tools) {
    customTools = Array.isArray(tools) ? tools : [];
    renderCustomToolsComponent(tools, {
      containerEl: customToolsEl,
      toolStats,
      collapsed: customToolsCollapsed,
      view: customToolsView,
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
      onPermissionChange: (metadataPath, permissionLevel) => {
        vscode.postMessage({ type: 'updateToolPermission', metadataPath, permissionLevel });
      },
    });
  }

  function clearPromptAfterCommand() {
    promptEl.value = '';
    promptEl.style.height = 'auto';
    autocomplete.close();
    closeAllPopups();
    renderContextBar();
  }

  function isAgentBusy() {
    return isGenerating;
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
      sessionEl.textContent = `${sessionDisplayName(currentSession)} ▾`;
      sessionEl.title = `Session: ${currentSession}`;
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

    const reviewAction = savedPlan?.reviewState === 'wait' ? classifyPlanReviewText(text) : null;
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
    const replayAll = savedHistory.length === 0;
    for (const event of events) {
      if (!event || typeof event !== 'object') continue;
      if (!replayAll && !statusOnly.has(event.type)) continue;
      window.dispatchEvent(new MessageEvent('message', {
        data: { type: 'runnerEvent', event: { ...event, replay: true } },
      }));
    }
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
      replayHistorySnapshot(data.history);
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
        toolPanel.note({
          key: 'request',
          label: 'answered',
          state: 'info',
        });
        runnerState = {
          ...runnerState,
          state: runnerState.running ? 'ready' : runnerState.state,
          lifecycle: runnerState.running ? 'ready' : runnerState.lifecycle,
        };
        currentAssistantArticle = null;
        currentAssistantEl      = null;
        currentAssistantTxt     = '';
        setGenerating(false);
        toolPanel.finishRequest();
        break;

      case 'AgentLoopStatus': {
        showActiveSkills(event);
        const status = formatAgentLoopStatus(event);
        setLoopStatus(status.state, status.text);
        if (status.state !== 'idle') {
          toolPanel.note({
            key: `loop:${event.tool_use_id || event.phase || 'status'}`,
            label: status.text,
            detail: event.message && event.message !== status.text ? event.message : '',
            state: status.state,
          });
        }
        break;
      }

      case 'CompactProgressEvent': {
        const status = formatCompactProgress(event);
        setLoopStatus(status.state, status.text);
        toolPanel.note({
          key: 'compact',
          label: status.text,
          detail: event.trigger ? `(${event.trigger})` : '',
          state: status.state === 'error' ? 'error' : 'info',
        });
        if (event.phase === 'compact_failed') {
          appendTransientMessage('system', status.text, 'warn', 5000);
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
        const reviewItem = createChangeReviewItem(event);
        if (reviewItem) {
          changeReviews = [reviewItem, ...changeReviews].slice(0, 20);
          persistState();
          renderChangeReviewPanel();
        }
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
        toolPanel.finishRequest();
        _appendMessageEl('system', event.message || 'Error', 'error');
        break;

      case 'StatusEvent':
        if (showActiveSkills(event) && /^Active skills:/i.test(event.message || '')) {
          setGenerating(false);
          break;
        }
        {
          const compactStatus = compactStatusFromMessage(event.message);
          if (compactStatus) {
            setLoopStatus(compactStatus.state, compactStatus.label);
            toolPanel.note({
              key: 'compact',
              label: compactStatus.label,
              detail: compactStatus.detail,
              state: compactStatus.state,
            });
            break;
          }
        }
        setGenerating(false);
        if (/PLAN 승인\/거부는 WAIT_FOR_REVIEW 상태에서만 가능합니다\./.test(event.message || '')) {
          clearSavedPlan();
          break;
        }
        if (/^(세션 목록|세션 전환|세션 삭제|세션 이름 변경|새 세션으로 전환):/.test(event.message || '')) {
          appendTransientMessage('system', event.message || '', 'hint', 4000);
          break;
        }
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
        if (savedPlan) {
          savedPlan.reviewState = 'wait';
          savedPlan.phase = 'wait';
        }
        setSavedPlan(savedPlan);
        _appendMessageEl('system', '📋 Plan drafted — review and approve to execute.', 'info');
        break;

      case 'PlanPhaseTransitionRequested':
        if (savedPlan) {
          const rawPhase = String(event.to_phase || '').trim();
          const normalizedPhase = rawPhase.toLowerCase();
          const nextState = normalizedPhase === 'completed'
            ? 'done'
            : normalizedPhase === 'waitforreview'
              ? 'wait'
              : normalizedPhase || 'review';
          savedPlan.reviewState = nextState;
          savedPlan.phase = rawPhase || nextState;
          setSavedPlan(savedPlan);
        }
        break;

      case 'PlanReviewEvent':
        if (['not_reviewable', 'closed', 'stale', 'cancelled', 'canceled', 'deleted'].includes(event.action)) {
          clearSavedPlan();
          break;
        }
        if (savedPlan) {
          const nextState = event.action === 'completed'
            ? 'done'
            : event.action === 'approved'
              ? 'executing'
              : event.action === 'rejected'
                ? 'drafting'
                : String(event.action || event.phase || 'review').toLowerCase();
          savedPlan.reviewState = nextState;
          savedPlan.phase = event.phase || nextState;
          if (Number.isInteger(event.totalTasks)) savedPlan.totalTasks = event.totalTasks;
          if (Number.isInteger(event.completedTasks)) savedPlan.completedTasks = event.completedTasks;
          if (Number.isInteger(event.remainingTasks)) savedPlan.remainingTasks = event.remainingTasks;
          setSavedPlan(savedPlan);
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
        if (Object.prototype.hasOwnProperty.call(event, 'planState')) {
          setSavedPlan(planFromSessionState(event.planState));
        } else {
          savedPlan = planBySession[currentSession] || null;
          renderPlanPanel(savedPlan);
        }
        savedHistory = Array.isArray(event.history) ? event.history : [];
        savedHistory.forEach(m => {
          if (m.type === 'message') {
            const text = collapseDuplicatedHistoryText(m.text);
            const rendered = _appendMessageEl(m.role, text, m.tone, false);
            if (m.role === 'user') toolPanel.startRequest(text, rendered.article);
            if (m.role === 'assistant') toolPanel.attachAssistant(rendered.article);
          } else if (m.type === 'tool') {
            toolPanel.appendTool(m.tool_name, m.tool_input, m.output, m.is_error, false, m);
          }
        });
        persistState();
        renderContextBar();
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
        activeFileContext = event.file ? { file: event.file, line: event.line } : null;
        if (suppressedActiveFile && suppressedActiveFile !== event.file) suppressedActiveFile = '';
        renderContextBar();
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

      case 'healthStatus':
        latestHealth = event;
        healthPanelVisible = true;
        renderHealthPanel();
        break;

      case 'changeReviewUpdated':
        if (event.id) changeReviews = changeReviews.filter(item => item.id !== event.id);
        persistState();
        renderChangeReviewPanel();
        _appendMessageEl('system', event.message || 'Change review updated.', event.success === false ? 'warn' : 'info');
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
