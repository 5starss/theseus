import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { isPidRunning, killPidTree } from './ProcessUtils';
import { RUNNER_STATE_SCHEMA_VERSION, type DaemonRunnerState, type TheseusSessionMetadata } from './runnerTypes';

type ReadDaemonOptions = {
  coreRoot?: string;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function samePath(left: string, right: string): boolean {
  const a = path.resolve(left);
  const b = path.resolve(right);
  return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function positiveInt(value: unknown): number | undefined {
  const numberValue = Number(value);
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : undefined;
}

export class RunnerStateStore {
  constructor(private readonly output: vscode.OutputChannel) {}

  path(workspaceCwd?: string): string | undefined {
    if (!workspaceCwd) return undefined;
    return path.join(workspaceCwd, '.theseus', 'runner.json');
  }

  readDaemon(workspaceCwd: string, options: ReadDaemonOptions = {}): DaemonRunnerState | undefined {
    const file = this.path(workspaceCwd);
    if (!file || !fs.existsSync(file)) return undefined;
    try {
      const parsed = JSON.parse(fs.readFileSync(file, 'utf8')) as unknown;
      if (!isObject(parsed)) {
        this.discardInvalidState(file, 'runner state is not an object');
        return undefined;
      }

      if (parsed.mode === 'stdio') return undefined;

      const pid = positiveInt(parsed.pid);
      const port = positiveInt(parsed.port);
      const host = typeof parsed.host === 'string' && parsed.host ? parsed.host : '127.0.0.1';
      const token = typeof parsed.token === 'string' ? parsed.token : '';
      const stateWorkspace = typeof parsed.workspaceCwd === 'string' ? parsed.workspaceCwd : '';
      const stateCoreRoot = typeof parsed.coreRoot === 'string' ? parsed.coreRoot : '';

      const invalidReason = this.validateDaemonState({
        state: parsed,
        pid,
        port,
        host,
        token,
        workspaceCwd,
        stateWorkspace,
        expectedCoreRoot: options.coreRoot,
        stateCoreRoot,
      });
      if (invalidReason) {
        this.discardInvalidState(file, invalidReason, pid);
        return undefined;
      }

      return {
        schemaVersion: RUNNER_STATE_SCHEMA_VERSION,
        pid,
        port,
        host,
        token,
        mode: 'local-daemon',
        model: typeof parsed.model === 'string' ? parsed.model : undefined,
        sessionId: typeof parsed.sessionId === 'string' ? parsed.sessionId : undefined,
        workspaceHash: typeof parsed.workspaceHash === 'string' ? parsed.workspaceHash : undefined,
        workspaceCwd: stateWorkspace,
        coreRoot: stateCoreRoot,
        startedAt: typeof parsed.startedAt === 'string' ? parsed.startedAt : undefined,
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.discardInvalidState(file, `failed to parse runner state: ${message}`);
      return undefined;
    }
  }

  writeStdio(pid: number | undefined, sessionId: string, metadata: TheseusSessionMetadata | undefined): void {
    if (!pid || !metadata) return;
    const file = this.path(metadata.workspaceCwd);
    if (!file) return;

    const payload = {
      pid,
      sessionId,
      startedAt: new Date().toISOString(),
      coreRoot: metadata.coreRoot,
      workspaceCwd: metadata.workspaceCwd,
      mode: 'stdio',
      schemaVersion: RUNNER_STATE_SCHEMA_VERSION,
    };

    try {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, JSON.stringify(payload, null, 2), 'utf8');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.output.appendLine(`[Theseus] failed to write runner pid: ${message}`);
    }
  }

  remove(workspaceCwd: string | undefined, expectedPid?: number): void {
    const file = this.path(workspaceCwd);
    if (!file) return;

    try {
      if (expectedPid && fs.existsSync(file)) {
        const state = JSON.parse(fs.readFileSync(file, 'utf8')) as { pid?: unknown };
        const recordedPid = Number(state.pid);
        if (recordedPid && recordedPid !== expectedPid) return;
      }
      fs.rmSync(file, { force: true });
    } catch {
      try {
        fs.rmSync(file, { force: true });
      } catch {
        // ignore cleanup failures
      }
    }
  }

  cleanupOrphan(workspaceCwd: string, ownedPid?: number): void {
    const file = this.path(workspaceCwd);
    if (!file || !fs.existsSync(file)) return;

    try {
      const state = JSON.parse(fs.readFileSync(file, 'utf8')) as { pid?: unknown };
      const pid = Number(state.pid);
      if (!pid) {
        fs.rmSync(file, { force: true });
        return;
      }

      if (ownedPid === pid) return;

      if (isPidRunning(pid)) {
        this.output.appendLine(`[Theseus] orphan runner detected. killing pid=${pid}`);
        killPidTree(pid);
      } else {
        this.output.appendLine(`[Theseus] stale runner pid file detected. pid=${pid}`);
      }
      fs.rmSync(file, { force: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.output.appendLine(`[Theseus] failed to inspect runner pid file: ${message}`);
      try {
        fs.rmSync(file, { force: true });
      } catch {
        // ignore cleanup failures
      }
    }
  }

  private validateDaemonState(args: {
    state: Record<string, unknown>;
    pid: number | undefined;
    port: number | undefined;
    host: string;
    token: string;
    workspaceCwd: string;
    stateWorkspace: string;
    expectedCoreRoot?: string;
    stateCoreRoot: string;
  }): string | undefined {
    if (args.state.mode !== 'local-daemon') return 'runner state is not a local daemon';
    if (args.state.schemaVersion !== RUNNER_STATE_SCHEMA_VERSION) {
      return `unsupported runner state schemaVersion=${String(args.state.schemaVersion)}`;
    }
    if (!args.pid) return 'runner state is missing a valid pid';
    if (!args.port || args.port > 65535) return 'runner state is missing a valid port';
    if (args.host !== '127.0.0.1') return `unsupported daemon host=${args.host}`;
    if (!args.token) return 'runner state is missing daemon token';
    if (!args.stateWorkspace || !samePath(args.stateWorkspace, args.workspaceCwd)) {
      return 'runner state workspace does not match current workspace';
    }
    if (args.expectedCoreRoot && (!args.stateCoreRoot || !samePath(args.stateCoreRoot, args.expectedCoreRoot))) {
      return 'runner state coreRoot does not match current Extension configuration';
    }
    if (typeof args.state.sessionId !== 'string' || !args.state.sessionId) {
      return 'runner state is missing daemon sessionId';
    }
    if (typeof args.state.workspaceHash !== 'string' || !args.state.workspaceHash) {
      return 'runner state is missing workspaceHash';
    }
    return undefined;
  }

  private discardInvalidState(file: string, reason: string, pid?: number): void {
    this.output.appendLine(`[Theseus] invalid runner state ignored: ${reason}`);
    if (pid && isPidRunning(pid)) {
      this.output.appendLine(`[Theseus] killing daemon with invalid runner state pid=${pid}`);
      killPidTree(pid);
    }
    try {
      fs.rmSync(file, { force: true });
    } catch {
      // ignore cleanup failures
    }
  }
}
