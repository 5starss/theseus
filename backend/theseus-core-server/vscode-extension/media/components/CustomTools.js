export function renderCustomTools(tools, { containerEl, toolStats, onPermissionChange }) {
  if (!containerEl) return;
  containerEl.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'custom-tools-header';
  const title = document.createElement('strong');
  title.textContent = 'Custom Tools';
  const count = document.createElement('span');
  count.textContent = String(Array.isArray(tools) ? tools.length : 0);
  header.append(title, count);
  containerEl.appendChild(header);

  if (!Array.isArray(tools) || !tools.length) {
    const empty = document.createElement('div');
    empty.className = 'custom-tools-empty';
    empty.textContent = 'No custom tools';
    containerEl.appendChild(empty);
    return;
  }

  const list = document.createElement('div');
  list.className = 'custom-tools-list';
  tools.forEach(tool => {
    const item = document.createElement('div');
    item.className = `custom-tool-item ${tool.isActive ? 'active' : 'inactive'}`;
    item.title = tool.modulePath || tool.metadataPath || '';

    const name = document.createElement('span');
    name.className = 'custom-tool-name';
    name.textContent = tool.toolName || tool.fileName || 'unknown';

    const meta = document.createElement('span');
    meta.className = 'custom-tool-meta';
    const permission = tool.permissionLevel === '' || tool.permissionLevel == null
      ? '?'
      : String(tool.permissionLevel);
    const stats = toolStats[tool.toolName] || { success: 0, failure: 0, lastRun: null };
    const lastRun = stats.lastRun ? new Date(stats.lastRun).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'never';
    meta.textContent = `L${permission} · ${tool.status || 'unknown'} · ${stats.success}/${stats.failure} · ${lastRun}`;

    const permInput = document.createElement('input');
    permInput.className = 'custom-tool-permission';
    permInput.type = 'number';
    permInput.min = '1';
    permInput.max = '5';
    permInput.value = permission === '?' ? '' : permission;
    permInput.title = 'permissionLevel';
    permInput.addEventListener('change', () => {
      onPermissionChange(tool.metadataPath, Number(permInput.value));
    });

    const validation = tool.validationResult || {};
    const badge = document.createElement('span');
    badge.className = validation.success === false ? 'custom-tool-badge bad' : 'custom-tool-badge';
    badge.textContent = tool.isActive ? 'active' : 'inactive';

    item.append(name, meta, permInput, badge);
    list.appendChild(item);
  });
  containerEl.appendChild(list);
}
