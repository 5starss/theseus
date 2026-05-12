export function setLoopStatus(loopStatusEl, state, text) {
  if (!loopStatusEl) return;
  loopStatusEl.className = `loop-status ${state || 'idle'}`;
  loopStatusEl.textContent = text || 'idle';
  loopStatusEl.title = text || 'Agent loop status';
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
