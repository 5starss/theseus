export function renderHealthPanel({
  panelEl,
  health,
  visible,
  onOpenSettings,
  onRestart,
  onShowLogs,
  onRefresh,
  onClose,
}) {
  if (!panelEl) return;
  panelEl.innerHTML = '';
  panelEl.hidden = !visible;
  if (!visible) return;

  const header = document.createElement('div');
  header.className = 'health-header';
  const title = document.createElement('strong');
  title.textContent = 'Setup & Health';
  const actions = document.createElement('div');
  actions.className = 'health-actions';

  const actionButtons = [
    ['Settings', onOpenSettings],
    ['Restart', onRestart],
    ['Logs', onShowLogs],
    ['Refresh', onRefresh],
    ['Close', onClose],
  ];
  actionButtons.forEach(([label, handler]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', handler);
    actions.appendChild(button);
  });
  header.append(title, actions);

  const checks = Array.isArray(health?.checks) ? health.checks : [];
  const list = document.createElement('div');
  list.className = 'health-checks';
  checks.forEach(check => {
    const row = document.createElement('div');
    row.className = `health-check ${check.status || 'unknown'}`;
    const label = document.createElement('span');
    label.className = 'health-check-label';
    label.textContent = check.label || 'Check';
    const detail = document.createElement('span');
    detail.className = 'health-check-detail';
    detail.textContent = check.detail || '';
    row.append(label, detail);
    list.appendChild(row);
  });

  const meta = document.createElement('div');
  meta.className = 'health-meta';
  const settings = health?.settings || {};
  const runner = health?.runner || {};
  const localDaemon = health?.localDaemon || {};
  const server = health?.server || {};
  const customTools = health?.customTools || {};
  const extension = settings.extension || {};
  meta.textContent = [
    extension.version ? `extension: ${extension.version}` : '',
    extension.builtAt ? `builtAt: ${extension.builtAt}` : '',
    extension.mediaBuiltAt ? `mediaBuiltAt: ${extension.mediaBuiltAt}` : '',
    extension.sourceMarker ? `sourceMarker: ${extension.sourceMarker}` : '',
    localDaemon.status ? `Local daemon: ${localDaemon.status}` : '',
    localDaemon.pid ? `daemon pid: ${localDaemon.pid}` : '',
    localDaemon.port ? `daemon port: ${localDaemon.port}` : '',
    localDaemon.session ? `session: ${localDaemon.session}` : '',
    localDaemon.workspace ? `daemon workspace: ${localDaemon.workspace}` : '',
    server.status ? `Server URL: ${server.status}` : '',
    server.url ? `serverUrl: ${server.url}` : 'serverUrl: standalone',
    server.detail ? `server detail: ${server.detail}` : '',
    Number.isFinite(customTools.availableCount) || Number.isFinite(customTools.unavailableCount)
      ? `Custom tools: ${customTools.availableCount || 0} available, ${customTools.unavailableCount || 0} unavailable${customTools.inactiveCount ? `, ${customTools.inactiveCount} inactive` : ''}`
      : '',
    customTools.source ? `custom tool source: ${customTools.source}` : '',
    settings.corePath ? `corePath: ${settings.corePath}` : 'corePath: not configured',
    settings.workspacePath ? `workspacePath: ${settings.workspacePath}` : '',
    settings.runnerPath ? `runnerPath: ${settings.runnerPath}` : '',
    Array.isArray(settings.customToolRoots) && settings.customToolRoots.length
      ? `customToolRoots: ${settings.customToolRoots.join(' | ')}`
      : '',
    settings.pythonPath ? `pythonPath: ${settings.pythonPath}` : '',
    runner.runtimeMode ? `runtime: ${runner.runtimeMode}` : '',
  ].filter(Boolean).join('\n');

  panelEl.append(header, list, meta);
}
