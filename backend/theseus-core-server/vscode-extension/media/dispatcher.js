export function createEventDispatcher(ctx) {
  return function dispatch(event) {
    switch (event.type) {
      case 'AssistantTextDelta':
        ctx.touchLoopActivity?.('running', 'Answering');
        if (!ctx.currentAssistantEl) {
          const { article, body } = ctx.createTypingIndicator();
          ctx.currentAssistantArticle = article;
          ctx.currentAssistantEl = body;
          ctx.currentAssistantTxt = '';
          ctx.markdownRenderRAF = null;
        }
        if (ctx.currentAssistantEl.querySelector('.typing-indicator')) {
          ctx.currentAssistantEl.innerHTML = '';
        }
        ctx.currentAssistantTxt += event.text || '';
        
        if (!ctx.markdownRenderRAF) {
          ctx.markdownRenderRAF = requestAnimationFrame(() => {
            if (ctx.currentAssistantEl) {
              ctx.currentAssistantEl.innerHTML = ctx.renderMarkdown(ctx.currentAssistantTxt);
              ctx.messagesEl.scrollTop = ctx.messagesEl.scrollHeight;
            }
            ctx.markdownRenderRAF = null;
          });
        }
        break;

      case 'AssistantTurnComplete':
        if (ctx.currentAssistantTxt) {
          ctx.savedHistory.push({ type: 'message', role: 'assistant', text: ctx.currentAssistantTxt });
          ctx.persistState();
          if (ctx.currentAssistantArticle && ctx.currentAssistantEl) {
            ctx.maybeAddFold(ctx.currentAssistantArticle, ctx.currentAssistantEl, ctx.currentAssistantTxt);
          }
        } else if (ctx.currentAssistantArticle) {
          ctx.currentAssistantArticle.remove();
        }
        ctx.toolPanel.note({
          key: 'request',
          label: 'answered',
          state: 'info',
        });
        ctx.runnerState = {
          ...ctx.runnerState,
          state: ctx.runnerState.running ? 'ready' : ctx.runnerState.state,
          lifecycle: ctx.runnerState.running ? 'ready' : ctx.runnerState.lifecycle,
        };
        ctx.currentAssistantArticle = null;
        ctx.currentAssistantEl = null;
        ctx.currentAssistantTxt = '';
        ctx.setGenerating(false);
        ctx.toolPanel.finishRequest();
        break;

      case 'AgentLoopStatus': {
        ctx.showActiveSkills(event);
        const status = ctx.formatAgentLoopStatus(event);
        ctx.setLoopStatus(status.state, status.text);
        if (status.state !== 'idle') {
          ctx.toolPanel.note({
            key: `loop:${event.tool_use_id || event.phase || 'status'}`,
            label: status.text,
            detail: event.message && event.message !== status.text ? event.message : '',
            state: status.state,
          });
        }
        break;
      }

      case 'CompactProgressEvent': {
        const status = ctx.formatCompactProgress(event);
        ctx.setLoopStatus(status.state, status.text);
        ctx.toolPanel.note({
          key: 'compact',
          label: status.text,
          detail: event.trigger ? `(${event.trigger})` : '',
          state: status.state === 'error' ? 'error' : 'info',
        });
        if (event.phase === 'compact_failed') {
          ctx.appendTransientMessage('system', status.text, 'warn', 5000);
        }
        break;
      }

      case 'ToolExecutionStarted': {
        ctx.toolPanel.start(event);
        break;
      }

      case 'ToolExecutionCompleted': {
        ctx.showActiveSkills(event);
        ctx.toolPanel.complete(event);
        const reviewItem = ctx.createChangeReviewItem(event);
        if (reviewItem) {
          ctx.changeReviews = [reviewItem, ...ctx.changeReviews].slice(0, 20);
          ctx.persistState();
          ctx.renderChangeReviewPanel();
        }
        break;
      }

      case 'RunnerReady':
        ctx.activeRunnerMode = 'agent';
        // runner가 정상화되었으므로 누적된 retry banner를 모두 제거
        ctx.clearRetryBanners?.();
        ctx.clearTransientSystemMessages?.();
        ctx.applyRunnerStatus({ ...event, type: 'RunnerStatus', running: true, processRunning: true, lifecycle: 'ready', state: 'ready' });
        if (ctx.runnerState.connectedSessionId !== ctx.runnerState.sessionId) {
          ctx.runnerState.connectedSessionId = ctx.runnerState.sessionId;
          ctx.appendTransientMessage('system', `✅ Connected  model: ${event.model}\ncwd: ${event.cwd}`, 'info', 1000);
        }
        break;

      case 'RunnerStarting':
        ctx.applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: true, lifecycle: 'starting', state: 'starting' });
        break;

      case 'RunnerStatus':
        ctx.applyRunnerStatus(event);
        if (event.running || event.state === 'ready' || event.lifecycle === 'ready') {
          ctx.clearRetryBanners?.();
          ctx.clearTransientSystemMessages?.();
        }
        break;

      case 'RunnerDiagnostic':
        ctx.runnerState.lastDiagnostic = event;
        if (event.code === 'session_busy') {
          break;
        }
        if (
          event.code === 'ready_timeout' &&
          (ctx.runnerState.running || ctx.runnerState.state === 'ready' || ctx.runnerState.lifecycle === 'ready')
        ) {
          ctx.clearRetryBanners?.();
          ctx.clearTransientSystemMessages?.();
          break;
        }
        if (event.code === 'ready_timeout') {
          ctx.setLoopStatus('error', 'starting stale');
          ctx.appendTransientMessage('system', event.message || 'Runner startup is taking longer than expected.', 'warn');
        } else if (event.code !== 'user_stop') {
          ctx.appendTransientMessage('system', event.message || 'Runner diagnostic', 'warn');
        }
        break;

      case 'RunnerExited':
        ctx.applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'exited', state: 'exited' });
        ctx.setGenerating(false);
        ctx.appendTransientMessage('system', 'Runner stopped.', 'warn');
        break;

      case 'RunnerStopped':
        ctx.applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'stopped', state: 'stopped' });
        ctx.setGenerating(false);
        ctx.appendTransientMessage('system', 'Runner stopped gracefully.', 'warn');
        break;

      case 'RunnerError':
        ctx.runnerState.lastDiagnostic = event;
        ctx.applyRunnerStatus({ ...event, type: 'RunnerStatus', running: false, processRunning: false, lifecycle: 'error', state: 'error', lastDiagnostic: event });
        ctx.appendTransientMessage('system', event.message || 'Unknown error', 'error');
        if (!/falling back to stdio runner/i.test(event.message || '')) {
          ctx.appendRetryBanner();
        }
        ctx.appendTransientMessage('system', '→ View > Output > "Theseus" for details', 'hint');
        break;

      case 'ErrorEvent':
        ctx.setGenerating(false);
        ctx.toolPanel.finishRequest();
        ctx.appendMessageEl('system', event.message || 'Error', 'error');
        break;

      case 'StatusEvent':
        if (ctx.showActiveSkills(event) && /^Active skills:/i.test(event.message || '')) {
          ctx.setGenerating(false);
          break;
        }
        {
          const compactStatus = ctx.compactStatusFromMessage(event.message);
          if (compactStatus) {
            ctx.setLoopStatus(compactStatus.state, compactStatus.label);
            ctx.toolPanel.note({
              key: 'compact',
              label: compactStatus.label,
              detail: compactStatus.detail,
              state: compactStatus.state,
            });
            break;
          }
        }
        if (/PLAN 승인\/거부는 WAIT_FOR_REVIEW 상태에서만 가능합니다\./.test(event.message || '')) {
          ctx.setGenerating(false);
          ctx.clearSavedPlan();
          break;
        }
        if (/^(세션 목록|세션 전환|세션 삭제|세션 이름 변경|새 세션으로 전환):/.test(event.message || '')) {
          ctx.appendTransientMessage('system', event.message || '', 'hint', 4000);
          break;
        }
        if (/Request failed; retrying|Model rejected max_tokens|도구 호출 없이 작업 진행 의도/i.test(event.message || '')) {
          ctx.toolPanel.note({
            key: `status:${event.message || ''}`,
            label: event.message || 'status',
            state: 'running',
          });
          break;
        }
        if (/^Tool registry refreshed:/i.test(event.message || '')) {
          ctx.toolPanel.note({
            key: 'tool-registry-refreshed',
            label: event.message || 'Tool registry refreshed.',
            state: 'info',
          });
          break;
        }
        ctx.setGenerating(false);
        ctx.appendMessageEl('system', event.message || '', 'info');
        break;

      case 'PermissionRequest':
        ctx.setLoopStatus('running', 'permission requested');
        ctx.appendTransientMessage(
          'system',
          `Permission requested${event.tool_name ? ` for ${event.tool_name}` : ''}: ${event.message || 'waiting for runner decision'}`,
          'warn',
          5000,
        );
        break;

      case 'filesResult':
        ctx.autocomplete.show((event.files || []).map(ctx.autocomplete.mentionValue));
        break;

      case 'PlanDraftedEvent':
        ctx.savedPlan = event.structured_plan || null;
        if (ctx.savedPlan) {
          ctx.savedPlan.reviewState = 'wait';
          ctx.savedPlan.phase = 'wait';
        }
        ctx.setSavedPlan(ctx.savedPlan);
        ctx.appendMessageEl('system', '📋 Plan drafted — review and approve to execute.', 'info');
        break;

      case 'PlanPhaseTransitionRequested':
        if (ctx.savedPlan) {
          const rawPhase = String(event.to_phase || '').trim();
          const normalizedPhase = rawPhase.toLowerCase();
          const nextState = normalizedPhase === 'completed'
            ? 'done'
            : normalizedPhase === 'waitforreview'
              ? 'wait'
              : normalizedPhase || 'review';
          ctx.savedPlan.reviewState = nextState;
          ctx.savedPlan.phase = rawPhase || nextState;
          ctx.setSavedPlan(ctx.savedPlan);
        }
        break;

      case 'PlanReviewEvent':
        if (['not_reviewable', 'closed', 'stale', 'cancelled', 'canceled', 'deleted'].includes(event.action)) {
          ctx.clearSavedPlan();
          break;
        }
        if (ctx.savedPlan) {
          const nextState = event.action === 'completed'
            ? 'done'
            : event.action === 'approved'
              ? 'executing'
              : event.action === 'rejected'
                ? 'drafting'
                : String(event.action || event.phase || 'review').toLowerCase();
          ctx.savedPlan.reviewState = nextState;
          ctx.savedPlan.phase = event.phase || nextState;
          if (Number.isInteger(event.totalTasks)) ctx.savedPlan.totalTasks = event.totalTasks;
          if (Number.isInteger(event.completedTasks)) ctx.savedPlan.completedTasks = event.completedTasks;
          if (Number.isInteger(event.remainingTasks)) ctx.savedPlan.remainingTasks = event.remainingTasks;
          ctx.setSavedPlan(ctx.savedPlan);
        }
        break;

      case 'SessionListEvent':
        ctx.sessions = Array.isArray(event.sessions) ? event.sessions : [];
        ctx.updateSession(event.current || ctx.currentSession);
        break;

      case 'SessionChangedEvent':
        ctx.updateSession(event.current || 'default');
        ctx.messagesEl.innerHTML = '';
        ctx.toolPanel.clear();
        if (Object.prototype.hasOwnProperty.call(event, 'planState')) {
          ctx.setSavedPlan(ctx.planFromSessionState(event.planState));
        } else {
          ctx.savedPlan = ctx.planBySession[ctx.currentSession] || null;
          ctx.renderPlanPanel(ctx.savedPlan);
        }
        ctx.savedHistory = Array.isArray(event.history) ? event.history : [];
        ctx.savedHistory.forEach(m => {
          if (m.type === 'message') {
            const text = ctx.collapseDuplicatedHistoryText(m.text);
            const rendered = ctx.appendMessageEl(m.role, text, m.tone, false);
            if (m.role === 'user') ctx.toolPanel.startRequest(text, rendered.article);
            if (m.role === 'assistant') ctx.toolPanel.attachAssistant(rendered.article);
          } else if (m.type === 'tool') {
            ctx.toolPanel.appendTool(m.tool_name, m.tool_input, m.output, m.is_error, false, m);
          }
        });
        ctx.persistState();
        ctx.renderContextBar();
        break;

      case 'SessionExportedEvent': {
        const preview = event.format === 'json'
          ? String(event.content || '').slice(0, 800)
          : String(event.content || '').slice(0, 1200);
        ctx.appendMessageEl('system', `Exported ${event.name} (${event.format})\n\n${preview}`, 'info');
        break;
      }

      case 'workspaceInfo':
        if (ctx.workspaceLabelEl) {
          ctx.workspaceLabelEl.textContent = event.name || '';
          ctx.workspaceLabelEl.title       = event.path || '';
        }
        break;

      case 'activeFileChanged':
        if (ctx.activeFileEl) {
          const name = (event.file || '').split(/[/\\]/).pop();
          const line = Number.isInteger(event.line) ? `:${event.line}` : '';
          ctx.activeFileEl.textContent = name ? `📄 ${name}${line}` : '';
          ctx.activeFileEl.title       = event.file || '';
        }
        ctx.activeFileContext = event.file ? { file: event.file, line: event.line } : null;
        if (ctx.suppressedActiveFile && ctx.suppressedActiveFile !== event.file) ctx.suppressedActiveFile = '';
        ctx.renderContextBar();
        break;

      case 'customToolsLoaded':
        if (!ctx.isRunnerProcessLive?.()) {
          ctx.renderCustomTools(event.tools || [], event.source || 'host');
        }
        break;

      case 'customToolInventoryUpdated':
        ctx.renderCustomTools(event.tools || [], event.source || 'runner');
        break;

      case 'customToolsChanged': {
        const icons    = { created: '🔧➕', changed: '🔧✏️', deleted: '🔧🗑' };
        const icon     = icons[event.action] || '🔧';
        const fileName = (event.file || '').split(/[/\\]/).pop();
        const validation = event.validation;
        const msg = validation?.message ? ` — ${validation.message}` : '';
        ctx.appendMessageEl('system', `${icon} Tool file ${event.action}: ${fileName}${msg}`, validation?.success === false ? 'warn' : 'info');
        ctx.vscode.postMessage({ type: 'getCustomTools' });
        break;
      }

      case 'customToolValidation':
        ctx.toolPanel.note({
          key: `custom-tool-validation:${event.message || ''}`,
          label: event.message || 'Custom tool validation updated.',
          state: event.success ? 'info' : 'error',
        });
        if (!event.success) {
          ctx.appendTransientMessage('system', event.message || 'Custom tool validation failed.', 'warn', 5000);
        }
        break;

      case 'customToolInstallProgress':
        ctx.toolPanel.note({
          key: `custom-tool-install:${Array.isArray(event.packages) ? event.packages.join(',') : event.message || 'install'}`,
          label: event.message || 'Custom tool dependency install updated.',
          detail: Array.isArray(event.packages) && event.packages.length ? event.packages.join(', ') : '',
          state: event.success ? 'info' : 'error',
        });
        if (!event.success) {
          ctx.appendTransientMessage('system', event.message || 'Custom tool dependency install failed.', 'warn', 5000);
        }
        if (!event.success) ctx.vscode.postMessage({ type: 'getCustomTools' });
        break;

      case 'toolRegistryUpdated':
        break;

      case 'healthStatus':
        ctx.latestHealth = event;
        ctx.healthPanelVisible = true;
        ctx.renderHealthPanel();
        break;

      case 'changeReviewUpdated':
        if (event.id) ctx.changeReviews = ctx.changeReviews.filter(item => item.id !== event.id);
        ctx.persistState();
        ctx.renderChangeReviewPanel();
        ctx.toolPanel.note({
          key: `change-review:${event.id || event.path || event.message || 'updated'}`,
          label: event.message || 'Change review updated.',
          state: event.success === false ? 'error' : 'info',
        });
        if (event.success === false) {
          ctx.appendTransientMessage('system', event.message || 'Change review failed.', 'warn', 5000);
        }
        break;

      case 'assetSaved':
        ctx.insertMentionPath(event.path || '');
        ctx.appendMessageEl('system', `Asset saved: ${event.path}`, 'info');
        break;

      case 'assetSaveFailed':
        ctx.appendMessageEl('system', event.message || 'Failed to save asset', 'error');
        break;

      case 'settingsChanged':
        ctx.toolPanel.note({
          key: 'settings-changed',
          label: event.restartRequired
            ? 'Settings changed. Restart Theseus to apply them.'
            : 'Settings changed. They will apply on the next Start.',
          state: 'info',
        });
        ctx.appendTransientMessage(
          'system',
          event.restartRequired
            ? 'Settings changed. Restart Theseus to apply them.'
            : 'Settings changed. They will apply on the next Start.',
          'warn',
          5000,
        );
        break;

      case 'ClearChat':
        ctx.clearChat();
        break;

      case 'injectText': {
        const injected = event.text || '';
        ctx.promptEl.value = injected + (ctx.promptEl.value ? '\n' + ctx.promptEl.value : '');
        ctx.resizeTextarea();
        ctx.promptEl.focus();
        ctx.promptEl.selectionStart = ctx.promptEl.selectionEnd = ctx.promptEl.value.length;
        break;
      }
    }
  };
}
