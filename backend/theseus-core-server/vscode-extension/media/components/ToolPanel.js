function keyForToolEvent(event) {
  return event?.tool_use_id || event?.tool_name || 'tool';
}

function getChangedFile(event) {
  return event?.metadata?.changed_file || null;
}

export function createToolPanelController({
  containerEl,
  visibleLimit,
  longRunningMs,
  onOpenDiff,
  onPersistTool,
  onStatsUpdate,
  onOpenGeneratedTool,
  onRefreshCustomTools,
}) {
  const runningTools = new Map();

  function enforceHistoryLimit() {
    let older = containerEl.querySelector('.older-tools');
    const directTools = Array.from(containerEl.children).filter(el => el.matches('details.tool'));
    if (directTools.length <= visibleLimit) return;
    if (!older) {
      older = document.createElement('details');
      older.className = 'older-tools';
      const summary = document.createElement('summary');
      summary.textContent = 'Older tool runs';
      const list = document.createElement('div');
      list.className = 'older-tools-list';
      older.append(summary, list);
      containerEl.appendChild(older);
    }
    const list = older.querySelector('.older-tools-list');
    directTools.slice(visibleLimit).forEach(el => list.appendChild(el));
    const count = list.querySelectorAll('details.tool').length;
    older.querySelector('summary').textContent = `Older tool runs (${count})`;
  }

  function appendDiffAction(toolEl, event) {
    const changedFile = getChangedFile(event);
    const skipped = event?.metadata?.changed_file_skipped_reason;
    if (!changedFile && !skipped) return;

    const existing = toolEl.querySelector('.tool-actions');
    if (existing) existing.remove();

    const actions = document.createElement('div');
    actions.className = 'tool-actions';

    if (changedFile?.path && typeof changedFile.old_content === 'string' && !event.is_error) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Open Diff';
      btn.addEventListener('click', () => onOpenDiff(event));
      actions.appendChild(btn);
    } else if (skipped) {
      const note = document.createElement('span');
      note.className = 'tool-note';
      note.textContent = `Diff unavailable: ${skipped}`;
      actions.appendChild(note);
    }

    if (actions.childNodes.length) toolEl.appendChild(actions);
  }

  function appendTool(toolName, toolInput, output, isError, save = true, eventData = null) {
    const item = document.createElement('details');
    item.className = isError ? 'tool error' : 'tool';
    item.open = true;
    if (eventData?.tool_use_id) item.dataset.toolId = eventData.tool_use_id;

    const summary = document.createElement('summary');
    summary.textContent = output
      ? `${toolName} ${isError ? '✗ failed' : '✓ done'}`
      : `⚙ ${toolName} running…`;

    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(output || toolInput || {}, null, 2);

    item.append(summary, pre);
    if (eventData) appendDiffAction(item, eventData);
    containerEl.prepend(item);
    enforceHistoryLimit();

    if (save) {
      onPersistTool({ type: 'tool', tool_name: toolName, tool_input: toolInput, output, is_error: isError });
    }
    return item;
  }

  function startLongRunTimer(toolEl, event) {
    const key = keyForToolEvent(event);
    const startedAt = Date.now();
    toolEl.dataset.startedAt = String(startedAt);
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      toolEl.classList.toggle('running-long', Date.now() - startedAt >= longRunningMs);
      const summary = toolEl.querySelector('summary');
      if (summary) summary.textContent = `⚙ ${event.tool_name} running… ${elapsed}s`;
    }, 1000);
    runningTools.set(key, timer);
  }

  function stopLongRunTimer(event) {
    const key = keyForToolEvent(event);
    const timer = runningTools.get(key);
    if (timer) clearInterval(timer);
    runningTools.delete(key);
  }

  function start(event) {
    const toolEl = appendTool(event.tool_name, event.tool_input, null, false, true, event);
    toolEl.dataset.tool = event.tool_name;
    startLongRunTimer(toolEl, event);
  }

  function complete(event) {
    stopLongRunTimer(event);
    const selector = event.tool_use_id
      ? `[data-tool-id="${event.tool_use_id}"]`
      : `[data-tool="${event.tool_name}"]`;
    const existing = containerEl.querySelector(selector);
    if (existing) {
      existing.className = event.is_error ? 'tool error' : 'tool';
      existing.open = true;
      existing.querySelector('summary').textContent =
        `${event.tool_name} ${event.is_error ? '✗ failed' : '✓ done'}`;
      existing.querySelector('pre').textContent =
        JSON.stringify(event.output || '', null, 2);
      appendDiffAction(existing, event);
      existing.removeAttribute('data-tool');
      existing.removeAttribute('data-tool-id');
    } else {
      appendTool(event.tool_name, event.tool_input, event.output, event.is_error, true, event);
    }
    onStatsUpdate(event.tool_name, !event.is_error);
    if (event.tool_name === 'create_tool' && !event.is_error) {
      onOpenGeneratedTool(event);
      onRefreshCustomTools();
    }
  }

  function clear() {
    for (const timer of runningTools.values()) clearInterval(timer);
    runningTools.clear();
    containerEl.innerHTML = '';
  }

  return {
    appendTool,
    start,
    complete,
    clear,
  };
}
