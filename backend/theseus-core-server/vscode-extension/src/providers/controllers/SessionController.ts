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

export class SessionController {
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
    if (this.canHandleLocally()) {
      this.withLocalSnapshot(() => createLocalSession(this.localSessionWorkspace(), sessionName));
      return;
    }
    this.postBusyNotice();
  }

  switchSession(name?: string): void {
    if (!name) return;
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session switch ${JSON.stringify(name)}`);
      return;
    }
    if (this.canHandleLocally()) {
      this.withLocalSnapshot(() => switchLocalSession(this.localSessionWorkspace(), name));
      return;
    }
    this.postBusyNotice();
  }

  deleteSession(name?: string): void {
    if (!name) return;
    const current = this.currentSessionName();
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session delete ${JSON.stringify(name)}`);
      return;
    }
    if (this.canHandleLocally()) {
      this.withLocalSnapshot(() => deleteLocalSession(this.localSessionWorkspace(), name, current));
      return;
    }
    this.postBusyNotice();
  }

  renameSession(oldName?: string, newName?: string): void {
    if (!oldName || !newName) return;
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session rename ${JSON.stringify(oldName)} ${JSON.stringify(newName)}`);
      return;
    }
    if (this.canHandleLocally()) {
      this.withLocalSnapshot(() => renameLocalSession(this.localSessionWorkspace(), oldName, newName, this.currentSessionName()));
      return;
    }
    this.postBusyNotice();
  }

  exportSession(name?: string, format?: string): void {
    if (!name || !format) return;
    if (this.canRouteToRunner()) {
      this.sessionManager.send(`/session export ${JSON.stringify(name)} ${format}`);
      return;
    }
    if (this.canHandleLocally()) {
      try {
        this.postRunnerEvent({
          type: 'SessionExportedEvent',
          ...exportLocalSession(this.localSessionWorkspace(), name, format),
        });
      } catch (err) {
        this.postLocalSessionError(err);
      }
      return;
    }
    this.postBusyNotice();
  }

  private currentSessionName(): string {
    const status = this.sessionManager.status;
    return typeof status.session === 'string' && status.session ? status.session : 'default';
  }

  private localSessionWorkspace(): string | undefined {
    const status = this.sessionManager.status;
    return typeof status.workspaceCwd === 'string' ? status.workspaceCwd : getWorkspaceCwd();
  }

  private canRouteToRunner(): boolean {
    return this.sessionManager.hasProcess && ['ready', 'waiting_input'].includes(this.sessionManager.currentState);
  }

  private canHandleLocally(): boolean {
    return !this.sessionManager.hasProcess || ['stopped', 'error', 'exited', 'stale'].includes(this.sessionManager.currentState);
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

  private postBusyNotice(): void {
    this.postRunnerEvent({
      type: 'RunnerDiagnostic',
      code: 'session_busy',
      message: 'Session changes are available after the current run finishes or the runner is stopped.',
      state: this.sessionManager.currentState,
    });
  }
}
