import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { TheseusSessionManager } from '../../session/SessionManager';
import type { JsonObject, RunnerEvent } from '../../shared/protocol';
import { getCoreRoot, getCustomToolSearchRoots, getWorkspaceCwd } from '../../workspace/WorkspaceContext';

function getExtensionBuildInfo(context: vscode.ExtensionContext): JsonObject {
  const packageJson = context.extension.packageJSON as Record<string, unknown> | undefined;
  const outFile = path.join(context.extensionUri.fsPath, 'out', 'extension.js');
  let builtAt = '';
  try {
    builtAt = fs.statSync(outFile).mtime.toISOString();
  } catch {
    builtAt = '';
  }
  return {
    version: typeof packageJson?.version === 'string' ? packageJson.version : '',
    extensionPath: context.extensionUri.fsPath,
    builtAt,
  };
}

export class HealthController {
  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly sessionManager: TheseusSessionManager,
    private readonly postRunnerEvent: (event: RunnerEvent) => void,
  ) {}

  postHealthStatus(): void {
    const coreRoot = getCoreRoot(this.context) || '';
    const workspaceCwd = getWorkspaceCwd() || '';
    const config = vscode.workspace.getConfiguration('theseus');
    const pythonExec = config.get<string>('pythonPath') || 'python';
    const serverUrl = config.get<string>('serverUrl') || '';
    const status = this.sessionManager.status;
    const customToolRoots = getCustomToolSearchRoots();
    this.postRunnerEvent({
      type: 'healthStatus',
      settings: {
        corePath: coreRoot,
        pythonPath: pythonExec,
        serverUrl,
        workspacePath: workspaceCwd,
        coreRoot,
        workspaceCwd,
        pythonExec,
        customToolRoots,
        extension: getExtensionBuildInfo(this.context),
      },
      runner: {
        running: status.running,
        processRunning: status.processRunning,
        lifecycle: status.lifecycle,
        runtimeMode: status.runtimeMode,
        daemonPid: status.daemonPid,
        daemonPort: status.daemonPort,
        sessionId: status.sessionId,
        lastDiagnostic: status.lastDiagnostic,
      },
      checks: [
        {
          label: 'Core path',
          status: coreRoot ? 'ok' : 'error',
          detail: coreRoot || 'theseus.corePath를 설정하세요.',
        },
        {
          label: 'Workspace',
          status: workspaceCwd ? 'ok' : 'warn',
          detail: workspaceCwd || '워크스페이스 폴더를 열거나 theseus.workspacePath를 설정하세요.',
        },
        {
          label: 'Python',
          status: pythonExec ? 'ok' : 'warn',
          detail: pythonExec,
        },
        {
          label: 'Runner',
          status: status.lifecycle === 'error' ? 'error' : status.running ? 'ok' : 'warn',
          detail: String(status.lifecycle || 'stopped'),
        },
        {
          label: 'Custom tools',
          status: customToolRoots.length ? 'ok' : 'warn',
          detail: customToolRoots.length
            ? customToolRoots.join(' | ')
            : 'corePath 또는 workspacePath를 확인하세요.',
        },
      ],
    });
  }
}
