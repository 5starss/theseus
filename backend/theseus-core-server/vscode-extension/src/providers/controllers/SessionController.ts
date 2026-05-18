import * as vscode from 'vscode';
import type { RunnerEvent } from '../../shared/protocol';
import {
  createLocalSession,
  deleteLocalSession,
  exportLocalSession,
  listLocalSessionSummaries,
  renameLocalSession,
  switchLocalSession,
  type LocalSessionActionResult,
} from '../../session/LocalSessionStore';
import { TheseusSessionManager } from '../../session/SessionManager';
import { getWorkspaceCwd } from '../../workspace/WorkspaceContext';

function makeUntitledSessionName(): string {
  const now = new Date();
  const pad = (value: number, size = 2) => String(value).padStart(size, '0');
  return [
    'session',
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
    pad(now.getMilliseconds(), 3),
  ].join('');
}

const SESSION_COMMAND_WAIT_TIMEOUT_MS = 5 * 60 * 1000;

export class SessionController {
  private pendingSessionCommand: { disposable: vscode.Disposable; timer: NodeJS.Timeout } | undefined;

  constructor(
    private readonly sessionManager: TheseusSessionManager,
    private readonly postRunnerEvent: (event: RunnerEvent) => void,
  ) {}

  postList(): void {
    const current = this.currentSessionName();
    this.postRunnerEvent({
      type: 'SessionListEvent',
      source: 'local',
      current,
      sessions: listLocalSessionSummaries(this.localSessionWorkspace(), current),
    });
  }

