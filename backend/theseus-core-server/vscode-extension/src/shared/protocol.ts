export type JsonObject = Record<string, unknown>;
type Nullable<T> = T | null;

export type RunnerLifecycleState =
  | 'starting'
  | 'starting_stale'
  | 'ready'
  | 'busy'
  | 'waiting_input'
  | 'stale'
  | 'stopped'
  | 'exited'
  | 'error'
  | string;

export type RunnerBaseEvent<T extends string> = {
  type: T;
  text?: Nullable<string>;
  message?: Nullable<string>;
  tool_name?: Nullable<string>;
  tool_input?: unknown;
  output?: unknown;
  is_error?: Nullable<boolean>;
  code?: number | string | null;
  model?: Nullable<string>;
  cwd?: Nullable<string>;
  metadata?: Nullable<JsonObject>;
  sessionId?: Nullable<string>;
  session?: Nullable<string>;
  workspaceCwd?: Nullable<string>;
  [key: string]: unknown;
};

export type AssistantTextDeltaEvent = RunnerBaseEvent<'AssistantTextDelta'> & {
  text?: Nullable<string>;
};

export type AssistantTurnCompleteEvent = RunnerBaseEvent<'AssistantTurnComplete'>;

export type AgentLoopStatusEvent = RunnerBaseEvent<'AgentLoopStatus'> & {
  phase?: Nullable<string>;
  turn?: Nullable<number>;
  tool_count?: Nullable<number>;
};

export type CompactProgressEvent = RunnerBaseEvent<'CompactProgressEvent'> & {
  phase?: Nullable<string>;
  trigger?: Nullable<string>;
};

export type ToolExecutionStartedEvent = RunnerBaseEvent<'ToolExecutionStarted'> & {
  tool_name?: Nullable<string>;
  tool_input?: unknown;
  tool_use_id?: Nullable<string>;
};

export type ToolExecutionCompletedEvent = RunnerBaseEvent<'ToolExecutionCompleted'> & {
  tool_name?: Nullable<string>;
  tool_input?: unknown;
  output?: unknown;
  is_error?: Nullable<boolean>;
  tool_use_id?: Nullable<string>;
};

export type RunnerReadyEvent = RunnerBaseEvent<'RunnerReady'> & {
  model?: Nullable<string>;
  cwd?: Nullable<string>;
};

export type RunnerStatusEvent = RunnerBaseEvent<'RunnerStatus'> & {
  running?: Nullable<boolean>;
  processRunning?: Nullable<boolean>;
  lifecycle?: Nullable<RunnerLifecycleState>;
  state?: Nullable<RunnerLifecycleState>;
  runtimeMode?: Nullable<string>;
  daemonPort?: Nullable<number>;
  lastDiagnostic?: RunnerEvent;
};

export type RunnerDiagnosticEvent = RunnerBaseEvent<'RunnerDiagnostic'> & {
  code?: Nullable<string>;
  message?: Nullable<string>;
  state?: Nullable<RunnerLifecycleState>;
};

export type PermissionRequestEvent = RunnerBaseEvent<'PermissionRequest'> & {
  request_id?: Nullable<string>;
  run_id?: Nullable<string>;
  tool_name?: Nullable<string>;
  message?: Nullable<string>;
};

export type SessionSummary = {
  name: string;
  current?: boolean;
  source?: string;
  [key: string]: unknown;
};

export type KnownRunnerEvent =
  | AssistantTextDeltaEvent
  | AssistantTurnCompleteEvent
  | AgentLoopStatusEvent
  | CompactProgressEvent
  | ToolExecutionStartedEvent
  | ToolExecutionCompletedEvent
  | RunnerReadyEvent
  | RunnerBaseEvent<'RunnerStarting'>
  | RunnerStatusEvent
  | RunnerDiagnosticEvent
  | RunnerBaseEvent<'RunnerLifecycle'>
  | RunnerBaseEvent<'RunnerHeartbeat'>
  | RunnerBaseEvent<'RunnerExited'>
  | RunnerBaseEvent<'RunnerStopped'>
  | RunnerBaseEvent<'RunnerError'>
  | RunnerBaseEvent<'ErrorEvent'>
  | RunnerBaseEvent<'StatusEvent'>
  | PermissionRequestEvent
  | (RunnerBaseEvent<'filesResult'> & { files?: string[] })
  | (RunnerBaseEvent<'PlanDraftedEvent'> & { structured_plan?: JsonObject })
  | (RunnerBaseEvent<'PlanReviewEvent'> & { action?: string })
  | (RunnerBaseEvent<'SessionListEvent'> & { current?: string; sessions?: SessionSummary[] })
  | (RunnerBaseEvent<'SessionChangedEvent'> & { current?: string; history?: unknown[] })
  | (RunnerBaseEvent<'SessionExportedEvent'> & { name?: string; format?: string; content?: string })
  | (RunnerBaseEvent<'workspaceInfo'> & { name?: string; path?: string })
  | (RunnerBaseEvent<'activeFileChanged'> & { file?: string; line?: number })
  | (RunnerBaseEvent<'customToolsLoaded'> & { tools?: unknown[] })
  | (RunnerBaseEvent<'customToolsChanged'> & { action?: string; file?: string; validation?: unknown })
  | (RunnerBaseEvent<'customToolValidation'> & { success?: boolean })
  | (RunnerBaseEvent<'assetSaved'> & { path?: string })
  | RunnerBaseEvent<'assetSaveFailed'>
  | (RunnerBaseEvent<'settingsChanged'> & { restartRequired?: boolean })
  | RunnerBaseEvent<'ClearChat'>
  | (RunnerBaseEvent<'injectText'> & { autoSubmit?: boolean });

