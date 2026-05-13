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
  return Array.from(names).sort().map(name => ({
    name,
    title: readLocalSessionTitle(sessionDir, name),
    current: name === currentName,
    source: 'local',
  }));
}

function readLocalSessionTitle(sessionDir: string | undefined, name: string): string {
  if (!sessionDir) return '';
  const filePath = path.join(sessionDir, `${name}.json`);
  if (!fs.existsSync(filePath)) return '';
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return '';
    const metadata = parsed.metadata && typeof parsed.metadata === 'object' ? parsed.metadata : {};
    const title = typeof metadata.title === 'string' ? metadata.title : parsed.title;
    return typeof title === 'string' ? title.trim() : '';
  } catch {
    return '';
  }
}
