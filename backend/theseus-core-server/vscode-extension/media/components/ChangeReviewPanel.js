export function changedFileFromEvent(event) {
  const changed = event?.metadata?.changed_file;
  if (!changed || typeof changed !== 'object') return null;
  if (!changed.path || typeof changed.old_content !== 'string') return null;
  return changed;
}

export function createChangeReviewItem(event) {
  const changed = changedFileFromEvent(event);
  if (!changed || event?.is_error) return null;
  const path = String(changed.path);
  const timestamp = Date.now();
  return {
    id: `${timestamp}-${Math.random().toString(36).slice(2, 8)}`,
    path,
    relativePath: String(changed.relative_path || path.split(/[\\/]/).pop() || path),
    oldContent: String(changed.old_content),
    existedBefore: changed.existed_before !== false,
    toolName: String(event.tool_name || 'tool'),
    timestamp,
    event,
    status: 'pending',
  };
}

export function renderChangeReviewPanel({
  panelEl,
  items,
  onOpenDiff,
  onOpenFile,
  onRevert,
  onDismiss,
  onClear,
}) {
  if (!panelEl) return;
  panelEl.innerHTML = '';
  const pending = Array.isArray(items) ? items.filter(item => item.status !== 'dismissed') : [];
  panelEl.hidden = pending.length === 0;
  if (!pending.length) return;

  const header = document.createElement('div');
  header.className = 'change-review-header';
  const title = document.createElement('strong');
  title.textContent = `Changes to Review (${pending.length})`;
  const clear = document.createElement('button');
  clear.type = 'button';
  clear.textContent = 'Clear';
  clear.addEventListener('click', onClear);
  header.append(title, clear);

  const list = document.createElement('div');
  list.className = 'change-review-list';
  pending.forEach(item => {
    const row = document.createElement('div');
    row.className = `change-review-item ${item.status || 'pending'}`;
    const info = document.createElement('div');
    info.className = 'change-review-info';
    const name = document.createElement('strong');
    name.textContent = item.relativePath || item.path;
    const meta = document.createElement('span');
    meta.textContent = `${item.toolName || 'tool'} · ${new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    info.append(name, meta);

    const actions = document.createElement('div');
    actions.className = 'change-review-actions';
    const buttons = [
      ['Diff', () => onOpenDiff(item)],
      ['Open', () => onOpenFile(item)],
      ['Revert', () => onRevert(item)],
      ['Dismiss', () => onDismiss(item)],
    ];
    buttons.forEach(([label, handler]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', handler);
      actions.appendChild(button);
    });
    row.append(info, actions);
    list.appendChild(row);
  });

  panelEl.append(header, list);
}
