import * as cp from 'child_process';

export function isPidRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    return code === 'EPERM';
  }
}

export function killPidTree(pid: number): void {
  if (process.platform === 'win32') {
    cp.spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true });
    return;
  }

  try {
    process.kill(pid, 'SIGTERM');
  } catch {
    // ignore missing processes
  }
}
