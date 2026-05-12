import * as cp from 'child_process';
import * as http from 'http';
import * as path from 'path';
import * as vscode from 'vscode';

import { asRunnerEvent, type RunnerEvent } from '../shared/protocol';
import type { DaemonRunnerState, DaemonStatus, RunnerClient, RunnerProcess, RunnerStartConfig } from './runnerTypes';

const DAEMON_REQUEST_TIMEOUT_MS = 5000;

type StreamEventsOptions = {
  after?: number;
};

export class DaemonHttpError extends Error {
  constructor(
    readonly method: string,
    readonly pathname: string,
    readonly statusCode: number,
    readonly body: string,
    readonly detail: string,
  ) {
    super(`Daemon ${method} ${pathname} failed (${statusCode}): ${detail || body}`);
    this.name = 'DaemonHttpError';
    Object.setPrototypeOf(this, DaemonHttpError.prototype);
  }
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function isDaemonHttpStatus(err: unknown, statusCode: number): err is DaemonHttpError {
  return err instanceof DaemonHttpError && err.statusCode === statusCode;
}

export function isDaemonConnectionError(err: unknown): boolean {
  const maybeCode = (err as NodeJS.ErrnoException | undefined)?.code;
  const code = typeof maybeCode === 'string' ? maybeCode : '';
  if (['ECONNRESET', 'ECONNREFUSED', 'EPIPE', 'ETIMEDOUT', 'ECONNABORTED'].includes(code)) return true;
  return /socket hang up|read ECONNRESET|connect ECONNREFUSED|write EPIPE/i.test(errorMessage(err));
}

export function sameWorkspacePath(left: string, right: string): boolean {
  const a = path.resolve(left);
  const b = path.resolve(right);
  return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function timeoutError(message: string): NodeJS.ErrnoException {
  const err = new Error(message) as NodeJS.ErrnoException;
  err.code = 'ETIMEDOUT';
  return err;
}

function daemonErrorDetail(text: string): string {
  if (!text) return '';
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    const detail = parsed.detail;
    if (typeof detail === 'string') return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  } catch {
    // fall through to raw response body
  }
  return text;
}

export class DaemonRunnerClient implements RunnerClient {
  readonly mode = 'local-daemon' as const;

  constructor(private readonly output: vscode.OutputChannel) {}

  startProcess(config: RunnerStartConfig): RunnerProcess {
    const extraPython = config.coreRoot !== config.workspaceCwd
      ? config.coreRoot + path.delimiter + (process.env.PYTHONPATH || '')
      : (process.env.PYTHONPATH || '');

    return cp.spawn(
      config.pythonExec,
      [
        '-m',
        'theseus_engine.daemon',
        '--host',
        '127.0.0.1',
        '--port',
        '0',
        '--workspace',
        config.workspaceCwd,
        '--core-root',
        config.coreRoot,
      ],
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

  request(
    daemon: DaemonRunnerState | undefined,
    method: 'GET' | 'POST',
    pathname: string,
    body?: unknown,
  ): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (!daemon?.port || !daemon.token) {
        reject(new Error('Daemon connection metadata is missing.'));
        return;
      }
      const payload = body ? JSON.stringify(body) : undefined;
      const req = http.request(
        {
          host: daemon.host || '127.0.0.1',
          port: daemon.port,
          path: pathname,
          method,
          headers: {
            Authorization: `Bearer ${daemon.token}`,
            ...(payload ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } : {}),
          },
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on('data', (chunk: Buffer) => chunks.push(chunk));
          res.on('error', reject);
          res.on('end', () => {
            const text = Buffer.concat(chunks).toString('utf8');
            if ((res.statusCode || 0) >= 400) {
              reject(new DaemonHttpError(
                method,
                pathname,
                res.statusCode || 0,
                text,
                daemonErrorDetail(text),
              ));
              return;
            }
            try {
              resolve(text ? JSON.parse(text) as Record<string, unknown> : {});
            } catch (err) {
              reject(err);
            }
          });
        },
      );
      req.on('error', reject);
      req.setTimeout(DAEMON_REQUEST_TIMEOUT_MS, () => {
        req.destroy(timeoutError(`Daemon ${method} ${pathname} timed out.`));
      });
      if (payload) req.write(payload);
      req.end();
    });
  }

  async status(daemon: DaemonRunnerState | undefined): Promise<DaemonStatus> {
    return await this.request(daemon, 'GET', '/status') as DaemonStatus;
  }

  streamEvents(
    daemon: DaemonRunnerState | undefined,
    runId: string,
    emit: (event: RunnerEvent, sequence?: number) => void,
    options: StreamEventsOptions = {},
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!daemon?.port || !daemon.token) {
        reject(new Error('Daemon connection metadata is missing.'));
        return;
      }
      const after = Math.max(0, Math.floor(options.after || 0));
      const streamPath = `/runs/${encodeURIComponent(runId)}/events${after ? `?after=${after}` : ''}`;
      const req = http.request(
        {
          host: daemon.host || '127.0.0.1',
          port: daemon.port,
          path: streamPath,
          method: 'GET',
          headers: { Authorization: `Bearer ${daemon.token}`, Accept: 'text/event-stream' },
        },
        (res) => {
          if ((res.statusCode || 0) >= 400) {
            reject(new DaemonHttpError('GET', streamPath, res.statusCode || 0, '', 'Daemon SSE failed'));
            res.resume();
            return;
          }
          let buffer = '';
          res.on('data', (chunk: Buffer) => {
            buffer += chunk.toString('utf8');
            let match: RegExpMatchArray | null;
            while ((match = buffer.match(/\r?\n\r?\n/)) && match.index !== undefined) {
              const frame = buffer.slice(0, match.index);
              buffer = buffer.slice(match.index + match[0].length);
              const lines = frame.split(/\r?\n/);
              const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
              const idLine = lines.find(line => line.startsWith('id:'));
              const sequence = idLine ? Number(idLine.slice(3).trim()) : undefined;
              if (!data) continue;
              try {
                const event = asRunnerEvent(JSON.parse(data));
                if (event) emit(event, Number.isFinite(sequence) ? sequence : undefined);
                else this.output.appendLine(`[Theseus] daemon SSE invalid event ignored: ${data}`);
              } catch (err) {
                this.output.appendLine(`[Theseus] daemon SSE parse failed: ${errorMessage(err)}`);
              }
            }
          });
          res.on('error', reject);
          res.on('end', resolve);
        },
      );
      req.on('error', reject);
      req.setTimeout(0);
      req.end();
    });
  }
}