export type UnknownRunnerEvent = RunnerBaseEvent<string>;

export type RunnerEvent = KnownRunnerEvent | UnknownRunnerEvent;

export type HostToWebviewMessage =
  | { type: 'runnerEvent'; event: RunnerEvent }
  | { type: 'diagnostic'; diagnostic: RunnerEvent }
  | { type: 'historySnapshot'; history: unknown[] }
  | { type: 'sessionState'; state: RunnerEvent }
  | { type: 'transientNotice'; message: string; tone?: string }
  | { type: 'visibilityChanged'; visible: boolean }
  | { type: 'fullState'; state: JsonObject };

type EmptyWebviewCommand = {
  type:
    | 'init'
    | 'attachSession'
    | 'getStatus'
    | 'getRunnerStatus'
    | 'getSessions'
    | 'launchSession'
    | 'start'
    | 'stopSession'
    | 'stop'
    | 'interruptSession'
    | 'stopGen'
    | 'getWorkspaceName'
    | 'getActiveFile'
    | 'getCustomTools';
};

export type WebviewToHostMessage =
  | EmptyWebviewCommand
  | { type: 'visibilityChanged'; visible?: boolean }
  | { type: 'send' | 'sendInput'; text?: string }
  | { type: 'setMode'; mode?: string }
  | { type: 'sendWithMode'; mode?: string; text?: string }
  | { type: 'newSession' | 'switchSession'; name?: string }
  | { type: 'renameSession'; oldName?: string; newName?: string }
  | { type: 'exportSession'; name?: string; format?: string }
  | { type: 'reviewPlan'; action?: string }
  | { type: 'openPlanPreview'; plan?: JsonObject }
  | { type: 'getFiles'; query?: string }
  | { type: 'updateToolPermission'; metadataPath?: string; permissionLevel?: unknown }
  | { type: 'savePastedImage'; name?: string; data?: unknown }
  | { type: 'openFile'; path?: string }
  | { type: 'openGeneratedTool' | 'openDiff'; event?: RunnerEvent };

const WEBVIEW_TO_HOST_MESSAGE_TYPES = new Set([
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
  'getFiles',
  'getWorkspaceName',
  'getActiveFile',
  'getCustomTools',
  'updateToolPermission',
  'savePastedImage',
  'openFile',
  'openGeneratedTool',
  'openDiff',
]);

const HOST_TO_WEBVIEW_MESSAGE_TYPES = new Set([
  'runnerEvent',
  'diagnostic',
  'historySnapshot',
  'sessionState',
  'transientNotice',
  'visibilityChanged',
  'fullState',
]);

const KNOWN_RUNNER_EVENT_TYPES = new Set([
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
  'PlanReviewEvent',
  'SessionListEvent',
  'SessionChangedEvent',
  'SessionExportedEvent',
  'workspaceInfo',
  'activeFileChanged',
  'customToolsLoaded',
  'customToolsChanged',
  'customToolValidation',
  'assetSaved',
  'assetSaveFailed',
  'settingsChanged',
  'ClearChat',
  'injectText',
]);

