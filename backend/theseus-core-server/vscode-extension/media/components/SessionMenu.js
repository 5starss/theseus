export function renderSessionMenu({
  menuEl,
  sessions,
  currentSession,
  listOpen = true,
  onListToggle,
  onClose,
  onSwitch,
  onNew,
  onDelete,
  onRename,
  onExport,
}) {
  if (!menuEl) return;
  menuEl.innerHTML = '';
  const sessionNames = new Set((sessions || []).map(session => session.name));
  const createSessionName = () => {
    const pad = value => String(value).padStart(2, '0');
    const now = new Date();
    const base = [
      'session',
      now.getFullYear(),
      pad(now.getMonth() + 1),
      pad(now.getDate()),
      pad(now.getHours()),
      pad(now.getMinutes()),
      pad(now.getSeconds()),
      String(now.getMilliseconds()).padStart(3, '0'),
    ].join('');
    let candidate = base;
    let suffix = 2;
    while (sessionNames.has(candidate)) {
      candidate = `${base}${suffix}`;
      suffix += 1;
    }
    return candidate;
  };
  const sessionTitle = session => {
    const title = String(session.title || '').trim();
    return title || 'Untitled session';
  };

  const header = document.createElement('div');
  header.className = 'session-menu-header';
  const headerLabel = document.createElement('span');
  headerLabel.textContent = 'Current';
  const headerValue = document.createElement('strong');
  const current = (sessions || []).find(session => session.name === currentSession);
  headerValue.textContent = current ? sessionTitle(current) : currentSession || 'default';
  header.append(headerLabel, headerValue);

  const details = document.createElement('details');
  details.className = 'session-list-details';
  details.open = listOpen !== false;
  details.addEventListener('toggle', () => {
    onListToggle?.(details.open);
  });
  const summary = document.createElement('summary');
  summary.className = 'session-list-summary';
  const summaryLabel = document.createElement('span');
  summaryLabel.textContent = `Sessions ${(sessions || []).length}`;
  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'session-add';
  addBtn.textContent = '+';
  addBtn.title = 'Start a new untitled session';
  addBtn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    onNew(createSessionName());
    onClose();
  });
  summary.append(summaryLabel, addBtn);
  details.appendChild(summary);

  const list = document.createElement('div');
  list.className = 'session-list';
  (sessions || []).forEach(session => {
    const row = document.createElement('div');
    row.className = 'session-row';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = session.name === currentSession ? 'session-item active' : 'session-item';
    const title = document.createElement('span');
    title.className = 'session-item-title';
    title.textContent = sessionTitle(session);
    const meta = document.createElement('span');
    meta.className = 'session-item-meta';
    meta.textContent = session.name;
    btn.append(title, meta);
    btn.addEventListener('click', () => {
      onClose();
      onSwitch(session.name);
    });
    row.appendChild(btn);

    if (onDelete) {
      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'session-delete';
      deleteBtn.textContent = 'x';
      deleteBtn.title = `Delete ${session.name}`;
      deleteBtn.setAttribute('aria-label', `Delete ${session.name}`);
      deleteBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (!confirm(`Delete session "${session.name}"?`)) return;
        onDelete(session.name);
        onClose();
      });
      row.appendChild(deleteBtn);
    }
    list.appendChild(row);
  });
  details.appendChild(list);

  const actions = document.createElement('div');
  actions.className = 'session-actions';
  const addAction = (label, handler) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.addEventListener('click', handler);
    actions.appendChild(btn);
  };
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

  menuEl.append(header, details, actions);
}
