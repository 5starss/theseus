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

function compactPrompt(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return 'request';
  return normalized.length > 48 ? `${normalized.slice(0, 45)}...` : normalized;
}

function formatClock(value) {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`;
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
  const requests = new Set();
  let currentRequest = null;
  let requestSeq = 0;

  function startRequest(prompt, anchorEl) {
    if (currentRequest?.collapseTimer) clearTimeout(currentRequest.collapseTimer);
    requestSeq += 1;
    currentRequest = {
      id: requestSeq,
      prompt: prompt || '',
      anchorEl,
      turnEl: null,
      groupEl: null,
      listEl: null,
      summaryEl: null,
      summaryTitleEl: null,
      summaryMetaEl: null,
      collapseTimer: null,
      userOpenOverride: null,
      startedAt: Date.now(),
      lastActivityAt: Date.now(),
    };
    requests.add(currentRequest);
    ensureTurnContainer(currentRequest);
  }

  function ensureTurnContainer(request) {
    if (!request?.anchorEl) return null;
    if (request.turnEl?.parentNode) return request.turnEl;
    let turnEl = request.anchorEl.closest?.('.turn');
    if (!turnEl && request.anchorEl.parentNode === messagesEl) {
      turnEl = document.createElement('section');
      turnEl.className = 'turn';
      messagesEl.insertBefore(turnEl, request.anchorEl);
      turnEl.appendChild(request.anchorEl);
    }
    request.turnEl = turnEl || null;
    return request.turnEl;
  }

  function appendAfterAnchor(el, request) {
    const turnEl = ensureTurnContainer(request);
    if (turnEl) {
      if (request.anchorEl?.parentNode === turnEl) {
        request.anchorEl.insertAdjacentElement('afterend', el);
      } else {
        turnEl.appendChild(el);
      }
      return;
    }
    if (request.anchorEl?.parentNode === messagesEl) {
      messagesEl.insertBefore(el, request.anchorEl.nextSibling);
      return;
    }
    messagesEl.appendChild(el);
  }

  function ensureRequest() {
    if (!currentRequest) {
      const fallbackAnchor = Array.from(messagesEl.querySelectorAll('.message.user')).pop() || messagesEl.lastElementChild;
      requestSeq += 1;
      currentRequest = {
        id: requestSeq,
        prompt: fallbackAnchor?.querySelector?.('.body')?.textContent || '',
        anchorEl: fallbackAnchor,
        turnEl: null,
        groupEl: null,
        listEl: null,
        summaryEl: null,
        summaryTitleEl: null,
        summaryMetaEl: null,
        collapseTimer: null,
        userOpenOverride: null,
        startedAt: Date.now(),
        lastActivityAt: Date.now(),
      };
      requests.add(currentRequest);
      ensureTurnContainer(currentRequest);
    }
    if (currentRequest.groupEl) return currentRequest;

    const groupEl = document.createElement('div');
    groupEl.className = 'activity-group open';
    groupEl.hidden = true;

    const summary = document.createElement('button');
    summary.type = 'button';
    summary.className = 'activity-summary';
    summary.setAttribute('aria-expanded', 'true');

    const caret = document.createElement('span');
    caret.className = 'activity-caret';
    caret.textContent = '›';

    const title = document.createElement('span');
    title.className = 'activity-title';

    const meta = document.createElement('span');
    meta.className = 'activity-meta';

    const list = document.createElement('div');
    list.className = 'activity-list';

    const ownerRequest = currentRequest;
    summary.addEventListener('click', () => {
      const nextOpen = !groupEl.classList.contains('open');
      if (ownerRequest) ownerRequest.userOpenOverride = nextOpen;
      groupEl.classList.toggle('open', nextOpen);
      summary.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
      list.hidden = !nextOpen;
    });

    summary.append(caret, title, meta);
    groupEl.append(summary, list);
    appendAfterAnchor(groupEl, currentRequest);

    currentRequest.groupEl = groupEl;
    currentRequest.listEl = list;
    currentRequest.summaryEl = summary;
    currentRequest.summaryTitleEl = title;
    currentRequest.summaryMetaEl = meta;
    updateGroupSummary(currentRequest);
    return currentRequest;
  }

  function setRequestOpen(request, open) {
    if (!request?.groupEl || !request.listEl) return;
    request.groupEl.classList.toggle('open', !!open);
    request.listEl.hidden = !open;
    request.summaryEl?.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function setRequestActive(request, active) {
    if (!request?.groupEl) return;
    request.groupEl.toggleAttribute('data-active', !!active);
    request.lastActivityAt = Date.now();
    if (active) {
      if (request.collapseTimer) clearTimeout(request.collapseTimer);
      request.collapseTimer = null;
      if (request.userOpenOverride !== false) setRequestOpen(request, true);
    }
  }

  function attachAssistant(article) {
    if (!currentRequest || !article) return false;
    const turnEl = ensureTurnContainer(currentRequest);
    if (!turnEl) return false;
    if (article.parentNode !== turnEl) {
      turnEl.appendChild(article);
    }
    return true;
  }

  function requestRunningToolCount(request) {
    if (!request?.groupEl) return 0;
    return request.groupEl.querySelectorAll('details.tool[data-status="running"]').length;
  }

  function scheduleCollapse(request, delay = 1200) {
    if (!request?.groupEl || requestRunningToolCount(request) > 0) return;
    if (request.userOpenOverride !== null) {
      setRequestActive(request, false);
      return;
    }
    if (request.collapseTimer) clearTimeout(request.collapseTimer);
    request.collapseTimer = setTimeout(() => {
      if (requestRunningToolCount(request) === 0) {
        setRequestActive(request, false);
        setRequestOpen(request, false);
      }
      request.collapseTimer = null;
    }, delay);
  }

  function finishRequest() {
    if (!currentRequest) return;
    scheduleCollapse(currentRequest, 700);
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
    const last = formatClock(request.lastActivityAt || request.startedAt);
    request.summaryMetaEl.textContent = `${tools.length} tool${tools.length === 1 ? '' : 's'} · ${parts.join(', ')}${last ? ` · ${last}` : ''}`;
  }

  function note({ key, label, detail = '', state = 'info' } = {}) {
    const text = String(label || '').trim();
    if (!text) return null;
    const request = ensureRequest();
    request.groupEl.hidden = false;
    request.lastActivityAt = Date.now();
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

      const timeEl = document.createElement('span');
      timeEl.className = 'activity-note-time';

      body.append(labelEl, detailEl, timeEl);
      item.append(marker, body);
      request.listEl.appendChild(item);
    }

    item.dataset.state = state || 'info';
    const labelEl = item.querySelector('.activity-note-label');
    const detailEl = item.querySelector('.activity-note-detail');
    const timeEl = item.querySelector('.activity-note-time');
    if (labelEl) labelEl.textContent = text;
    if (detailEl) {
      const detailText = String(detail || '').trim();
      detailEl.textContent = detailText ? ` ${detailText}` : '';
    }
    if (timeEl) timeEl.textContent = ` · ${formatClock(Date.now())}`;
    if (state === 'running' || state === 'tool') {
      setRequestActive(request, true);
    } else if (state === 'info' && requestRunningToolCount(request) === 0) {
      scheduleCollapse(request);
    }
    updateGroupSummary(request);
    messagesEl.scrollTop = messagesEl.scrollHeight;
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
      startedAt: eventData?.startedAt,
      completedAt: eventData?.completedAt,
      durationMs: eventData?.durationMs,
    };
  }

  function appendTool(toolName, toolInput, output, isError, save = true, eventData = null) {
    const request = ensureRequest();
    request.groupEl.hidden = false;
    const isRunning = eventData?.status === 'running'
      || eventData?.type === 'ToolExecutionStarted'
      || (!eventData && output === undefined && !isError);
    if (isRunning) setRequestActive(request, true);
    request.lastActivityAt = Date.now();
    const item = document.createElement('details');
    item.className = isError ? 'tool error' : 'tool';
    item.open = isRunning;
    item.dataset.status = isRunning ? 'running' : isError ? 'failed' : 'done';
    if (eventData?.tool_use_id) item.dataset.toolId = eventData.tool_use_id;
    if (toolName) item.dataset.tool = toolName;
    const startedAt = eventData?.startedAt || Date.now();
    item.dataset.startedAt = String(startedAt);

    const summary = document.createElement('summary');
    summary.innerHTML = isRunning
      ? `<span class="tool-icon spin">⚙</span> ${toolName} running...`
      : `<span class="tool-icon">${isError ? '✗' : '✓'}</span> ${toolName} ${isError ? 'failed' : 'done'}`;

    const pre = document.createElement('pre');
    pre.textContent = formatToolPayload(isRunning ? toolInput : output);

    const meta = document.createElement('div');
    meta.className = 'tool-meta';
    const completedAt = eventData?.completedAt;
    const durationMs = eventData?.durationMs;
    meta.textContent = [
      startedAt ? `started ${formatClock(startedAt)}` : '',
      completedAt ? `finished ${formatClock(completedAt)}` : '',
      Number.isFinite(durationMs) ? `duration ${formatDuration(durationMs)}` : '',
    ].filter(Boolean).join(' · ');

    item.append(summary, meta, pre);
    if (eventData) appendDiffAction(item, eventData);
    request.listEl.appendChild(item);
    updateGroupSummary(request);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    if (!isRunning && !save) {
      setRequestOpen(request, false);
    }

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
      if (summary) summary.innerHTML = `<span class="tool-icon spin">⚙</span> ${event.tool_name} running... ${elapsed}s`;
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
    const completedAt = Date.now();
    if (existing) {
      existing.className = event.is_error ? 'tool error' : 'tool';
      existing.open = false;
      existing.dataset.status = event.is_error ? 'failed' : 'done';
      existing.dataset.completedAt = String(completedAt);
      const startedAt = Number(existing.dataset.startedAt || completedAt);
      const durationMs = Math.max(0, completedAt - startedAt);
      existing.querySelector('summary').innerHTML =
        `<span class="tool-icon">${event.is_error ? '✗' : '✓'}</span> ${event.tool_name} ${event.is_error ? 'failed' : 'done'}${durationMs ? ` · ${formatDuration(durationMs)}` : ''}`;
      const meta = existing.querySelector('.tool-meta');
      if (meta) {
        meta.textContent = [
          `started ${formatClock(startedAt)}`,
          `finished ${formatClock(completedAt)}`,
          `duration ${formatDuration(durationMs)}`,
        ].join(' · ');
      }
      existing.querySelector('pre').textContent = formatToolPayload(event.output);
      appendDiffAction(existing, event);
      runningToolEls.delete(key);
      if (running.request) running.request.lastActivityAt = completedAt;
      updateGroupSummary(running.request || currentRequest);
      onPersistTool(buildToolEntry(event.tool_name, event.tool_input, event.output, event.is_error, existing.dataset.status, {
        ...event,
        startedAt,
        completedAt,
        durationMs,
      }));
      scheduleCollapse(running.request || currentRequest);
    } else {
      const toolEl = appendTool(event.tool_name, event.tool_input, event.output, event.is_error, true, {
        ...event,
        completedAt,
      });
      scheduleCollapse(currentRequest);
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
    for (const request of requests) {
      if (request?.collapseTimer) clearTimeout(request.collapseTimer);
    }
    requests.clear();
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
    attachAssistant,
    finishRequest,
  };
}
