function lastRunTime(toolStats, toolName) {
  const value = toolStats?.[toolName]?.lastRun;
  return value ? new Date(value).getTime() || 0 : 0;
}

function validationFailed(tool) {
  return tool?.validationResult?.success === false;
}

export function renderCustomTools(tools, {
  containerEl,
  toolStats,
  collapsed = false,
  view = {},
  onViewChange,
  onToggleCollapsed,
  onPermissionChange,
}) {
  if (!containerEl) return;
  containerEl.innerHTML = '';
  containerEl.classList.toggle('collapsed', collapsed);

  const search = String(view.search || '').toLowerCase();
  const filter = view.filter || 'all';
  const sort = view.sort || 'name';
  let visibleTools = Array.isArray(tools) ? [...tools] : [];
  visibleTools = visibleTools.filter(tool => {
    const name = String(tool.toolName || tool.fileName || '').toLowerCase();
    if (search && !name.includes(search)) return false;
    if (filter === 'active' && tool.isActive === false) return false;
    if (filter === 'inactive' && tool.isActive !== false) return false;
    if (filter === 'errors' && !validationFailed(tool)) return false;
    if (filter === 'recent' && !lastRunTime(toolStats, tool.toolName)) return false;
    return true;
  });
  visibleTools.sort((a, b) => {
    if (sort === 'permission') return Number(a.permissionLevel || 0) - Number(b.permissionLevel || 0) || String(a.toolName).localeCompare(String(b.toolName));
    if (sort === 'lastRun') return lastRunTime(toolStats, b.toolName) - lastRunTime(toolStats, a.toolName) || String(a.toolName).localeCompare(String(b.toolName));
    return String(a.toolName || a.fileName || '').localeCompare(String(b.toolName || b.fileName || ''));
  });

  const header = document.createElement('div');
  header.className = 'custom-tools-header';
  const titleGroup = document.createElement('div');
  titleGroup.className = 'custom-tools-title';
  const toggle = document.createElement('button');
  toggle.className = 'custom-tools-toggle';
  toggle.type = 'button';
  toggle.textContent = collapsed ? '▸' : '▾';
  toggle.title = collapsed ? 'Show custom tools' : 'Hide custom tools';
  toggle.setAttribute('aria-expanded', String(!collapsed));
  toggle.addEventListener('click', () => onToggleCollapsed?.(!collapsed));
  const title = document.createElement('strong');
  title.textContent = 'Custom Tools';
  const count = document.createElement('span');
  count.className = 'custom-tools-count';
  count.textContent = `${visibleTools.length}/${Array.isArray(tools) ? tools.length : 0}`;
  titleGroup.append(toggle, title);
  header.append(titleGroup, count);
  containerEl.appendChild(header);

  if (collapsed) return;

  const controls = document.createElement('div');
  controls.className = 'custom-tools-controls';
  const searchInput = document.createElement('input');
  searchInput.type = 'search';
  searchInput.placeholder = 'Search tools';
  searchInput.value = view.search || '';
  searchInput.addEventListener('input', () => onViewChange?.({ ...view, search: searchInput.value }));
  const filterSelect = document.createElement('select');
  [
    ['all', 'All'],
    ['active', 'Active'],
    ['inactive', 'Inactive'],
    ['errors', 'Errors'],
    ['recent', 'Recent'],
  ].forEach(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    option.selected = filter === value;
    filterSelect.appendChild(option);
  });
  filterSelect.addEventListener('change', () => onViewChange?.({ ...view, filter: filterSelect.value }));
  const sortSelect = document.createElement('select');
  [
    ['name', 'Name'],
    ['permission', 'Permission'],
    ['lastRun', 'Last run'],
  ].forEach(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    option.selected = sort === value;
    sortSelect.appendChild(option);
  });
  sortSelect.addEventListener('change', () => onViewChange?.({ ...view, sort: sortSelect.value }));
  controls.append(searchInput, filterSelect, sortSelect);
  containerEl.appendChild(controls);

  if (!Array.isArray(tools) || !tools.length || !visibleTools.length) {
    const empty = document.createElement('div');
    empty.className = 'custom-tools-empty';
    empty.textContent = Array.isArray(tools) && tools.length ? 'No matching custom tools' : 'No custom tools';
    containerEl.appendChild(empty);
    return;
  }

  const list = document.createElement('div');
  list.className = 'custom-tools-list';
  visibleTools.forEach(tool => {
    const item = document.createElement('details');
    item.className = `custom-tool-item ${tool.isActive ? 'active' : 'inactive'}`;
    item.title = tool.modulePath || tool.metadataPath || '';

    const summary = document.createElement('summary');
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
    permInput.disabled = !tool.metadataPath;
    permInput.addEventListener('change', () => {
      if (!tool.metadataPath) return;
      onPermissionChange(tool.metadataPath, Number(permInput.value));
    });

    const validation = tool.validationResult || {};
    const badge = document.createElement('span');
    badge.className = validation.success === false ? 'custom-tool-badge bad' : 'custom-tool-badge';
    badge.textContent = tool.isActive ? 'active' : 'inactive';

    summary.append(name, meta, permInput, badge);
    const details = document.createElement('div');
    details.className = 'custom-tool-details';
    details.textContent = [
      tool.modulePath ? `module: ${tool.modulePath}` : '',
      tool.metadataPath ? `metadata: ${tool.metadataPath}` : '',
      validation.message ? `validation: ${validation.message}` : '',
    ].filter(Boolean).join('\n');

    item.append(summary, details);
    list.appendChild(item);
  });
  containerEl.appendChild(list);
}
