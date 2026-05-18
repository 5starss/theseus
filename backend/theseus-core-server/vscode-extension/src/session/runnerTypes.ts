import type * as cp from 'child_process';

export type RunnerRuntimeMode = 'local-daemon' | 'stdio' | 'bundled-daemon' | 'bundled-stdio';

export const RUNNER_STATE_SCHEMA_VERSION = 1;

export type TheseusSessionMetadata = {
  coreRoot: string;
  workspaceCwd: string;
  pythonExec: string;
  runnerPath?: string;
  serverUrl: string;
  initialSession?: string;
  runtimeMode?: RunnerRuntimeMode;
  daemonHost?: string;
  daemonPort?: number;
  daemonToken?: string;
};

export type DaemonRunnerState = {
  schemaVersion?: number;
  pid?: number;
  port?: number;
  host?: string;
  token?: string;
  mode?: string;
  model?: string;
  sessionId?: string;
  session?: string;
  workspaceHash?: string;
  workspaceCwd?: string;
  coreRoot?: string;
  startedAt?: string;
};

export type DaemonRunStatus = {
  runId?: string;
  status?: string;
  createdAt?: number;
  updatedAt?: number;
  eventCount?: number;
  eventOffset?: number;
  interruptRequested?: boolean;
};

export type DaemonStatus = {
  schemaVersion?: number;
  mode?: string;
  pid?: number;
  model?: string;
  sessionId?: string;
  workspaceHash?: string;
  workspaceCwd?: string;
  startedAt?: number | string;
  lastEventAt?: number;
  session?: string;
  runs?: DaemonRunStatus[];
};

export type RunnerStartConfig = {
  coreRoot: string;
  workspaceCwd: string;
  pythonExec: string;
  runnerPath?: string;
  serverUrl: string;
  initialSession?: string;
  signal?: AbortSignal;
};

export interface RunnerClient {
  readonly mode: RunnerRuntimeMode;
}

export type RunnerProcess = cp.ChildProcessWithoutNullStreams;
