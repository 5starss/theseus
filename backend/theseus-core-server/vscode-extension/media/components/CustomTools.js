function lastRunTime(toolStats, toolName) {
  const value = toolStats?.[toolName]?.lastRun;
  return value ? new Date(value).getTime() || 0 : 0;
}

function validationFailed(tool) {
  return tool?.validationResult?.success === false || tool?.loadState === 'unavailable';
}

function toolLoadLabel(tool) {
  if (tool?.loadState === 'unavailable') return 'unavailable';
  if (tool?.loadState === 'inactive' || tool?.isActive === false) return 'inactive';
  if (tool?.loadState === 'available') return 'available';
  return tool?.isActive ? 'active' : 'inactive';
}

function makeToolAction(label, title, onClick, disabled = false) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'custom-tool-action';
  button.textContent = label;
  button.title = title;
  button.disabled = disabled;
  button.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    if (!disabled) onClick?.();
  });
  return button;
}

export function renderCustomTools(tools, {
  containerEl,
  toolStats,
  collapsed = false,
  view = {},
  onViewChange,
  onToggleCollapsed,
  onPermissionChange,
  onInstallDependencies,
  onRetryLoad,
  onRegisterTool,
  onDisableTool,
  onOpenFile,
  // 엔진이 dynamic tool retrieval로 이번 턴에 노출한 tool 이름 집합 (옵션)
  activeToolNames = null,
}) {
  const activeSet = activeToolNames instanceof Set
    ? activeToolNames
    : Array.isArray(activeToolNames)
      ? new Set(activeToolNames)
      : null;
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
    if (filter === 'active' && tool.loadState !== 'available') return false;
    if (filter === 'inactive' && tool.loadState !== 'inactive' && tool.isActive !== false) return false;
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

  // 정적 등록 목록과 실제 턴별 활성 tool이 다를 수 있음을 명시
  const notice = document.createElement('div');
  notice.className = 'custom-tools-notice';
  if (activeSet && activeSet.size) {
    const registeredNames = new Set(
      visibleTools.map(t => t.toolName).filter(Boolean),
    );
    const matchedInPanel = [...activeSet].filter(name => registeredNames.has(name)).length;
    const externalActive = activeSet.size - matchedInPanel;
    const parts = [`이번 응답에 ${activeSet.size}개 활성화 · ✓ = 모델에 노출됨`];
    if (externalActive > 0) {
      // 정적 패널에 없지만 활성된 tool (core/built-in일 가능성)
      parts.push(`(이 패널 밖 ${externalActive}개 포함)`);
    }
    notice.textContent = parts.join(' ');
  } else {
    notice.textContent = '전체 등록 목록 (응답마다 모델에 노출되는 tool은 다를 수 있음)';
  }
  containerEl.appendChild(notice);

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
    const isInActiveTurn = activeSet ? activeSet.has(tool.toolName) : null;
    const loadState = tool.loadState || (tool.isActive ? 'available' : 'inactive');
    item.className = `custom-tool-item ${loadState === 'available' ? 'active' : 'inactive'} ${loadState}`;
    if (isInActiveTurn === true) item.classList.add('turn-active');
    if (isInActiveTurn === false) item.classList.add('turn-inactive');
    item.title = tool.modulePath || tool.metadataPath || '';

    const summary = document.createElement('summary');
    const name = document.createElement('span');
    name.className = 'custom-tool-name';
    // 동적 retrieval에서 활성된 tool은 ✓ 마커로 표시
    const turnMarker = isInActiveTurn === true ? '✓ ' : '';
    name.textContent = `${turnMarker}${tool.toolName || tool.fileName || 'unknown'}`;

    const meta = document.createElement('span');
    meta.className = 'custom-tool-meta';
    const permission = tool.permissionLevel === '' || tool.permissionLevel == null
      ? '?'
      : String(tool.permissionLevel);
    const stats = toolStats[tool.toolName] || { success: 0, failure: 0, lastRun: null };
    const lastRun = stats.lastRun ? new Date(stats.lastRun).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'never';
    meta.textContent = `L${permission} · ${toolLoadLabel(tool)} · ${stats.success}/${stats.failure} · ${lastRun}`;

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
      // 의미적 식별자(toolName)와 경로(metadataPath)를 함께 전달 →
      // 백엔드가 permission_provider를 도입하면 toolName 기반으로 처리하고,
      // 미도입 환경에서는 기존처럼 metadataPath fallback으로 동작
      onPermissionChange(tool.metadataPath, Number(permInput.value), {
        toolName: tool.toolName || tool.fileName || null,
      });
    });

    const validation = tool.validationResult || {};
    const badge = document.createElement('span');
    badge.className = validationFailed(tool) ? 'custom-tool-badge bad' : 'custom-tool-badge';
    badge.textContent = toolLoadLabel(tool);

    summary.append(name, meta, permInput, badge);
    const details = document.createElement('div');
    details.className = 'custom-tool-details';
    const detailLines = [
      tool.modulePath ? `module: ${tool.modulePath}` : '',
      tool.metadataPath ? `metadata: ${tool.metadataPath}` : '',
      Array.isArray(tool.dependencies) && tool.dependencies.length ? `dependencies: ${tool.dependencies.join(', ')}` : '',
      Array.isArray(tool.missingModules) && tool.missingModules.length ? `missing: ${tool.missingModules.join(', ')}` : '',
      Array.isArray(tool.installCandidates) && tool.installCandidates.length ? `install: ${tool.installCandidates.join(', ')}` : '',
      tool.importError ? `import: ${tool.importError}` : '',
      validation.message ? `validation: ${validation.message}` : '',
    ].filter(Boolean);
    const detailText = document.createElement('pre');
    detailText.textContent = detailLines.join('\n');
    details.appendChild(detailText);

    const actions = document.createElement('div');
    actions.className = 'custom-tool-actions';
    actions.append(
      makeToolAction('View Error', 'Show import or validation error', () => {
        item.open = true;
        detailText.classList.toggle('focused');
      }, !validationFailed(tool)),
      makeToolAction('Install Dependencies', 'Install approved missing Python packages', () => onInstallDependencies?.(tool), !tool.canInstall),
      makeToolAction('Retry Load', 'Retry custom tool import and registry refresh', () => onRetryLoad?.(tool)),
      makeToolAction('Register', 'Validate and refresh runtime registry', () => onRegisterTool?.(tool), tool.loadState !== 'available' || !tool.metadataPath),
      makeToolAction('Open File', 'Open the tool source file', () => onOpenFile?.(tool), !tool.modulePath && !tool.metadataPath),
      makeToolAction('Disable', 'Mark this custom tool inactive', () => onDisableTool?.(tool), !tool.metadataPath),
    );
    details.appendChild(actions);

    item.append(summary, details);
    list.appendChild(item);
  });
  containerEl.appendChild(list);
}
