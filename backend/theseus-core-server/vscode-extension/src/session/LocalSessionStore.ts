import * as fs from 'fs';
import * as path from 'path';

export function listLocalSessionSummaries(
  workspaceCwd: string | undefined,
  current = 'default',
): Array<Record<string, unknown>> {
  const currentName = current || 'default';
  const names = new Set<string>([currentName]);
  const sessionDir = workspaceCwd ? path.join(workspaceCwd, '.theseus_sessions') : undefined;
  if (sessionDir && fs.existsSync(sessionDir)) {
    for (const entry of fs.readdirSync(sessionDir, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.toLowerCase().endsWith('.json')) {
        names.add(path.basename(entry.name, '.json'));
      }
    }
  }
  return Array.from(names).sort().map(name => ({ name, current: name === currentName, source: 'local' }));
}
