export function renderSessionMenu({
  menuEl,
  sessions,
  currentSession,
  onClose,
  onSwitch,
  onNew,
  onRename,
  onExport,
}) {
  if (!menuEl) return;
  menuEl.innerHTML = '';
  const list = document.createElement('div');
  list.className = 'session-list';
  (sessions || []).forEach(session => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = session.name === currentSession ? 'session-item active' : 'session-item';
    btn.textContent = session.name;
    btn.addEventListener('click', () => {
      onClose();
      onSwitch(session.name);
    });
    list.appendChild(btn);
  });

  const actions = document.createElement('div');
  actions.className = 'session-actions';
  const addAction = (label, handler) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.addEventListener('click', handler);
    actions.appendChild(btn);
  };
  addAction('New', () => {
    const name = prompt('New session name (letters and numbers only)');
    if (name) onNew(name);
    onClose();
  });
  addAction('Rename', () => {
    const name = prompt('Rename session to', currentSession);
    if (name && name !== currentSession) onRename(currentSession, name);
    onClose();
  });
  addAction('Export MD', () => {
    onExport(currentSession, 'markdown');
    onClose();
  });
  addAction('Export JSON', () => {
    onExport(currentSession, 'json');
    onClose();
  });

  menuEl.append(list, actions);
}
