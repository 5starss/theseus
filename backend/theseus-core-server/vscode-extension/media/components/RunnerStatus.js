export function setLoopStatus(loopStatusEl, state, text) {
  if (!loopStatusEl) return;
  loopStatusEl.className = `loop-status ${state || 'idle'}`;
  loopStatusEl.textContent = text || 'idle';
  loopStatusEl.title = text || 'Agent loop status';
}

export function renderRunnerStatusBar({
  detailEl,
  actionsEl,
  runnerState,
  loopStatus,
  onStart,
  onStop,
  onReconnect,
  onRestart,
  onShowLogs,
  onRefreshTools,
  onToggleHealth,
}) {
  const lifecycle = runnerState?.lifecycle || runnerState?.state || 'stopped';
  const running = !!runnerState?.running;
  const processRunning = !!runnerState?.processRunning;
  const label = running
    ? (runnerState?.state === 'busy' ? 'Running' : 'Ready')
    : processRunning
      ? (lifecycle === 'stale' || lifecycle === 'starting_stale' ? 'Reconnecting' : 'Starting')
      : lifecycle === 'error'
        ? 'Error'
        : 'Stopped';
  const detail = [
    label,
    loopStatus?.text && loopStatus.text !== 'idle' ? loopStatus.text : '',
    runnerState?.runtimeMode || '',
    runnerState?.daemonPort ? `:${runnerState.daemonPort}` : '',
  ].filter(Boolean).join(' · ');

  if (detailEl) {
    detailEl.textContent = detail;
    detailEl.title = [
      detail,
      runnerState?.lastDiagnostic?.message ? `Last diagnostic: ${runnerState.lastDiagnostic.message}` : '',
      runnerState?.workspaceCwd ? `cwd: ${runnerState.workspaceCwd}` : '',
    ].filter(Boolean).join('\n');
    detailEl.className = `runner-status-detail ${label.toLowerCase()}`;
  }

  if (!actionsEl) return;
  actionsEl.innerHTML = '';
  const addButton = (labelText, title, handler, className = '') => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = labelText;
    button.title = title;
    if (className) button.className = className;
    button.addEventListener('click', handler);
    actionsEl.appendChild(button);
  };

  if (!processRunning && !running) {
    addButton('Start', 'Start agent', onStart, 'primary');
  } else if (running) {
    addButton('Stop', 'Stop agent', onStop);
  } else {
    addButton('Reconnect', 'Reconnect to running agent', onReconnect, 'primary');
    addButton('Restart', 'Restart agent', onRestart);
  }
  if (processRunning || lifecycle === 'error') addButton('Logs', 'Show Theseus logs', onShowLogs);
  addButton('Tools', 'Refresh custom tools', onRefreshTools);
  addButton('Health', 'Show setup and runner health', onToggleHealth);
}

export function formatAgentLoopStatus(event) {
  const phase = event.phase || 'idle';
  const turn = event.turn ? `T${event.turn}` : '';
  const toolName = event.tool_name || '';
  const count = Number.isInteger(event.tool_count) ? `${event.tool_count} tools` : '';
  const labels = {
    model_start: `${turn} thinking`,
    model_complete: count ? `${turn} planned ${count}` : `${turn} answered`,
    waiting: count ? `${turn} running ${count}` : `${turn} running tools`,
    tool_start: toolName ? `${turn} tool ${toolName}` : `${turn} tool running`,
    tool_complete: toolName ? `${turn} ${toolName} ${event.is_error ? 'failed' : 'done'}` : `${turn} tool done`,
    complete: 'idle',
    error: 'loop error',
  };
  const state = event.is_error || phase === 'error'
    ? 'error'
    : phase === 'complete'
      ? 'idle'
      : phase.startsWith('tool') || phase === 'waiting'
        ? 'tool'
        : 'running';
  return { state, text: labels[phase] || event.message || phase };
}

export function applyRunnerStatusEvent({
  event,
  runnerState,
  normalizeLifecycle,
  formatDiagnostic,
  setLoopStatusText,
  updateSession,
  sendPromptText,
  appendTransientMessage,
  setGenerating,
  requestRunnerAttach,
  requestRunnerStatus,
}) {
  const lifecycle = normalizeLifecycle(event);
  const previousSessionId = runnerState.sessionId;
  const nextState = {
    ...runnerState,
    running: !!event.running,
    processRunning: !!event.processRunning || !!event.running,
    lifecycle,
    state: event.state || lifecycle,
    lastStatusAt: Date.now(),
    lastDiagnostic: event.lastDiagnostic || runnerState.lastDiagnostic,
    sessionId: event.sessionId || runnerState.sessionId,
    pythonExec: event.pythonExec || runnerState.pythonExec,
    coreRoot: event.coreRoot || runnerState.coreRoot,
    workspaceCwd: event.workspaceCwd || runnerState.workspaceCwd,
    cwd: event.cwd || runnerState.cwd,
    exitReason: event.exitReason || runnerState.exitReason,
  };

  if (nextState.running) {
    setLoopStatusText('idle', 'idle');
    updateSession(event.session || nextState.session || 'default');
    if (nextState.pendingSubmitText) {
      const text = nextState.pendingSubmitText;
      nextState.pendingSubmitText = null;
      sendPromptText(text);
    }
    return nextState;
  }

  if (nextState.processRunning) {
    const stale = lifecycle === 'starting_stale' || lifecycle === 'stale';
    setLoopStatusText('running',
      stale ? 'reconnecting' : lifecycle === 'starting' ? 'starting' : 'connecting');
    if (stale && requestRunnerAttach()) requestRunnerStatus();
    return nextState;
  }

  if (nextState.pendingSubmitText) {
    nextState.pendingSubmitText = null;
    const diagnosticText = formatDiagnostic(event, nextState.lastDiagnostic);
    appendTransientMessage(
      'system',
      diagnosticText || '에이전트가 시작되지 않았습니다. ▶ Start 버튼을 눌러주세요.',
      'warn',
    );
  }
  setLoopStatusText('idle', lifecycle === 'error' ? 'runner error' : 'stopped');
  setGenerating(false);

  if (previousSessionId && previousSessionId !== nextState.sessionId) {
    nextState.connectedSessionId = null;
  }
  return nextState;
}
