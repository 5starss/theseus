function keyForToolEvent(event) {
  return event?.tool_use_id || event?.tool_name || 'tool';
}

function getChangedFile(event) {
  return event?.metadata?.changed_file || null;
}

function formatToolPayload(value) {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderToolPayload(pre, value) {
  const text = formatToolPayload(value);
  if (!text) return false;
  const renderer = window.TheseusMarkdown?.renderMarkdown;
  pre.innerHTML = renderer ? renderer(text) : escHtml(text);
  return true;
}

function compactPrompt(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return 'request';
  return normalized.length > 48 ? `${normalized.slice(0, 45)}...` : normalized;
}

export function createActivityLogController({
  messagesEl,
  longRunningMs,
  onOpenDiff,
  onPersistTool,
  onStatsUpdate,
  onOpenGeneratedTool,
  onRefreshCustomTools,
}) {
  const runningTools = new Map();
  const runningToolEls = new Map();
  const noteEls = new Map();
  let currentRequest = null;
  let requestSeq = 0;

  function startRequest(prompt, anchorEl) {
    requestSeq += 1;
    currentRequest = {
      id: requestSeq,
      prompt: prompt || '',
      anchorEl,
      groupEl: null,
      listEl: null,
      summaryTitleEl: null,
      summaryMetaEl: null,
    };
  }

  function appendAfterAnchor(el, anchorEl) {
    if (anchorEl?.parentNode === messagesEl) {
      messagesEl.insertBefore(el, anchorEl.nextSibling);
    } else {
      messagesEl.appendChild(el);
    }
  }

  function ensureRequest() {
    if (!currentRequest) {
      const fallbackAnchor = Array.from(messagesEl.querySelectorAll('.message.user')).pop() || messagesEl.lastElementChild;
      requestSeq += 1;
      currentRequest = {
        id: requestSeq,
        prompt: fallbackAnchor?.querySelector?.('.body')?.textContent || '',
        anchorEl: fallbackAnchor,
        groupEl: null,
        listEl: null,
        summaryTitleEl: null,
        summaryMetaEl: null,
      };
    }
    if (currentRequest.groupEl) return currentRequest;

    const groupEl = document.createElement('details');
    groupEl.className = 'activity-group';
    groupEl.open = true;

    const summary = document.createElement('summary');
    summary.className = 'activity-summary';

    const title = document.createElement('span');
    title.className = 'activity-title';

    const meta = document.createElement('span');
    meta.className = 'activity-meta';

    summary.append(title, meta);

    const list = document.createElement('div');
    list.className = 'activity-list';

    groupEl.append(summary, list);
    appendAfterAnchor(groupEl, currentRequest.anchorEl);

    currentRequest.groupEl = groupEl;
    currentRequest.listEl = list;
    currentRequest.summaryTitleEl = title;
    currentRequest.summaryMetaEl = meta;
    updateGroupSummary(currentRequest);
    return currentRequest;
  }

  function updateGroupSummary(request) {
    if (!request?.groupEl || !request.summaryTitleEl || !request.summaryMetaEl) return;
    const tools = Array.from(request.groupEl.querySelectorAll('details.tool'));
    const notes = Array.from(request.groupEl.querySelectorAll('.activity-note'));
    const running = tools.filter(el => el.dataset.status === 'running').length;
    const failed = tools.filter(el => el.dataset.status === 'failed').length;
    const done = tools.filter(el => el.dataset.status === 'done').length;
    const parts = [];
    if (running) parts.push(`${running} running`);
    if (done) parts.push(`${done} done`);
    if (failed) parts.push(`${failed} failed`);
    if (!parts.length && notes.length) parts.push(`${notes.length} status`);
    if (!parts.length) parts.push('waiting');
    request.summaryTitleEl.textContent = `Activity for "${compactPrompt(request.prompt)}"`;
    request.summaryMetaEl.textContent = `${tools.length} tool${tools.length === 1 ? '' : 's'} · ${parts.join(', ')}`;
  }

  function scrollRequestIntoView(request) {
    request?.groupEl?.scrollIntoView?.({ block: 'nearest' });
  }

  function note({ key, label, detail = '', state = 'info' } = {}) {
    const text = String(label || '').trim();
    if (!text) return null;
    const request = ensureRequest();
    const noteKey = key ? `${request.id || 'request'}:${key}` : '';
    let item = noteKey ? noteEls.get(noteKey) : null;
    if (!item || item.dataset.requestPrompt !== (request.prompt || '')) {
      item = document.createElement('div');
      item.className = 'activity-note';
      item.dataset.requestPrompt = request.prompt || '';
      if (noteKey) noteEls.set(noteKey, item);

      const marker = document.createElement('span');
      marker.className = 'activity-note-marker';
      marker.textContent = '•';

      const body = document.createElement('span');
      body.className = 'activity-note-body';

      const labelEl = document.createElement('span');
      labelEl.className = 'activity-note-label';

      const detailEl = document.createElement('span');
      detailEl.className = 'activity-note-detail';

      body.append(labelEl, detailEl);
      item.append(marker, body);
      request.listEl.appendChild(item);
    }

    item.dataset.state = state || 'info';
    const labelEl = item.querySelector('.activity-note-label');
    const detailEl = item.querySelector('.activity-note-detail');
    if (labelEl) labelEl.textContent = text;
    if (detailEl) {
      const detailText = String(detail || '').trim();
      detailEl.textContent = detailText ? ` ${detailText}` : '';
    }
    updateGroupSummary(request);
    scrollRequestIntoView(request);
    return item;
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

  function buildToolEntry(toolName, toolInput, output, isError, status, eventData) {
    return {
      type: 'tool',
      tool_use_id: eventData?.tool_use_id,
      tool_name: toolName,
      tool_input: toolInput,
      output,
      is_error: !!isError,
      status,
    };
  }

  function appendToolSection(body, label, value) {
    const text = formatToolPayload(value);
    if (!text) return;
    const section = document.createElement('section');
    section.className = 'tool-section';

    const heading = document.createElement('div');
    heading.className = 'tool-section-label';
    heading.textContent = label;

    const pre = document.createElement('pre');
    renderToolPayload(pre, value);

    section.append(heading, pre);
    body.appendChild(section);
  }

  function renderToolContent(toolEl, { toolInput, output, isRunning }) {
    let body = toolEl.querySelector('.tool-body');
    if (!body) {
      body = document.createElement('div');
      body.className = 'tool-body';
      toolEl.appendChild(body);
    }
    body.innerHTML = '';
    appendToolSection(body, isRunning ? 'Input' : 'Input', toolInput);
    appendToolSection(body, isRunning ? 'Running' : 'Output', isRunning ? null : output);
    if (!body.childNodes.length) {
      appendToolSection(body, isRunning ? 'Running' : 'Output', isRunning ? toolInput : output);
    }
  }

  function appendTool(toolName, toolInput, output, isError, save = true, eventData = null) {
    const request = ensureRequest();
    const isRunning = eventData?.status === 'running'
      || eventData?.type === 'ToolExecutionStarted'
      || (!eventData && output === undefined && !isError);
    const item = document.createElement('details');
    item.className = isError ? 'tool error' : 'tool';
    item.open = true;
    item.dataset.status = isRunning ? 'running' : isError ? 'failed' : 'done';
    if (eventData?.tool_use_id) item.dataset.toolId = eventData.tool_use_id;
    if (toolName) item.dataset.tool = toolName;

    const summary = document.createElement('summary');
    summary.textContent = isRunning
      ? `${toolName} running...`
      : `${toolName} ${isError ? 'failed' : 'done'}`;

    item.appendChild(summary);
    renderToolContent(item, { toolInput, output, isRunning });
    if (eventData) appendDiffAction(item, eventData);
    request.listEl.appendChild(item);
    updateGroupSummary(request);
    scrollRequestIntoView(request);

    if (save) {
      onPersistTool(buildToolEntry(toolName, toolInput, output, isError, item.dataset.status, eventData));
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
      if (summary) summary.textContent = `${event.tool_name} running... ${elapsed}s`;
    }, 1000);
    runningTools.set(key, timer);
    runningToolEls.set(key, { toolEl, request: currentRequest });
  }

  function stopLongRunTimer(event) {
    const key = keyForToolEvent(event);
    const timer = runningTools.get(key);
    if (timer) clearInterval(timer);
    runningTools.delete(key);
  }

  function start(event) {
    const toolEl = appendTool(event.tool_name, event.tool_input, null, false, false, event);
    startLongRunTimer(toolEl, event);
  }

  function complete(event) {
    stopLongRunTimer(event);
    const key = keyForToolEvent(event);
    const running = runningToolEls.get(key);
    const existing = running?.toolEl;
    if (existing) {
      const wasOpen = existing.open;
      existing.className = event.is_error ? 'tool error' : 'tool';
      existing.open = wasOpen;
      existing.dataset.status = event.is_error ? 'failed' : 'done';
      existing.querySelector('summary').textContent =
        `${event.tool_name} ${event.is_error ? 'failed' : 'done'}`;
      renderToolContent(existing, { toolInput: event.tool_input, output: event.output, isRunning: false });
      appendDiffAction(existing, event);
      runningToolEls.delete(key);
      updateGroupSummary(running.request || currentRequest);
      scrollRequestIntoView(running.request || currentRequest);
      onPersistTool(buildToolEntry(event.tool_name, event.tool_input, event.output, event.is_error, existing.dataset.status, event));
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
    runningToolEls.clear();
    noteEls.clear();
    currentRequest = null;
    messagesEl.querySelectorAll('.activity-group').forEach(el => el.remove());
  }

  return {
    appendTool,
    note,
    start,
    complete,
    clear,
    startRequest,
  };
}