function isObject(value: unknown): value is JsonObject {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isMissing(value: unknown): boolean {
  return value === undefined || value === null;
}

function optionalString(value: unknown): boolean {
  return isMissing(value) || typeof value === 'string';
}

function optionalBoolean(value: unknown): boolean {
  return isMissing(value) || typeof value === 'boolean';
}

function optionalNumber(value: unknown): boolean {
  return isMissing(value) || typeof value === 'number';
}

function optionalStringArray(value: unknown): boolean {
  return isMissing(value) || (Array.isArray(value) && value.every(item => typeof item === 'string'));
}

function isKnownRunnerEventShape(value: JsonObject, type: string): boolean {
  switch (type) {
    case 'AssistantTextDelta':
      return optionalString(value.text);
    case 'AgentLoopStatus':
      return optionalString(value.phase) && optionalNumber(value.turn) && optionalNumber(value.tool_count);
    case 'CompactProgressEvent':
      return optionalString(value.phase) && optionalString(value.trigger) && optionalString(value.message);
    case 'ToolExecutionStarted':
      return optionalString(value.tool_name);
    case 'ToolExecutionCompleted':
      return optionalString(value.tool_name) && optionalBoolean(value.is_error);
    case 'RunnerReady':
      return optionalString(value.model) && optionalString(value.cwd);
    case 'RunnerStatus':
      return optionalBoolean(value.running)
        && optionalBoolean(value.processRunning)
        && optionalString(value.lifecycle)
        && optionalString(value.state)
        && optionalNumber(value.daemonPort);
    case 'RunnerDiagnostic':
    case 'RunnerError':
    case 'ErrorEvent':
    case 'StatusEvent':
    case 'PermissionRequest':
      return optionalString(value.message);
    case 'filesResult':
      return optionalStringArray(value.files);
    case 'SessionListEvent':
      return isMissing(value.sessions) || Array.isArray(value.sessions);
    case 'SessionChangedEvent':
      return optionalString(value.current) && (isMissing(value.history) || Array.isArray(value.history));
    case 'SessionExportedEvent':
      return optionalString(value.name) && optionalString(value.format) && optionalString(value.content);
    case 'workspaceInfo':
      return optionalString(value.name) && optionalString(value.path);
    case 'activeFileChanged':
      return optionalString(value.file) && optionalNumber(value.line);
    case 'customToolsLoaded':
      return value.tools === undefined || Array.isArray(value.tools);
    case 'customToolValidation':
      return optionalBoolean(value.success) && optionalString(value.message);
    case 'assetSaved':
      return optionalString(value.path);
    case 'assetSaveFailed':
      return optionalString(value.message);
    case 'settingsChanged':
      return optionalBoolean(value.restartRequired);
    case 'injectText':
      return optionalString(value.text) && optionalBoolean(value.autoSubmit);
    default:
      return true;
  }
}

export function asRunnerEvent(value: unknown): RunnerEvent | undefined {
  if (!isObject(value)) return undefined;
  const type = value.type;
  if (typeof type !== 'string' || !type) return undefined;
  if (KNOWN_RUNNER_EVENT_TYPES.has(type) && !isKnownRunnerEventShape(value, type)) return undefined;
  return value as RunnerEvent;
}

export function asHostToWebviewMessage(value: unknown): HostToWebviewMessage | undefined {
  if (!isObject(value)) return undefined;
  const type = value.type;
  if (typeof type !== 'string' || !HOST_TO_WEBVIEW_MESSAGE_TYPES.has(type)) return undefined;
  switch (type) {
    case 'runnerEvent': {
      const event = asRunnerEvent(value.event);
      return event ? { type, event } : undefined;
    }
    case 'diagnostic': {
      const diagnostic = asRunnerEvent(value.diagnostic);
      return diagnostic ? { type, diagnostic } : undefined;
    }
    case 'sessionState': {
      const state = asRunnerEvent(value.state);
      return state ? { type, state } : undefined;
    }
    case 'historySnapshot':
      return Array.isArray(value.history) ? value as HostToWebviewMessage : undefined;
    case 'transientNotice':
      return typeof value.message === 'string' ? value as HostToWebviewMessage : undefined;
    case 'visibilityChanged':
      return typeof value.visible === 'boolean' ? value as HostToWebviewMessage : undefined;
    case 'fullState':
      return isObject(value.state) ? value as HostToWebviewMessage : undefined;
    default:
      return undefined;
  }
}

export function asWebviewToHostMessage(value: unknown): WebviewToHostMessage | undefined {
  if (!isObject(value)) return undefined;
  const type = value.type;
  if (typeof type !== 'string' || !WEBVIEW_TO_HOST_MESSAGE_TYPES.has(type)) return undefined;
  if ((type === 'openGeneratedTool' || type === 'openDiff') && value.event !== undefined && !asRunnerEvent(value.event)) {
    return undefined;
  }
  if (type === 'openPlanPreview' && value.plan !== undefined && !isObject(value.plan)) {
    return undefined;
  }
  return value as WebviewToHostMessage;
}
