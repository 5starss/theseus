import * as cp from 'child_process';
import * as path from 'path';
import * as readline from 'readline';
import * as vscode from 'vscode';

import type { RunnerClient, RunnerProcess, RunnerStartConfig } from './runnerTypes';

export type StdioRunnerHandlers = {
  onLine: (line: string) => void;
  onStderr: (text: string) => void;
  onExit: (code: number | null, signal: NodeJS.Signals | null) => void;
  onError: (err: Error) => void;
};

export class StdioRunnerClient implements RunnerClient {
  readonly mode = 'stdio' as const;

  constructor(private readonly output: vscode.OutputChannel) {}

  startProcess(config: RunnerStartConfig): RunnerProcess {
    const extraPython = config.coreRoot !== config.workspaceCwd
      ? config.coreRoot + path.delimiter + (process.env.PYTHONPATH || '')
      : (process.env.PYTHONPATH || '');

    return cp.spawn(
      config.pythonExec,
      ['-m', 'theseus_engine.cli_runner', '--json-mode', '--session', config.initialSession || 'default'],
      {
        cwd: config.workspaceCwd,
        env: {
          ...process.env,
          PYTHONPATH: extraPython,
          THESEUS_SERVER_URL: config.serverUrl,
          PYTHONIOENCODING: 'utf-8',
          PYTHONUTF8: '1',
        },
        signal: config.signal,
      },
    );
  }

  attach(process: RunnerProcess, handlers: StdioRunnerHandlers): void {
    const rl = readline.createInterface({ input: process.stdout });
    rl.on('line', handlers.onLine);
    process.stderr.on('data', (chunk: Buffer) => handlers.onStderr(chunk.toString()));
    process.on('exit', (code, signal) => {
      rl.close();
      handlers.onExit(code, signal);
    });
    process.on('error', handlers.onError);
  }

  writeLine(process: RunnerProcess | undefined, line: string, onError: (err: unknown) => void): void {
    try {
      process?.stdin.write(line + '\n');
    } catch (err) {
      onError(err);
    }
  }
}
