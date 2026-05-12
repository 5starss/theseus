export function createInitialState(vscode) {
  const prevState = vscode.getState() || {};
  return {
    savedHistory: Array.isArray(prevState.history) ? prevState.history : [],
    savedPlan: prevState.plan || null,
    currentMode: prevState.mode || 'agent',
    currentSession: prevState.session || 'default',
    sessions: Array.isArray(prevState.sessions) ? prevState.sessions : [],
    toolStats: prevState.toolStats || {},
  };
}

export function persistWebviewState(vscode, state) {
  vscode.setState({
    history: state.savedHistory,
    plan: state.savedPlan,
    mode: state.currentMode,
    session: state.currentSession,
    sessions: state.sessions,
    toolStats: state.toolStats,
  });
}
