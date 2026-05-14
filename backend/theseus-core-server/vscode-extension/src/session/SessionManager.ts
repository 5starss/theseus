import * as vscode from 'vscode';

import { asRunnerEvent, type RunnerEvent } from '../shared/protocol';
import { DaemonRunnerClient, errorMessage, isDaemonConnectionError, isDaemonHttpStatus, sameWorkspacePath } from './DaemonRunnerClient';
import { killPidTree } from './ProcessUtils';
import { RunnerStateStore } from './RunnerStateStore';
import { StdioRunnerClient } from './StdioRunnerClient';
import type { DaemonRunStatus, DaemonRunnerState, DaemonStatus, RunnerProcess, RunnerRuntimeMode, TheseusSessionMetadata } from './runnerTypes';
// ── Session manager ─────────────────────────────────────────────────

type TheseusSessionState =
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'busy'
  | 'waiting_input'
  | 'stale'
  | 'exited'
  | 'error';

type TheseusDiagnosticCode =
  | 'spawn_failed'
  | 'ready_timeout'
  | 'python_import_failed'
  | 'user_stop'
  | 'crash_exit'
  | 'runner_error'
  | 'json_parse_error'
  | 'send_failed'
  | 'daemon_busy'
  | 'event_replay_gap';

type PendingInput = {
  text: string;
  mode?: string;
};

type ResolvedRuntimeConfig = {
  pythonExec: string;
  runnerPath: string;
  serverUrl: string;
  daemonMode: RunnerRuntimeMode;
  stdioMode: RunnerRuntimeMode;
};

const READY_TIMEOUT_MS = 25000;
const HEARTBEAT_STALE_MS = 45000;
const DAEMON_HEARTBEAT_INTERVAL_MS = 5000;
const DAEMON_HEARTBEAT_FAILURE_LIMIT = 2;
const DAEMON_SSE_RECONNECT_MAX = 5;
const DAEMON_SSE_RECONNECT_BASE_MS = 750;
const LIFECYCLE_HISTORY_LIMIT = 100;
const SESSION_STATE_KEY = 'theseus.lastActiveSession';
const SELECTED_SESSION_KEY = 'theseus.selectedLocalSession';
const TERMINAL_DAEMON_RUN_STATUSES = new Set(['completed', 'interrupted', 'error']);
const EXPECTED_STOP_REASONS = new Set(['user_stop', 'restart', 'extension_dispose', 'daemon_connection_lost', 'worktree_changed']);

function nowIso(): string {
  return new Date().toISOString();
}

