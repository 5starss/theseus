import * as fs from 'fs';
import * as path from 'path';

export type LocalSessionActionResult = {
  current: string;
  sessions: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  planState: Record<string, unknown> | null;
};

function sessionDirectory(workspaceCwd: string | undefined): string | undefined {
  return workspaceCwd ? path.join(workspaceCwd, '.theseus_sessions') : undefined;
}

function validateSessionName(name: string | undefined): string {
  const clean = String(name || '').trim();
  if (!clean || !/^[A-Za-z0-9]+$/.test(clean)) {
    throw new Error('Session name must be alphanumeric.');
  }
  return clean;
}

function ensureSessionDir(workspaceCwd: string | undefined): string {
  const sessionDir = sessionDirectory(workspaceCwd);
  if (!sessionDir) throw new Error('Workspace path is not available.');
  fs.mkdirSync(sessionDir, { recursive: true });
  return sessionDir;
}

function sessionPath(sessionDir: string, name: string): string {
  return path.join(sessionDir, `${validateSessionName(name)}.json`);
}

function readEnvelope(filePath: string): Record<string, unknown> {
  if (!fs.existsSync(filePath)) return {};
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function writeEnvelope(filePath: string, envelope: Record<string, unknown>): void {
  fs.writeFileSync(filePath, `${JSON.stringify(envelope, null, 2)}\n`, 'utf8');
}

function ensureSessionFile(sessionDir: string, name: string): void {
  const filePath = sessionPath(sessionDir, name);
  if (!fs.existsSync(filePath)) {
    writeEnvelope(filePath, { history: [] });
  }
}

export function listLocalSessionSummaries(
  workspaceCwd: string | undefined,
  current = 'default',
): Array<Record<string, unknown>> {
  const currentName = current || 'default';
  const names = new Set<string>([currentName]);
  const sessionDir = sessionDirectory(workspaceCwd);
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

export function createLocalSession(workspaceCwd: string | undefined, name: string): LocalSessionActionResult {
  const sessionDir = ensureSessionDir(workspaceCwd);
  const current = validateSessionName(name);
  ensureSessionFile(sessionDir, current);
  return localSessionSnapshot(workspaceCwd, current);
}

export function switchLocalSession(workspaceCwd: string | undefined, name: string): LocalSessionActionResult {
  const sessionDir = ensureSessionDir(workspaceCwd);
  const current = validateSessionName(name);
  ensureSessionFile(sessionDir, current);
  return localSessionSnapshot(workspaceCwd, current);
}

export function deleteLocalSession(
  workspaceCwd: string | undefined,
  name: string,
  current = 'default',
): LocalSessionActionResult {
  const sessionDir = ensureSessionDir(workspaceCwd);
  const target = validateSessionName(name);
  const targetPath = sessionPath(sessionDir, target);
  if (fs.existsSync(targetPath)) fs.unlinkSync(targetPath);

  const remaining = fs.readdirSync(sessionDir, { withFileTypes: true })
    .filter(entry => entry.isFile() && entry.name.toLowerCase().endsWith('.json'))
    .map(entry => path.basename(entry.name, '.json'))
    .filter(item => item !== target)
    .sort();
  const nextCurrent = target === current ? (remaining[0] || 'default') : current;
  ensureSessionFile(sessionDir, nextCurrent);
  return localSessionSnapshot(workspaceCwd, nextCurrent);
}

export function renameLocalSession(
  workspaceCwd: string | undefined,
  oldName: string,
  newName: string,
  current = 'default',
): LocalSessionActionResult {
  const sessionDir = ensureSessionDir(workspaceCwd);
  const oldClean = validateSessionName(oldName);
  const newClean = validateSessionName(newName);
  const oldPath = sessionPath(sessionDir, oldClean);
  const newPath = sessionPath(sessionDir, newClean);
  ensureSessionFile(sessionDir, oldClean);
  if (fs.existsSync(newPath)) throw new Error(`Session already exists: ${newClean}`);
  fs.renameSync(oldPath, newPath);
  return localSessionSnapshot(workspaceCwd, current === oldClean ? newClean : current);
}

export function exportLocalSession(
  workspaceCwd: string | undefined,
  name: string,
  format: string,
): Record<string, unknown> {
  const sessionDir = ensureSessionDir(workspaceCwd);
  const sessionName = validateSessionName(name);
  const envelope = readEnvelope(sessionPath(sessionDir, sessionName));
  const normalizedFormat = format === 'json' ? 'json' : 'markdown';
  if (normalizedFormat === 'json') {
    return { name: sessionName, format: 'json', content: JSON.stringify(envelope || {}, null, 2), source: 'local' };
  }
  const lines = [`# Theseus session: ${sessionName}`, ''];
  for (const item of historyForUi(envelope)) {
    const role = String(item.role || 'message');
    const text = String(item.text || '').trim();
    if (text) lines.push(`## ${role}`, '', text, '');
  }
  return { name: sessionName, format: 'markdown', content: lines.join('\n'), source: 'local' };
}

export function localSessionSnapshot(
  workspaceCwd: string | undefined,
  current = 'default',
): LocalSessionActionResult {
  const sessionDir = sessionDirectory(workspaceCwd);
  const currentName = current || 'default';
  const envelope = sessionDir ? readEnvelope(sessionPath(sessionDir, currentName)) : {};
  const planState = envelope.plan_state && typeof envelope.plan_state === 'object' && !Array.isArray(envelope.plan_state)
    ? envelope.plan_state as Record<string, unknown>
    : null;
  return {
    current: currentName,
    sessions: listLocalSessionSummaries(workspaceCwd, currentName),
    history: historyForUi(envelope),
    planState,
  };
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

function historyForUi(envelope: Record<string, unknown>): Array<Record<string, unknown>> {
  const rawHistory = Array.isArray(envelope)
    ? envelope
    : Array.isArray(envelope.history)
      ? envelope.history
      : [];
  const history: Array<Record<string, unknown>> = [];
  const pendingTools = new Map<string, Record<string, unknown>>();
  for (const item of rawHistory) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const message = item as Record<string, unknown>;
    const role = typeof message.role === 'string' ? message.role : 'message';
    const text = messageText(message, pendingTools, history);
    if (text) history.push({ type: 'message', role, text });
  }
  return history;
}

function messageText(
  message: Record<string, unknown>,
  pendingTools: Map<string, Record<string, unknown>>,
  history: Array<Record<string, unknown>>,
): string {
  if (typeof message.text === 'string') return message.text;
  const content = message.content;
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  const chunks: string[] = [];
  for (const block of content) {
    if (typeof block === 'string') {
      chunks.push(block);
    } else if (block && typeof block === 'object' && !Array.isArray(block)) {
      const record = block as Record<string, unknown>;
      if (typeof record.text === 'string') {
        chunks.push(record.text);
      } else if (record.type === 'tool_use') {
        const toolUseId = typeof record.id === 'string' ? record.id : '';
        if (toolUseId) {
          pendingTools.set(toolUseId, {
            tool_use_id: toolUseId,
            tool_name: typeof record.name === 'string' ? record.name : 'tool',
            tool_input: record.input && typeof record.input === 'object' ? record.input : {},
          });
        }
      } else if (record.type === 'tool_result') {
        const toolUseId = typeof record.tool_use_id === 'string' ? record.tool_use_id : '';
        const tool = toolUseId ? pendingTools.get(toolUseId) : undefined;
        if (toolUseId) pendingTools.delete(toolUseId);
        const isError = record.is_error === true;
        history.push({
          type: 'tool',
          tool_use_id: toolUseId,
          tool_name: typeof tool?.tool_name === 'string' ? tool.tool_name : 'tool_result',
          tool_input: tool?.tool_input || {},
          output: record.content ?? '',
          is_error: isError,
          status: isError ? 'failed' : 'done',
        });
      }
    }
  }
  return chunks.filter(Boolean).join('\n');
}
