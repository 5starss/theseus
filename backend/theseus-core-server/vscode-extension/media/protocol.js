(function () {
  'use strict';

  const webviewToHostTypes = new Set([
    'init',
    'attachSession',
    'getStatus',
    'getRunnerStatus',
    'visibilityChanged',
    'send',
    'sendInput',
    'setMode',
    'sendWithMode',
    'getSessions',
    'newSession',
    'switchSession',
    'deleteSession',
    'renameSession',
    'exportSession',
    'reviewPlan',
    'openPlanPreview',
    'launchSession',
    'start',
    'stopSession',
    'stop',
    'interruptSession',
    'stopGen',
    'showLogs',
    'openSettings',
    'getFiles',
    'getWorkspaceName',
    'getActiveFile',
    'getCustomTools',
    'getHealth',
    'explainProblem',
    'fixProblem',
    'updateToolPermission',
    'savePastedImage',
    'revertChangedFile',
    'openFile',
    'openGeneratedTool',
    'openDiff',
  ]);

  const hostToWebviewTypes = new Set([
    'runnerEvent',
    'diagnostic',
    'historySnapshot',
    'sessionState',
    'transientNotice',
    'visibilityChanged',
    'fullState',
  ]);

  const knownRunnerEventTypes = new Set([
    'AssistantTextDelta',
    'AssistantTurnComplete',
    'AgentLoopStatus',
    'CompactProgressEvent',
    'ToolExecutionStarted',
    'ToolExecutionCompleted',
    'RunnerReady',
    'RunnerStarting',
    'RunnerStatus',
    'RunnerDiagnostic',
    'RunnerLifecycle',
    'RunnerHeartbeat',
    'RunnerExited',
    'RunnerStopped',
    'RunnerError',
    'ErrorEvent',
    'StatusEvent',
    'PermissionRequest',
    'filesResult',
    'PlanDraftedEvent',
    'PlanPhaseTransitionRequested',
    'PlanReviewEvent',
    'SessionListEvent',
    'SessionChangedEvent',
    'SessionExportedEvent',
    'workspaceInfo',
    'activeFileChanged',
    'customToolsLoaded',
    'customToolsChanged',
    'customToolValidation',
    'healthStatus',
    'changeReviewUpdated',
    'assetSaved',
    'assetSaveFailed',
    'settingsChanged',
    'ClearChat',
    'injectText',
  ]);

  function isObject(value) {
    return value !== null && typeof value === 'object';
  }

  function isWebviewToHostMessage(message) {
    return isObject(message) && webviewToHostTypes.has(message.type);
  }

  function optionalString(value) {
    return isMissing(value) || typeof value === 'string';
  }

  function optionalBoolean(value) {
    return isMissing(value) || typeof value === 'boolean';
  }

  function optionalNumber(value) {
    return isMissing(value) || typeof value === 'number';
  }

  function optionalStringArray(value) {
    return isMissing(value) || (Array.isArray(value) && value.every(item => typeof item === 'string'));
  }

  function isMissing(value) {
    return value === undefined || value === null;
  }

  function isKnownRunnerEventShape(event) {
    switch (event.type) {
      case 'AssistantTextDelta':
        return optionalString(event.text);
      case 'AgentLoopStatus':
        return optionalString(event.phase) && optionalNumber(event.turn) && optionalNumber(event.tool_count);
      case 'CompactProgressEvent':
        return optionalString(event.phase) && optionalString(event.trigger) && optionalString(event.message);
      case 'ToolExecutionStarted':
        return optionalString(event.tool_name);
      case 'ToolExecutionCompleted':
        return optionalString(event.tool_name) && optionalBoolean(event.is_error);
      case 'RunnerReady':
        return optionalString(event.model) && optionalString(event.cwd);
      case 'RunnerStatus':
        return optionalBoolean(event.running)
          && optionalBoolean(event.processRunning)
          && optionalString(event.lifecycle)
          && optionalString(event.state)
          && optionalNumber(event.daemonPort);
      case 'RunnerDiagnostic':
      case 'RunnerError':
      case 'ErrorEvent':
      case 'StatusEvent':
      case 'PermissionRequest':
        return optionalString(event.message);
      case 'filesResult':
        return optionalStringArray(event.files);
      case 'PlanPhaseTransitionRequested':
        return optionalString(event.from_phase)
          && optionalString(event.to_phase)
          && optionalString(event.reason)
          && optionalString(event.source)
          && optionalString(event.trigger);
      case 'SessionListEvent':
        return isMissing(event.sessions) || Array.isArray(event.sessions);
      case 'SessionChangedEvent':
        return optionalString(event.current)
          && (isMissing(event.history) || Array.isArray(event.history))
          && (isMissing(event.planState) || event.planState === null || isObject(event.planState));
      case 'SessionExportedEvent':
        return optionalString(event.name) && optionalString(event.format) && optionalString(event.content);
      case 'workspaceInfo':
        return optionalString(event.name) && optionalString(event.path);
      case 'activeFileChanged':
        return optionalString(event.file) && optionalNumber(event.line);
      case 'customToolsLoaded':
        return event.tools === undefined || Array.isArray(event.tools);
      case 'customToolValidation':
        return optionalBoolean(event.success) && optionalString(event.message);
      case 'healthStatus':
        return true;
      case 'changeReviewUpdated':
        return optionalString(event.id) && optionalBoolean(event.success) && optionalString(event.message);
      case 'assetSaved':
        return optionalString(event.path);
      case 'assetSaveFailed':
        return optionalString(event.message);
      case 'settingsChanged':
        return optionalBoolean(event.restartRequired);
      case 'injectText':
        return optionalString(event.text) && optionalBoolean(event.autoSubmit);
      default:
        return true;
    }
  }

  function normalizeRunnerEvent(event) {
    if (!isObject(event) || typeof event.type !== 'string' || !event.type) return null;
    if (knownRunnerEventTypes.has(event.type) && !isKnownRunnerEventShape(event)) return null;
    return event;
  }

  function normalizeHostMessage(message) {
    if (!isObject(message) || !hostToWebviewTypes.has(message.type)) return null;
    if (message.type === 'runnerEvent') {
      const event = normalizeRunnerEvent(message.event);
      return event ? { ...message, event } : null;
    }
    if (message.type === 'diagnostic') {
      const diagnostic = normalizeRunnerEvent(message.diagnostic);
      return diagnostic ? { ...message, diagnostic } : null;
    }
    if (message.type === 'sessionState') {
      const state = normalizeRunnerEvent(message.state);
      return state ? { ...message, state } : null;
    }
    if (message.type === 'historySnapshot') return Array.isArray(message.history) ? message : null;
    if (message.type === 'transientNotice') return typeof message.message === 'string' ? message : null;
    if (message.type === 'visibilityChanged') return typeof message.visible === 'boolean' ? message : null;
    if (message.type === 'fullState') return isObject(message.state) ? message : null;
    return null;
  }

  function createVsCodeApi(api) {
    return {
      getState: () => api.getState(),
      setState: state => api.setState(state),
      postMessage: message => {
        if (!isWebviewToHostMessage(message)) {
          console.warn('[Theseus] Unknown WebView message', message);
        }
        api.postMessage(message);
      },
    };
  }

  window.TheseusProtocol = {
    createVsCodeApi,
    isWebviewToHostMessage,
    normalizeHostMessage,
    normalizeRunnerEvent,
  };
}());