function makeSessionId(): string {
  return `theseus-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeSessionName(name: string | undefined): string {
  const clean = String(name || '').trim();
  return clean && /^[A-Za-z0-9]+$/.test(clean) ? clean : 'default';
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function isExpectedStopReason(reason: string | undefined): boolean {
  return !!reason && EXPECTED_STOP_REASONS.has(reason);
}

function classifyProcessFailure(stderr: string, code: number | null): TheseusDiagnosticCode {
  if (/ModuleNotFoundError|ImportError|No module named/i.test(stderr)) return 'python_import_failed';
  return code === 0 || code === null ? 'runner_error' : 'crash_exit';
}

export class TheseusSessionManager implements vscode.Disposable {
  private proc: RunnerProcess | undefined;
  private abortController: AbortController | undefined;
  private readyTimer: NodeJS.Timeout | undefined;
  private heartbeatTimer: NodeJS.Timeout | undefined;
  private readonly listeners = new Set<(event: RunnerEvent) => void>();
  private readonly lifecycleHistory: RunnerEvent[] = [];
  private readonly pendingInput: PendingInput[] = [];
  private state: TheseusSessionState = 'stopped';
  private sessionId = makeSessionId();
  private lastReadyEvent: RunnerEvent | undefined;
  private lastEventAt: number | undefined;
  private lastHeartbeatAt: number | undefined;
  private exitReason: string | undefined;
  private startMetadata: TheseusSessionMetadata | undefined;
  private lastDiagnostic: RunnerEvent | undefined;
  private jsonParseErrorCount = 0;
  private runtimeMode: RunnerRuntimeMode = 'local-daemon';
  private daemon: DaemonRunnerState | undefined;
  private activeRunId: string | undefined;
  private activeRunEventCount = 0;
  private daemonHeartbeatFailures = 0;
  private daemonStreamReconnectAttempt = 0;
  private daemonSendQueue: Promise<void> = Promise.resolve();
  private readonly daemonReplayGapWarnings = new Set<string>();
  private readonly permissionRequestsHandled = new Set<string>();
  // 마지막으로 runner에 송신한 mode. 같은 mode 재전송 시 runner가 매번
  // "✅ ... 모드로 전환됐습니다." 를 다시 발행하지 않도록 익스텐션이 dedupe한다.
  private lastSentMode: string | undefined;
  private preferredSession = 'default';

  readonly output = vscode.window.createOutputChannel('Theseus');
  private readonly daemonClient = new DaemonRunnerClient(this.output);
  private readonly stdioClient = new StdioRunnerClient(this.output);
  private readonly runnerState = new RunnerStateStore(this.output);

  constructor(private readonly context: vscode.ExtensionContext) {
    const previous = this.context.workspaceState.get<Partial<TheseusSessionMetadata> & { sessionId?: string }>(SESSION_STATE_KEY);
    if (previous?.sessionId) this.sessionId = previous.sessionId;
    const selected = this.context.workspaceState.get<string>(SELECTED_SESSION_KEY);
    if (selected?.trim()) this.preferredSession = normalizeSessionName(selected);
  }

  get hasProcess(): boolean { return !!this.proc || !!this.daemon; }
  get isRunning(): boolean { return ['ready', 'busy', 'waiting_input'].includes(this.state); }
  get currentState(): TheseusSessionState { return this.state; }
  get preferredSessionName(): string { return this.preferredSession || 'default'; }

  setPreferredSession(name: string): void {
    const clean = normalizeSessionName(name);
    if (clean === this.preferredSession) return;
    this.preferredSession = clean;
    void this.context.workspaceState.update(SELECTED_SESSION_KEY, clean);
  }

  private resolveRuntimeConfig(): ResolvedRuntimeConfig {
    const config = vscode.workspace.getConfiguration('theseus');
    const pythonExec = config.get<string>('pythonPath') || 'python';
    const configuredRunnerPath = config.get<string>('runnerPath')?.trim() || '';
    const runtimeModeSetting = config.get<string>('runtimeMode')?.trim();
    const useBundledRunner = !!configuredRunnerPath && runtimeModeSetting !== 'source-python';
    const runnerPath = useBundledRunner ? configuredRunnerPath : '';
    return {
      pythonExec,
      runnerPath,
      serverUrl: config.get<string>('serverUrl') || '',
      daemonMode: useBundledRunner ? 'bundled-daemon' : 'local-daemon',
      stdioMode: useBundledRunner ? 'bundled-stdio' : 'stdio',
    };
  }

  get status(): RunnerEvent {
    const processRunning = this.hasProcess;
    const attachableStdio = !!this.proc && !this.daemon && processRunning && !!this.lastReadyEvent;
    const effectiveState = this.state === 'stale' && attachableStdio ? 'ready' : this.state;
    const lifecycle = effectiveState === 'stale' && processRunning ? 'starting_stale' : effectiveState;
    return {
      type: 'RunnerStatus',
      running: ['ready', 'busy', 'waiting_input'].includes(effectiveState),
      processRunning,
      lifecycle,
      state: effectiveState,
      sessionId: this.sessionId,
      model: this.lastReadyEvent?.model,
      cwd: this.lastReadyEvent?.cwd || this.startMetadata?.workspaceCwd,
      pythonExec: this.startMetadata?.pythonExec,
      runnerPath: this.startMetadata?.runnerPath,
      coreRoot: this.startMetadata?.coreRoot,
      workspaceCwd: this.startMetadata?.workspaceCwd,
      runtimeMode: this.runtimeMode,
      daemonPid: this.daemon?.pid ?? this.proc?.pid,
      daemonPort: this.daemon?.port,
      session: this.lastReadyEvent?.session || this.preferredSessionName,
      lastEventAt: this.lastEventAt,
      lastHeartbeatAt: this.lastHeartbeatAt,
      exitReason: this.exitReason,
      pendingInput: this.pendingInput.length,
      lastDiagnostic: this.lastDiagnostic,
    };
  }

  get historySnapshot(): RunnerEvent[] {
    return [...this.lifecycleHistory];
  }

  onEvent(listener: (event: RunnerEvent) => void): vscode.Disposable {
    this.listeners.add(listener);
    return new vscode.Disposable(() => this.listeners.delete(listener));
  }

  /**
   * Ensure the single active Extension Host-owned session exists.
   * Healthy Python processes are reused; attachable stale processes are revived on Start.
   */
  async ensureSession(coreRoot: string, workspaceCwd: string): Promise<void> {
    if (this.daemon) {
      if (await this.pollDaemonStatus({ emitStatus: false })) {
        this.flushPendingInput();
        this.emit(this.status);
        return;
      }
      this.output.appendLine('[Theseus] existing local daemon failed status check on Start; restarting daemon');
      this.logLifecycle('restart_unhealthy_daemon', { state: this.state });
      this.resetDaemonConnection('daemon_status_failed_on_start');
    }
    if (await this.attachExistingDaemon(workspaceCwd, coreRoot)) {
      this.emit(this.status);
      return;
    }
    if (!this.proc) {
      await this.startDaemon(coreRoot, workspaceCwd);
      if (this.daemon) return;
      const failedDaemonProc = this.proc as RunnerProcess | undefined;
      this.proc = undefined;
      if (failedDaemonProc && !failedDaemonProc.killed) failedDaemonProc.kill();
      this.output.appendLine('[Theseus] local daemon unavailable; falling back to stdio runner');
      this.emitDiagnostic('runner_error', 'Local daemon failed to start. Falling back to stdio runner.');
    }

    if (this.proc) {
      this.logLifecycle('attach_existing_process', { state: this.state });

      if (this.reviveReadyIfAttachable('ensure_session')) {
        this.emit(this.status);
        return;
      }

      if (['ready', 'busy', 'waiting_input', 'starting'].includes(this.state)) {
        this.emit(this.status);
        return;
      }

      if (this.state === 'stale' || this.state === 'error') {
        this.output.appendLine(`[Theseus] unhealthy state on Start: ${this.state}; restarting process`);
        this.logLifecycle('restart_unhealthy_process', { state: this.state });
        void this.restart(coreRoot, workspaceCwd);
        return;
      }

      this.logLifecycle('attach_existing_process_unknown_state', { state: this.state });
      this.emit(this.status);
      return;
    }
    this.startStdio(coreRoot, workspaceCwd);
  }

  reattachIfPossible(reason = 'reattach'): boolean {
    return this.reviveReadyIfAttachable(reason);
  }

  async restart(coreRoot: string, workspaceCwd: string): Promise<void> {
    this.stop('restart');
    await this.ensureSession(coreRoot, workspaceCwd);
  }

  stop(reason = 'user_stop'): void {
    this.clearTimers();
    this.exitReason = reason;
    const proc = this.proc;
    this.proc = undefined;
    const daemonPid = this.daemon?.pid;
    this.daemon = undefined;
    this.abortController?.abort();
    this.activeRunId = undefined;
    this.activeRunEventCount = 0;
    this.daemonHeartbeatFailures = 0;
    this.daemonStreamReconnectAttempt = 0;
    this.daemonReplayGapWarnings.clear();
    this.permissionRequestsHandled.clear();
    this.lastReadyEvent = undefined;
    this.pendingInput.length = 0;
    this.lastSentMode = undefined; // runner 재시작 시 다음 첫 send에서 mode 재동기화
    this.removeRunnerPid(proc?.pid ?? daemonPid);
    this.setState('stopped', { code: 'user_stop', reason });
    if (proc && !proc.killed) proc.kill();
    if (daemonPid) killPidTree(daemonPid);
    this.emit({ type: 'RunnerStopped', code: 'user_stop', reason });
  }

  interrupt(): void {
    if (this.daemon && this.activeRunId) {
      void this.daemonClient.request(this.daemon, 'POST', `/runs/${this.activeRunId}/interrupt`).then(() => {
        this.emitDiagnostic('user_stop', 'Interrupt requested.');
      }).catch((err) => this.emitDiagnostic('send_failed', err instanceof Error ? err.message : String(err)));
      return;
    }
    if (!this.proc) {
      this.emitDiagnostic('send_failed', 'Runner is not running. Press Start.');
      return;
    }
    this.proc.stdin.write(JSON.stringify({ type: 'interrupt' }) + '\n');
    this.emitDiagnostic('user_stop', 'Interrupt requested.');
  }

  private async handlePermissionRequest(event: RunnerEvent): Promise<void> {
    const requestId = typeof event.request_id === 'string'
      ? event.request_id
      : typeof event.requestId === 'string'
        ? event.requestId
        : '';
    if (!requestId) {
      this.output.appendLine('[Theseus] permission request ignored: missing request_id');
      return;
    }
    if (this.permissionRequestsHandled.has(requestId)) return;
    this.permissionRequestsHandled.add(requestId);

    const toolName = typeof event.tool_name === 'string' ? event.tool_name : '';
    const reason = typeof event.message === 'string' ? event.message : '';
    const detail = [toolName ? `도구: ${toolName}` : '', reason].filter(Boolean).join('\n\n');
    const allowLabel = '허용';
    const denyLabel = '거부';
    const choice = await vscode.window.showWarningMessage(
      `Theseus가 도구 실행 권한을 요청했습니다.${detail ? `\n\n${detail}` : ''}`,
      { modal: true },
      allowLabel,
      denyLabel,
    );
    const approved = choice === allowLabel;
    try {
      await this.sendPermissionResponse(event, approved);
      this.output.appendLine(`[Theseus] permission ${approved ? 'approved' : 'denied'} request=${requestId}`);
    } catch (err) {
      const message = `권한 응답 전송 실패: ${errorMessage(err)}`;
      this.output.appendLine(`[Theseus] ${message}`);
      this.emitDiagnostic('send_failed', message);
    }
  }

  private async sendPermissionResponse(event: RunnerEvent, approved: boolean): Promise<void> {
    const requestId = typeof event.request_id === 'string'
      ? event.request_id
      : typeof event.requestId === 'string'
        ? event.requestId
        : '';
    if (!requestId) throw new Error('Permission request_id is missing.');

    if (this.daemon) {
      const runId = typeof event.run_id === 'string'
        ? event.run_id
        : typeof event.runId === 'string'
          ? event.runId
          : this.activeRunId;
      if (!runId) throw new Error('Permission run_id is missing.');
      await this.daemonClient.request(
        this.daemon,
        'POST',
        `/runs/${encodeURIComponent(runId)}/permissions/${encodeURIComponent(requestId)}`,
        { approved },
      );
      return;
    }

    if (!this.proc) throw new Error('Runner is not running.');
    this.writeLine(JSON.stringify({ type: 'PermissionResponse', request_id: requestId, approved }));
  }

  send(text: string, mode?: string): void {
    const normalized = text.trim();
    if (!normalized) return;
    // 동일 mode 재전송 시 runner의 mode-switch 알림을 억제하기 위해 mode 인자를 비운다
    const effectiveMode = mode && mode !== this.lastSentMode ? mode : undefined;
    if (this.daemon) {
      if (this.state === 'starting' || this.state === 'stale') {
        this.pendingInput.push({ text: normalized, mode });
        this.emit(this.status);
        return;
      }
      // 낙관적으로 commit 후, sendDaemon 실패 시 rollback해 다음 send에서 mode 재동기화
      const prevSentMode = this.lastSentMode;
      if (effectiveMode) this.lastSentMode = effectiveMode;
      void this.sendDaemon(normalized, effectiveMode).then(success => {
        if (!success) this.lastSentMode = prevSentMode;
      });
      return;
    }
    if (!this.proc) {
      this.emitDiagnostic('send_failed', 'Runner is not running. Press Start.');
      return;
    }
    if (this.state === 'starting' || this.state === 'stale') {
      this.pendingInput.push({ text: normalized, mode });
      this.emit(this.status);
      return;
    }
    if (effectiveMode) {
      this.writeLine(JSON.stringify({ type: 'setMode', mode: effectiveMode }));
      this.lastSentMode = effectiveMode;
    }
    this.writeLine(normalized);
    this.setState('busy');
  }

  setMode(mode: string): void {
    // 이미 같은 mode면 runner에 재전송하지 않음 (전환 알림 스팸 방지)
    if (mode === this.lastSentMode) return;
    if (this.daemon) {
      const previousMode = this.lastSentMode;
      this.lastSentMode = mode;
      void this.sendDaemon(JSON.stringify({ type: 'setMode', mode })).then(success => {
        if (!success) this.lastSentMode = previousMode;
      });
      return;
    }
    if (!this.proc) {
      this.emitDiagnostic('send_failed', 'Runner is not running. Press Start.');
      return;
    }
    this.writeLine(JSON.stringify({ type: 'setMode', mode }));
    this.lastSentMode = mode;
  }

  showLogs(): void {
    this.output.show(true);
    this.output.appendLine('[Theseus] === Recent lifecycle events ===');
    for (const event of this.lifecycleHistory) {
      this.output.appendLine(JSON.stringify(event));
    }
  }

  dispose(): void {
    this.stop('extension_dispose');
    this.output.dispose();
  }

  private async startDaemon(coreRoot: string, workspaceCwd: string): Promise<void> {
    this.cleanupOrphanRunner(workspaceCwd);

    const runtimeConfig = this.resolveRuntimeConfig();
    const { pythonExec, runnerPath, serverUrl } = runtimeConfig;
    const runtimeMode = runtimeConfig.daemonMode;

    this.runtimeMode = runtimeMode;
    this.sessionId = makeSessionId();
    this.startMetadata = { coreRoot, workspaceCwd, pythonExec, runnerPath, serverUrl, runtimeMode, initialSession: this.preferredSessionName };
    this.lastReadyEvent = undefined;
    this.lastDiagnostic = undefined;
    this.exitReason = undefined;
    this.permissionRequestsHandled.clear();
    this.abortController = new AbortController();
    this.context.workspaceState.update(SESSION_STATE_KEY, { ...this.startMetadata, sessionId: this.sessionId });

    this.output.appendLine(`[Theseus] === Starting local daemon === session=${this.sessionId}`);
    this.output.appendLine(`[Theseus] core   : ${coreRoot}`);
    this.output.appendLine(`[Theseus] cwd    : ${workspaceCwd}`);
    this.output.appendLine(`[Theseus] python : ${pythonExec}`);
    if (runnerPath) this.output.appendLine(`[Theseus] runner : ${runnerPath}`);
    this.setState('starting');
    this.emit({ type: 'RunnerStarting', sessionId: this.sessionId, runtimeMode });
    this.startReadyTimeout();

    try {
      this.proc = this.daemonClient.startProcess({
        coreRoot,
        workspaceCwd,
        pythonExec,
        runnerPath,
        serverUrl,
        initialSession: this.preferredSessionName,
        signal: this.abortController.signal,
      });
    } catch (err) {
      this.proc = undefined;
      if (isExpectedStopReason(this.exitReason) || this.abortController.signal.aborted) {
        this.output.appendLine(`[Theseus] ignored expected daemon spawn abort: ${err instanceof Error ? err.message : String(err)}`);
        return;
      }
      this.setState('error', { code: 'spawn_failed' });
      this.emitDiagnostic('spawn_failed', `Failed to start local daemon: ${err instanceof Error ? err.message : String(err)}`);
      return;
    }

    const child = this.proc;
    let stderrBuf = '';
    child.stdout.on('data', (chunk: Buffer) => this.output.append(chunk.toString()));
    child.stderr.on('data', (chunk: Buffer) => {
      const text = chunk.toString();
      stderrBuf += text;
      this.output.append(text);
    });
    child.on('exit', (code, signal) => {
      if (this.proc !== child) {
        this.output.appendLine(`[Theseus] ignored stale daemon exit code: ${code}${signal ? ` signal: ${signal}` : ''}`);
        return;
      }
      this.clearTimers();
      this.proc = undefined;
      this.daemon = undefined;
      this.lastReadyEvent = undefined;
      this.output.appendLine(`[Theseus] daemon exit code: ${code}${signal ? ` signal: ${signal}` : ''}`);
      if (isExpectedStopReason(this.exitReason)) return;
      this.exitReason = signal ? `signal:${signal}` : `code:${code}`;
      if (code !== 0 && code !== null && stderrBuf.trim()) {
        const diagnosticCode = classifyProcessFailure(stderrBuf, code);
        this.setState('error', { code: diagnosticCode });
        this.emitDiagnostic(diagnosticCode, `Daemon exited (code ${code}):\n${stderrBuf.trim()}`);
      } else {
        this.setState('exited');
        this.emit({ type: 'RunnerExited', code, signal: signal || undefined });
      }
    });

    const attached = await this.waitForDaemonAttach(workspaceCwd, coreRoot, child.pid);
    if (!attached) {
      this.setState('error', { code: 'ready_timeout' });
      this.emitDiagnostic('ready_timeout', 'Local daemon did not become healthy before timeout.');
    }
  }

  private async waitForDaemonAttach(workspaceCwd: string, coreRoot: string, expectedPid?: number): Promise<boolean> {
    const deadline = Date.now() + READY_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (await this.attachExistingDaemon(workspaceCwd, coreRoot, expectedPid)) return true;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    return false;
  }

  private async attachExistingDaemon(workspaceCwd: string, coreRoot: string, expectedPid?: number): Promise<boolean> {
    const state = this.runnerState.readDaemon(workspaceCwd, { coreRoot });
    if (!state || state.mode !== 'local-daemon' || !state.port || !state.token) return false;
    if (expectedPid && state.pid && state.pid !== expectedPid) return false;
    if (state.workspaceCwd && !sameWorkspacePath(state.workspaceCwd, workspaceCwd)) return false;

    const previousDaemon = this.daemon;
    this.daemon = { ...state, host: state.host || '127.0.0.1' };
    try {
      const status = await this.daemonClient.status(this.daemon);
      const runtimeConfig = this.resolveRuntimeConfig();
      const { runnerPath, serverUrl, pythonExec } = runtimeConfig;
      const runtimeMode = runtimeConfig.daemonMode;
      this.runtimeMode = runtimeMode;
      this.lastReadyEvent = {
        type: 'RunnerReady',
        mode: runtimeMode,
        model: typeof status.model === 'string' ? status.model : undefined,
        cwd: String(status.workspaceCwd || workspaceCwd),
        session: typeof status.session === 'string' ? status.session : 'default',
        sessionId: this.sessionId,
      };
      this.startMetadata = {
        ...(this.startMetadata || {
          pythonExec,
          runnerPath,
          serverUrl,
        }),
        coreRoot,
        workspaceCwd,
        initialSession: this.preferredSessionName,
        runnerPath,
        runtimeMode,
        daemonHost: this.daemon.host,
        daemonPort: this.daemon.port,
        daemonToken: this.daemon.token,
      };
      this.applyDaemonStatus(status);
      this.clearTimers();
      this.startHeartbeatMonitor();
      this.setState(this.pendingInput.length ? 'waiting_input' : 'ready');
      this.flushPendingInput();
      this.output.appendLine(`[Theseus] attached local daemon pid=${state.pid} port=${state.port} session=${state.sessionId || 'unknown'}`);
      return true;
    } catch (err) {
      this.daemon = previousDaemon;
      this.output.appendLine(`[Theseus] daemon attach failed: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    }
  }

  private async sendDaemon(text: string, mode?: string): Promise<boolean> {
    const queued = this.daemonSendQueue.then(() => this.sendDaemonNow(text, mode));
    this.daemonSendQueue = queued.then(() => undefined, () => undefined);
    return queued;
  }

  private async sendDaemonNow(text: string, mode?: string): Promise<boolean> {
    if (!this.daemon) {
      return false;
    }
    let keepBusyState = false;
    try {
      this.setState('busy');
      const created = await this.daemonClient.request(this.daemon, 'POST', '/runs', mode ? { text, mode } : { text });
      const runId = String(created.runId || '');
      if (!runId) throw new Error('Daemon did not return runId.');
      this.activeRunId = runId;
      this.activeRunEventCount = 0;
      this.daemonStreamReconnectAttempt = 0;
      this.daemonReplayGapWarnings.clear();
      await this.streamDaemonRun(runId);
    } catch (err) {
      if (isDaemonConnectionError(err)) {
        this.markDaemonConnectionLost(errorMessage(err));
        return false;
      }
      if (isDaemonHttpStatus(err, 409)) {
        keepBusyState = true;
        const message = err.detail || 'Local daemon already has an active run.';
        this.output.appendLine(`[Theseus] daemon busy: ${message}`);
        this.logLifecycle('daemon_busy', { message });
        this.setState('busy', { code: 'daemon_busy' });
        this.emitDiagnostic('daemon_busy', message);
        await this.pollDaemonStatus({ emitStatus: true });
        return false;
      }
      this.setState('error', { code: 'send_failed' });
      this.emitDiagnostic('send_failed', errorMessage(err));
      return false;
    } finally {
      this.activeRunId = undefined;
      this.activeRunEventCount = 0;
      this.daemonStreamReconnectAttempt = 0;
      if (!keepBusyState && this.daemon && this.lastReadyEvent && (this.state === 'busy' || this.state === 'stale')) {
        this.setState(this.pendingInput.length ? 'waiting_input' : 'ready');
        this.flushPendingInput();
      }
    }
    return true;
  }

  private async streamDaemonRun(runId: string): Promise<void> {
    while (this.daemon && this.activeRunId === runId) {
      const daemon = this.daemon;
      try {
        await this.daemonClient.streamEvents(
          daemon,
          runId,
          (event, sequence) => this.recordDaemonEvent(event, sequence),
          { after: this.activeRunEventCount },
        );
        if (await this.isDaemonRunComplete(runId)) return;
        throw Object.assign(new Error('Daemon SSE ended before run completed.'), { code: 'ECONNRESET' });
      } catch (err) {
        if (!isDaemonConnectionError(err) || !this.daemon || this.activeRunId !== runId) throw err;
        this.daemonStreamReconnectAttempt += 1;
        if (this.daemonStreamReconnectAttempt > DAEMON_SSE_RECONNECT_MAX) throw err;

        const delay = DAEMON_SSE_RECONNECT_BASE_MS * this.daemonStreamReconnectAttempt;
        this.logLifecycle('daemon_sse_reconnect', {
          runId,
          after: this.activeRunEventCount,
          attempt: this.daemonStreamReconnectAttempt,
          delay,
          message: errorMessage(err),
        });
        this.setState('stale', {
          code: 'send_failed',
          runId,
          reconnectAttempt: this.daemonStreamReconnectAttempt,
        });
        await sleep(delay);
        await this.pollDaemonStatus({ emitStatus: false });
      }
    }
  }

  private recordDaemonEvent(event: RunnerEvent, sequence?: number): void {
    if (typeof sequence === 'number' && sequence > this.activeRunEventCount + 1 && this.activeRunId) {
      this.reportDaemonReplayGap(this.activeRunId, this.activeRunEventCount + 1, sequence, 'sse_sequence');
    }
    if (typeof sequence === 'number' && sequence > this.activeRunEventCount) {
      this.activeRunEventCount = sequence;
    } else {
      this.activeRunEventCount += 1;
    }
    this.daemonStreamReconnectAttempt = 0;
    this.emit(event);
  }

  private async isDaemonRunComplete(runId: string): Promise<boolean> {
    const status = await this.daemonClient.status(this.daemon);
    this.applyDaemonStatus(status);
    const run = status.runs?.find(item => item.runId === runId);
    if (!run) return true;
    this.detectDaemonReplayGap(run, 'status_check');
    if (typeof run.eventCount === 'number' && run.eventCount > this.activeRunEventCount) {
      this.output.appendLine(`[Theseus] daemon run ${runId} has ${run.eventCount - this.activeRunEventCount} buffered events pending replay`);
      return false;
    }
    return TERMINAL_DAEMON_RUN_STATUSES.has(String(run.status || ''));
  }

  private daemonHasActiveRun(status: DaemonStatus): boolean {
    return !!status.runs?.some(run => !TERMINAL_DAEMON_RUN_STATUSES.has(String(run.status || '')));
  }

  private detectDaemonReplayGap(run: DaemonRunStatus | undefined, source: string): void {
    if (!run?.runId || typeof run.eventOffset !== 'number') return;
    if (this.activeRunId !== run.runId) return;
    if (this.activeRunEventCount >= run.eventOffset) return;
    this.reportDaemonReplayGap(run.runId, this.activeRunEventCount + 1, run.eventOffset + 1, source);
  }

  private reportDaemonReplayGap(runId: string, expectedSequence: number, nextAvailableSequence: number, source: string): void {
    const key = `${runId}:${expectedSequence}:${nextAvailableSequence}`;
    if (this.daemonReplayGapWarnings.has(key)) return;
    this.daemonReplayGapWarnings.add(key);
    const message = `Local daemon replay buffer skipped events for ${runId}. Expected event ${expectedSequence}, next available is ${nextAvailableSequence}. Check the Theseus Output channel for full runner logs.`;
    this.output.appendLine(`[Theseus] daemon replay gap (${source}): ${message}`);
    this.logLifecycle('daemon_replay_gap', { runId, expectedSequence, nextAvailableSequence, source });
    this.emitDiagnostic('event_replay_gap', message);
  }

  private markDaemonConnectionLost(message: string): void {
    this.resetDaemonConnection('daemon_connection_lost');
    this.setState('error', { code: 'send_failed', disconnected: true });
    this.emitDiagnostic('send_failed', `Local daemon connection lost: ${message}. Press Start to reconnect.`);
  }

  private resetDaemonConnection(reason: string): void {
    const proc = this.proc;
    const daemonPid = this.daemon?.pid ?? proc?.pid;
    this.clearTimers();
    this.daemon = undefined;
    this.proc = undefined;
    this.activeRunId = undefined;
    this.activeRunEventCount = 0;
    this.daemonHeartbeatFailures = 0;
    this.daemonStreamReconnectAttempt = 0;
    this.daemonReplayGapWarnings.clear();
    this.lastReadyEvent = undefined;
    this.exitReason = reason;
    this.daemonSendQueue = Promise.resolve();
    this.permissionRequestsHandled.clear();
    this.removeRunnerPid(daemonPid);
    if (daemonPid) {
      killPidTree(daemonPid);
    } else if (proc && !proc.killed) {
      proc.kill();
    }
  }

  private applyDaemonStatus(status: DaemonStatus): void {
    this.daemonHeartbeatFailures = 0;
    this.lastHeartbeatAt = Date.now();
    if (typeof status.session === 'string' && status.session) {
      this.setPreferredSession(status.session);
    }
    const lastEventAt = typeof status.lastEventAt === 'number' ? status.lastEventAt : undefined;
    if (lastEventAt) this.lastEventAt = lastEventAt > 1_000_000_000_000 ? lastEventAt : Math.round(lastEventAt * 1000);
    if (this.daemon) {
      this.daemon = {
        ...this.daemon,
        pid: typeof status.pid === 'number' ? status.pid : this.daemon.pid,
        model: typeof status.model === 'string' ? status.model : this.daemon.model,
        sessionId: typeof status.sessionId === 'string' ? status.sessionId : this.daemon.sessionId,
        workspaceHash: typeof status.workspaceHash === 'string' ? status.workspaceHash : this.daemon.workspaceHash,
        workspaceCwd: typeof status.workspaceCwd === 'string' ? status.workspaceCwd : this.daemon.workspaceCwd,
      };
    }
    this.lastReadyEvent = {
      type: 'RunnerReady',
      mode: 'local-daemon',
      model: typeof status.model === 'string' ? status.model : this.lastReadyEvent?.model,
      cwd: typeof status.workspaceCwd === 'string' ? status.workspaceCwd : this.lastReadyEvent?.cwd,
      session: typeof status.session === 'string' ? status.session : this.lastReadyEvent?.session || 'default',
      sessionId: this.sessionId,
    };
  }

  private async pollDaemonStatus(options: { emitStatus?: boolean } = {}): Promise<boolean> {
    const daemon = this.daemon;
    if (!daemon) return false;
    try {
      const status = await this.daemonClient.status(daemon);
      if (this.daemon !== daemon && this.daemon?.port !== daemon.port) return false;
      this.applyDaemonStatus(status);
      const activeRun = this.activeRunId ? status.runs?.find(item => item.runId === this.activeRunId) : undefined;
      this.detectDaemonReplayGap(activeRun, 'heartbeat');
      if (this.state === 'stale' && this.lastReadyEvent) {
        this.setState(this.activeRunId ? 'busy' : this.pendingInput.length ? 'waiting_input' : 'ready', {
          reason: 'daemon_status_recovered',
        });
        this.flushPendingInput();
      } else if (this.daemon && this.state === 'busy' && !this.activeRunId && !this.daemonHasActiveRun(status)) {
        this.setState(this.pendingInput.length ? 'waiting_input' : 'ready', {
          reason: 'daemon_busy_cleared',
        });
        this.flushPendingInput();
      } else if (options.emitStatus) {
        this.emit(this.status);
      }
      return true;
    } catch (err) {
      if (this.daemon !== daemon && this.daemon?.port !== daemon.port) return false;
      this.daemonHeartbeatFailures += 1;
      this.output.appendLine(`[Theseus] daemon status check failed (${this.daemonHeartbeatFailures}): ${errorMessage(err)}`);
      this.logLifecycle('daemon_heartbeat_failed', {
        failures: this.daemonHeartbeatFailures,
        message: errorMessage(err),
      });
      if (this.daemonHeartbeatFailures >= DAEMON_HEARTBEAT_FAILURE_LIMIT && this.state !== 'stale') {
        this.setState('stale', {
          code: 'ready_timeout',
          failures: this.daemonHeartbeatFailures,
        });
        this.emitDiagnostic(
          'ready_timeout',
          'Local daemon heartbeat is stale. Theseus will try to reuse buffered run events while reconnecting.',
        );
      }
      return false;
    }
  }

  private startStdio(coreRoot: string, workspaceCwd: string): void {
    this.cleanupOrphanRunner(workspaceCwd);

    const runtimeConfig = this.resolveRuntimeConfig();
    const { pythonExec, runnerPath, serverUrl } = runtimeConfig;
    const runtimeMode = runtimeConfig.stdioMode;

    this.runtimeMode = runtimeMode;
    this.sessionId = makeSessionId();
    this.startMetadata = { coreRoot, workspaceCwd, pythonExec, runnerPath, serverUrl, runtimeMode, initialSession: this.preferredSessionName };
    this.lastReadyEvent = undefined;
    this.lastDiagnostic = undefined;
    this.jsonParseErrorCount = 0;
    this.exitReason = undefined;
    this.permissionRequestsHandled.clear();
    this.abortController = new AbortController();
    this.context.workspaceState.update(SESSION_STATE_KEY, { ...this.startMetadata, sessionId: this.sessionId });

    this.output.appendLine(`[Theseus] === Starting === session=${this.sessionId}`);
    this.output.appendLine(`[Theseus] step   : resolve_config`);
    this.output.appendLine(`[Theseus] core   : ${coreRoot}`);
    this.output.appendLine(`[Theseus] cwd    : ${workspaceCwd}`);
    this.output.appendLine(`[Theseus] python : ${pythonExec}`);
    if (runnerPath) this.output.appendLine(`[Theseus] runner : ${runnerPath}`);
    this.output.appendLine(`[Theseus] step   : spawn_python`);

    try {
      this.proc = this.stdioClient.startProcess({
        coreRoot,
        workspaceCwd,
        pythonExec,
        runnerPath,
        serverUrl,
        initialSession: this.preferredSessionName,
        signal: this.abortController.signal,
      });
    } catch (err) {
      this.proc = undefined;
      const message = err instanceof Error ? err.message : String(err);
      if (isExpectedStopReason(this.exitReason) || this.abortController.signal.aborted) {
        this.output.appendLine(`[Theseus] ignored expected stdio spawn abort: ${message}`);
        return;
      }
      this.output.appendLine(`[Theseus] spawn exception: ${message}`);
      this.setState('error', { code: 'spawn_failed' });
      this.emitDiagnostic('spawn_failed', `Failed to start Python: ${message}`);
      return;
    }

    this.writeRunnerPid();
    this.setState('starting');
    this.emit({ type: 'RunnerStarting', sessionId: this.sessionId, runtimeMode });
    this.startReadyTimeout();
    this.startHeartbeatMonitor();

    const child = this.proc;
    let stderrBuf = '';

    this.stdioClient.attach(child, {
      onLine: (line) => this.handleStdout(line),
      onStderr: (text) => {
        this.output.append(text);
        stderrBuf += text;
        this.captureStartupStep(text);
      },
      onExit: (code, signal) => {
        if (this.proc !== child) {
          this.output.appendLine(`[Theseus] ignored stale stdio exit code: ${code}${signal ? ` signal: ${signal}` : ''}`);
          return;
        }
        this.clearTimers();
        this.proc = undefined;
        this.lastReadyEvent = undefined;
        this.removeRunnerPid(child.pid);
        this.output.appendLine(`[Theseus] exit code: ${code}${signal ? ` signal: ${signal}` : ''}`);
        if (isExpectedStopReason(this.exitReason)) {
          return;
        }
        this.exitReason = signal ? `signal:${signal}` : `code:${code}`;
        if (code !== 0 && code !== null && stderrBuf.trim()) {
          const diagnosticCode = classifyProcessFailure(stderrBuf, code);
          this.setState('error', { code: diagnosticCode });
          this.emitDiagnostic(diagnosticCode, `Process exited (code ${code}):\n${stderrBuf.trim()}`);
        } else {
          this.setState('exited');
          this.emit({ type: 'RunnerExited', code, signal: signal || undefined });
        }
      },
      onError: (err) => {
        if (this.proc !== child) {
          this.output.appendLine(`[Theseus] ignored stale stdio error: ${err.message}`);
          return;
        }
        this.clearTimers();
        this.proc = undefined;
        this.removeRunnerPid(child.pid);
        if (isExpectedStopReason(this.exitReason) || this.abortController?.signal.aborted) {
          this.output.appendLine(`[Theseus] ignored expected stdio error: ${err.message}`);
          return;
        }
        this.output.appendLine(`[Theseus] spawn error: ${err.message}`);
        this.setState('error', { code: 'spawn_failed' });
        this.emitDiagnostic(
          'spawn_failed',
          `Failed to start Python: ${err.message}\n\nCheck "Theseus" Output Channel.\nVerify theseus.pythonPath in settings.`,
        );
      },
    });
  }

  private writeRunnerPid(): void {
    this.runnerState.writeStdio(this.proc?.pid, this.sessionId, this.startMetadata);
  }

  private removeRunnerPid(expectedPid?: number): void {
    this.runnerState.remove(this.startMetadata?.workspaceCwd, expectedPid);
  }

  private cleanupOrphanRunner(workspaceCwd: string): void {
    this.runnerState.cleanupOrphan(workspaceCwd, this.proc?.pid);
  }

  private writeLine(line: string): void {
    this.stdioClient.writeLine(this.proc, line, (err) => {
      this.emitDiagnostic('send_failed', err instanceof Error ? err.message : String(err));
    });
  }

  private flushPendingInput(): void {
    if (this.daemon) {
      while (this.pendingInput.length) {
        const pending = this.pendingInput.shift();
        if (!pending) continue;
        // 동일 mode 재전송 시 runner의 mode-switch 알림을 억제
        const effectiveMode = pending.mode && pending.mode !== this.lastSentMode ? pending.mode : undefined;
        const previousMode = this.lastSentMode;
        if (effectiveMode) this.lastSentMode = effectiveMode;
        void this.sendDaemon(pending.text, effectiveMode).then(success => {
          if (!success) this.lastSentMode = previousMode;
        });
      }
      if (this.pendingInput.length === 0 && this.state === 'waiting_input') {
        this.setState('ready');
      }
      return;
    }
    while (this.pendingInput.length && this.proc) {
      const pending = this.pendingInput.shift();
      if (!pending) continue;
      const effectiveMode = pending.mode && pending.mode !== this.lastSentMode ? pending.mode : undefined;
      if (effectiveMode) {
        this.writeLine(JSON.stringify({ type: 'setMode', mode: effectiveMode }));
        this.lastSentMode = effectiveMode;
      }
      this.writeLine(pending.text);
    }
    if (this.pendingInput.length === 0 && this.state === 'waiting_input') {
      this.setState('ready');
    }
  }

  private reviveReadyIfAttachable(reason: string): boolean {
    if (!this.proc || !this.lastReadyEvent) return false;
    if (!['stale', 'starting', 'error'].includes(this.state)) return false;

    this.output.appendLine(`[Theseus] revive existing runner: ${reason}, state=${this.state}`);
    this.lastHeartbeatAt = Date.now();
    this.exitReason = undefined;
    this.setState(this.pendingInput.length ? 'waiting_input' : 'ready', {
      reason,
      revived: true,
    });
    this.flushPendingInput();
    return true;
  }

  private handleStdout(line: string): void {
    if (!line.trim()) return;
    this.lastEventAt = Date.now();
    try {
      this.jsonParseErrorCount = 0;
      const event = asRunnerEvent(JSON.parse(line));
      if (!event) {
        this.output.appendLine(`[json-event-error] ${line}`);
        this.emitDiagnostic('json_parse_error', 'Runner emitted JSON without a valid Theseus event type.');
        return;
      }
      this.emit(event);
    } catch {
      this.jsonParseErrorCount += 1;
      this.output.appendLine(`[json-parse-error] ${line}`);
      if (this.state === 'starting' && this.jsonParseErrorCount === 1) {
        this.emitDiagnostic(
          'json_parse_error',
          `Runner emitted non-JSON stdout while starting. Check the Theseus Output channel.\n\n${line}`,
        );
      }
    }
  }

  private startReadyTimeout(): void {
    if (this.readyTimer) clearTimeout(this.readyTimer);
    this.readyTimer = setTimeout(() => {
      if (this.state !== 'starting') return;
      this.setState('stale', { code: 'ready_timeout' });
      this.emitDiagnostic(
        'ready_timeout',
        `Runner has not emitted RunnerReady after ${Math.round(READY_TIMEOUT_MS / 1000)}s. The Python process is still running.`,
      );
    }, READY_TIMEOUT_MS);
  }

  private startHeartbeatMonitor(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    if (this.daemon) {
      this.heartbeatTimer = setInterval(() => {
        void this.pollDaemonStatus({ emitStatus: false });
      }, DAEMON_HEARTBEAT_INTERVAL_MS);
      return;
    }
    this.heartbeatTimer = setInterval(() => {
      if (!this.proc || !this.lastHeartbeatAt || this.state === 'starting' || this.state === 'stale') return;
      if (Date.now() - this.lastHeartbeatAt > HEARTBEAT_STALE_MS) {
        this.setState('stale', { code: 'ready_timeout' });
        this.emitDiagnostic('ready_timeout', 'Runner heartbeat is stale. The Python process is still running.');
      }
    }, 10000);
  }

  private clearTimers(): void {
    if (this.readyTimer) clearTimeout(this.readyTimer);
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.readyTimer = undefined;
    this.heartbeatTimer = undefined;
  }

  private captureStartupStep(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (/Loaded .*custom tools/i.test(trimmed)) {
      this.logLifecycle('startup_step', { step: 'loaded_custom_tools', message: trimmed });
    }
  }

  private emitDiagnostic(code: TheseusDiagnosticCode, message: string): void {
    this.output.appendLine(`[Theseus] diagnostic ${code}: ${message}`);
    const diagnostic = { type: 'RunnerDiagnostic', code, message, state: this.state, sessionId: this.sessionId };
    this.lastDiagnostic = diagnostic;
    this.emit(diagnostic);
    if (
      code !== 'ready_timeout' &&
      code !== 'user_stop' &&
      code !== 'send_failed' &&
      code !== 'json_parse_error' &&
      code !== 'daemon_busy' &&
      code !== 'event_replay_gap'
    ) {
      this.emit({ type: 'RunnerError', code, message });
    }
  }

  private setState(state: TheseusSessionState, metadata?: Record<string, unknown>): void {
    this.state = state;
    // error 상태로 전환 시 mode dedupe 신뢰성을 잃으므로 lastSentMode를 리셋해
    // 다음 send에서 mode를 다시 명시 전송하도록 한다 (stdio writeLine 실패 등의 fallback)
    if (state === 'error') this.lastSentMode = undefined;
    this.logLifecycle('state', { state, ...metadata });
    this.emit(this.status);
  }

  private logLifecycle(type: string, metadata?: Record<string, unknown>): void {
    const event: RunnerEvent = {
      type: 'RunnerLifecycle',
      lifecycleType: type,
      state: this.state,
      sessionId: this.sessionId,
      timestamp: nowIso(),
      metadata,
    };
    this.lifecycleHistory.push(event);
    while (this.lifecycleHistory.length > LIFECYCLE_HISTORY_LIMIT) this.lifecycleHistory.shift();
    this.output.appendLine(`[Theseus] lifecycle ${type}: ${JSON.stringify({ state: this.state, ...metadata })}`);
  }

  private emit(event: RunnerEvent): void {
    if (event.type === 'RunnerReady') {
      if (typeof event.session === 'string' && event.session) {
        this.setPreferredSession(event.session);
      }
      if (this.readyTimer) clearTimeout(this.readyTimer);
      this.readyTimer = undefined;
      if (this.daemon) {
        if (!this.heartbeatTimer) this.startHeartbeatMonitor();
      } else if (this.heartbeatTimer) {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = undefined;
      }
      this.lastReadyEvent = event;
      this.lastHeartbeatAt = Date.now();
      this.output.appendLine('[Theseus] step   : runner_ready');
      this.setState(this.pendingInput.length ? 'waiting_input' : 'ready');
      this.flushPendingInput();
    } else if (event.type === 'RunnerHeartbeat' || event.type === 'StatusEvent') {
      this.lastHeartbeatAt = Date.now();
      if (this.state === 'stale' && this.lastReadyEvent) this.setState('ready');
    } else if (event.type === 'SessionChangedEvent') {
      const current = typeof event.current === 'string' ? event.current : undefined;
      if (current) this.setPreferredSession(current);
      if (current && this.lastReadyEvent) {
        this.lastReadyEvent = { ...this.lastReadyEvent, session: current };
      }
    } else if (event.type === 'SessionListEvent') {
      const current = typeof event.current === 'string' ? event.current : undefined;
      if (current) this.setPreferredSession(current);
    } else if (event.type === 'AssistantTextDelta' || event.type === 'ToolExecutionStarted') {
      if (this.isRunning) this.state = 'busy';
    } else if (event.type === 'AssistantTurnComplete' || event.type === 'PlanDraftedEvent') {
      if ((this.proc || this.daemon) && this.lastReadyEvent) this.state = 'ready';
    } else if (event.type === 'RunnerExited') {
      this.clearTimers();
      this.lastReadyEvent = undefined;
      this.state = 'exited';
    } else if (event.type === 'RunnerStopped') {
      this.clearTimers();
      this.lastReadyEvent = undefined;
      this.state = 'stopped';
    } else if (event.type === 'RunnerError') {
      this.clearTimers();
      this.lastReadyEvent = undefined;
      this.state = 'error';
    }

    if (event.type !== 'RunnerStatus' && event.type !== 'RunnerLifecycle') {
      const lifecycleEvent = { ...event, timestamp: nowIso(), sessionId: event.sessionId || this.sessionId };
      this.lifecycleHistory.push(lifecycleEvent);
      while (this.lifecycleHistory.length > LIFECYCLE_HISTORY_LIMIT) this.lifecycleHistory.shift();
    }
    if (event.type === 'PermissionRequest') {
      void this.handlePermissionRequest(event);
    }
    for (const listener of this.listeners) listener(event);
  }
}
