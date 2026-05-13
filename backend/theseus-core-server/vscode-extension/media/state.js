export function createInitialState(vscode) {
  const prevState = vscode.getState() || {};
  const currentSession = prevState.session || 'default';
  const planBySession = prevState.planBySession && typeof prevState.planBySession === 'object'
    ? prevState.planBySession
    : {};
  if (prevState.plan && !planBySession[currentSession]) {
    planBySession[currentSession] = prevState.plan;
  }
  return {
    savedHistory: Array.isArray(prevState.history) ? prevState.history : [],
    savedPlan: planBySession[currentSession] || null,
    planBySession,
    currentMode: prevState.mode || 'agent',
    currentSession,
    sessions: Array.isArray(prevState.sessions) ? prevState.sessions : [],
    toolStats: prevState.toolStats || {},
    customToolsCollapsed: Boolean(prevState.customToolsCollapsed),
    customToolsView: prevState.customToolsView || { search: '', filter: 'all', sort: 'name' },
    sessionListOpen: prevState.sessionListOpen !== false,
    changeReviews: Array.isArray(prevState.changeReviews) ? prevState.changeReviews : [],
  };
}

export function persistWebviewState(vscode, state) {
  vscode.setState({
    history: state.savedHistory,
    plan: state.savedPlan,
    planBySession: state.planBySession || {},
    mode: state.currentMode,
    session: state.currentSession,
    sessions: state.sessions,
    toolStats: state.toolStats,
    customToolsCollapsed: Boolean(state.customToolsCollapsed),
    customToolsView: state.customToolsView || { search: '', filter: 'all', sort: 'name' },
    sessionListOpen: state.sessionListOpen !== false,
    changeReviews: Array.isArray(state.changeReviews) ? state.changeReviews.slice(0, 20) : [],
  });
}