  newSession(name?: string): void {
    const sessionName = typeof name === 'string' && name.trim() ? name.trim() : makeUntitledSessionName();
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session new ${JSON.stringify(sessionName)}`);
      return;
    }
    if (this.isBlockedByActiveRun()) {
      this.postStatus(`세션 전환: 현재 run이 끝나면 새 세션으로 전환합니다: ${sessionName}`);
      this.waitForReadyThenSend(`/session new ${JSON.stringify(sessionName)}`);
      return;
    }
    this.withLocalSnapshot(() => createLocalSession(this.localSessionWorkspace(), sessionName));
    this.waitForReadyThenSwitch(sessionName);
  }

  switchSession(name?: string): void {
    if (!name) return;
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session switch ${JSON.stringify(name)}`);
      return;
    }
    if (this.isBlockedByActiveRun()) {
      this.postStatus(`세션 전환: 현재 run이 끝나면 전환합니다: ${name}`);
      this.waitForReadyThenSwitch(name);
      return;
    }
    // process가 살아있는 비-ready 상태(starting/stale/...)에서는
    // local snapshot을 먼저 반영하고 ready transition을 기다려 라우팅
    if (this.sessionManager.hasProcess) {
      this.withLocalSnapshot(() => switchLocalSession(this.localSessionWorkspace(), name));
      this.waitForReadyThenSwitch(name);
      return;
    }
    this.withLocalSnapshot(() => switchLocalSession(this.localSessionWorkspace(), name));
  }

  /**
   * runner가 ready/waiting_input 상태가 되면 세션 전환을 실행.
   * - busy 상태여도 interrupt하지 않음.
   * - starting/stale 상태면 기다리기만 함
   * 상태 transition을 이벤트로 구독해 race-free하게 대기한다.
   * 긴 run은 정상일 수 있으므로 짧은 타임아웃으로 runner를 재시작하지 않는다.
   */
  private waitForReadyThenSwitch(name: string): void {
    this.waitForReadyThenSend(`/session switch ${JSON.stringify(name)}`, () => {
      this.withLocalSnapshot(() => switchLocalSession(this.localSessionWorkspace(), name));
    });
  }

  private waitForReadyThenSend(command: string, fallback?: () => void): void {
    this.pendingSessionCommand?.disposable.dispose();
    if (this.pendingSessionCommand?.timer) clearTimeout(this.pendingSessionCommand.timer);
    let settled = false;
    const finishWithFallback = () => {
      if (this.canRouteToRunner()) this.sessionManager.send(command);
      else if (fallback) fallback();
      else this.postStatus('세션 전환: 현재 run이 아직 진행 중입니다. 완료 후 다시 시도해 주세요.');
    };

    const disposable = this.sessionManager.onEvent(() => {
      if (settled) return;
      if (this.canRouteToRunner()) {
        settled = true;
        clearTimeout(timer);
        disposable.dispose();
        this.pendingSessionCommand = undefined;
        this.sessionManager.send(command);
      }
    });

    // 안전망: 장시간 ready가 안 되면 runner 재시작 없이 fallback 또는 안내만 남긴다.
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      disposable.dispose();
      if (this.pendingSessionCommand?.timer === timer) this.pendingSessionCommand = undefined;
      finishWithFallback();
    }, SESSION_COMMAND_WAIT_TIMEOUT_MS);
    this.pendingSessionCommand = { disposable, timer };

    // 즉시 ready로 transition한 경우 대비
    if (this.canRouteToRunner()) {
      settled = true;
      clearTimeout(timer);
      disposable.dispose();
      this.pendingSessionCommand = undefined;
      this.sessionManager.send(command);
    }
  }

  deleteSession(name?: string): void {
    if (!name) return;
    const current = this.currentSessionName();
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session delete ${JSON.stringify(name)}`);
      return;
    }
    if (this.isBlockedByActiveRun()) {
      this.postStatus(`세션 삭제: 현재 run이 끝나면 삭제합니다: ${name}`);
      this.waitForReadyThenSend(`/session delete ${JSON.stringify(name)}`);
      return;
    }
    try {
      const snapshot = deleteLocalSession(this.localSessionWorkspace(), name, current);
      this.postLocalSessionSnapshot(snapshot);
      if (name === current) this.waitForReadyThenSwitch(snapshot.current);
    } catch (err) {
      this.postLocalSessionError(err);
    }
  }

  renameSession(oldName?: string, newName?: string): void {
    if (!oldName || !newName) return;
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session rename ${JSON.stringify(oldName)} ${JSON.stringify(newName)}`);
      return;
    }
    if (this.isBlockedByActiveRun()) {
      this.postStatus(`세션 이름 변경: 현재 run이 끝나면 변경합니다: ${oldName} → ${newName}`);
      this.waitForReadyThenSend(`/session rename ${JSON.stringify(oldName)} ${JSON.stringify(newName)}`);
      return;
    }
    const wasCurrent = oldName === this.currentSessionName();
    this.withLocalSnapshot(() => renameLocalSession(this.localSessionWorkspace(), oldName, newName, this.currentSessionName()));
    if (wasCurrent) this.waitForReadyThenSwitch(newName);
  }

  exportSession(name?: string, format?: string): void {
    if (!name || !format) return;
    try {
      this.postRunnerEvent({
        type: 'SessionExportedEvent',
        ...exportLocalSession(this.localSessionWorkspace(), name, format),
      });
    } catch (err) {
      this.postLocalSessionError(err);
    }
  }

  private currentSessionName(): string {
    return this.sessionManager.preferredSessionName;
  }

  private localSessionWorkspace(): string | undefined {
    const status = this.sessionManager.status;
    return typeof status.workspaceCwd === 'string' ? status.workspaceCwd : getWorkspaceCwd();
  }

  private canRouteToRunner(): boolean {
    const status = this.sessionManager.status;
    const state = typeof status.state === 'string' ? status.state : this.sessionManager.currentState;
    return !!status.processRunning && ['ready', 'waiting_input'].includes(state);
  }

  private isBlockedByActiveRun(): boolean {
    const status = this.sessionManager.status;
    const state = typeof status.state === 'string' ? status.state : this.sessionManager.currentState;
    return !!status.processRunning && (state === 'busy' || this.sessionManager.currentState === 'busy');
  }

  private withLocalSnapshot(action: () => LocalSessionActionResult): void {
    try {
      this.postLocalSessionSnapshot(action());
    } catch (err) {
      this.postLocalSessionError(err);
    }
  }

  private postLocalSessionSnapshot(snapshot: LocalSessionActionResult): void {
    this.sessionManager.setPreferredSession(snapshot.current);
    this.postRunnerEvent({
      type: 'SessionListEvent',
      source: 'local',
      current: snapshot.current,
      sessions: snapshot.sessions,
    });
    this.postRunnerEvent({
      type: 'SessionChangedEvent',
      source: 'local',
      current: snapshot.current,
      history: snapshot.history,
      planState: snapshot.planState,
    });
  }

  private postLocalSessionError(error: unknown): void {
    this.postRunnerEvent({
      type: 'RunnerDiagnostic',
      code: 'session_error',
      message: error instanceof Error ? error.message : String(error),
      state: this.sessionManager.currentState,
    });
  }

  private postStatus(message: string): void {
    this.postRunnerEvent({
      type: 'StatusEvent',
      message,
    });
  }

}
