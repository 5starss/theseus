import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

const FILE_SEARCH_EXCLUDE =
  '**/{node_modules,.git,out,dist,build,.next,target,.venv,venv,__pycache__}/**';
const FILE_SEARCH_LIMIT = 500;
const FILE_SEARCH_FALLBACK_LIMIT = 5000;
const FILE_SUGGESTION_LIMIT = 30;

export type ActiveCursorContext = {
  file: string;
  line: number;
};

export type RuntimeModeSetting = 'auto' | 'source-python' | 'bundled-runner';

export function hasTheseusEngine(dir: string): boolean {
  return fs.existsSync(path.join(dir, 'theseus_engine'));
}

function firstWorkspaceFolderPath(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function workspaceFolderPath(name?: string): string | undefined {
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (!name) return folders[0]?.uri.fsPath;
  return folders.find(folder => folder.name === name)?.uri.fsPath;
}

export function expandTheseusPath(value: string | undefined): string {
  const raw = value?.trim() || '';
  if (!raw) return '';

  let expanded = raw.replace(/\$\{workspaceFolder(?::([^}]+))?\}/g, (_match, name: string | undefined) => {
    return workspaceFolderPath(name) || '';
  });

  expanded = expanded.replace(/\$\{userHome\}/g, os.homedir());
  expanded = expanded.replace(/\$\{env:([^}]+)\}/g, (_match, name: string) => process.env[name] || '');

  if (expanded === '~' || expanded.startsWith(`~${path.sep}`) || expanded.startsWith('~/') || expanded.startsWith('~\\')) {
    expanded = path.join(os.homedir(), expanded.slice(1));
  }

  if (!path.isAbsolute(expanded)) {
    const workspace = firstWorkspaceFolderPath();
    if (workspace) expanded = path.resolve(workspace, expanded);
  }

  return path.normalize(expanded);
}

function getTheseusPathSetting(key: string): string {
  return expandTheseusPath(vscode.workspace.getConfiguration('theseus').get<string>(key));
}

export function getRunnerPath(): string {
  return getTheseusPathSetting('runnerPath');
}

export function getConfiguredPythonPath(): string {
  return getTheseusPathSetting('pythonPath');
}

export function getPythonPath(): string {
  return getConfiguredPythonPath() || 'python';
}

export function getRuntimeModeSetting(): RuntimeModeSetting {
  const value = vscode.workspace.getConfiguration('theseus').get<string>('runtimeMode')?.trim();
  if (value === 'source-python' || value === 'bundled-runner') return value;
  return 'auto';
}

export function shouldUseBundledRunner(): boolean {
  const mode = getRuntimeModeSetting();
  if (mode === 'source-python') return false;
  return !!getRunnerPath();
}

export function getCoreRoot(context: vscode.ExtensionContext): string | undefined {
  const corePath = getTheseusPathSetting('corePath');
  if (corePath && hasTheseusEngine(corePath)) return corePath;

  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    if (hasTheseusEngine(folder.uri.fsPath)) return folder.uri.fsPath;
    const nestedCore = path.join(folder.uri.fsPath, 'backend', 'theseus-core-server');
    if (hasTheseusEngine(nestedCore)) return nestedCore;
  }

  const devRoot = path.resolve(context.extensionUri.fsPath, '..');
  if (hasTheseusEngine(devRoot)) return devRoot;

  return undefined;
}

export function getWorkspaceCwd(): string | undefined {
  const explicit = getTheseusPathSetting('workspacePath');
  if (explicit) return explicit;
  return firstWorkspaceFolderPath();
}

export function getCoreRootPathFallback(): string | undefined {
  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    if (hasTheseusEngine(folder.uri.fsPath)) return folder.uri.fsPath;
  }
  const extension = vscode.extensions.getExtension('theseus.theseus-vscode');
  const devRoot = extension ? path.resolve(extension.extensionUri.fsPath, '..') : '';
  if (devRoot && hasTheseusEngine(devRoot)) return devRoot;
  return undefined;
}

export function relativeToRoot(root: string, uri: vscode.Uri): string {
  const rel = path.relative(root, uri.fsPath);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) {
    return vscode.workspace.asRelativePath(uri).replace(/\\/g, '/');
  }
  return rel.replace(/\\/g, '/');
}

export function getActiveCursorContext(): ActiveCursorContext | undefined {
  const editor = vscode.window.activeTextEditor;
  const root = getWorkspaceCwd();
  if (!editor || !root) return undefined;
  return {
    file: relativeToRoot(root, editor.document.uri),
    line: editor.selection.active.line + 1,
  };
}

export function injectCursorContext(text: string): string {
  const cursor = getActiveCursorContext();
  if (
    !cursor
    || text.trimStart().startsWith('/')
    || userMentionedAnyFile(text)
    || !shouldAttachActiveCursorContext(text)
  ) {
    return text;
  }
  return [
    text,
    '',
    '---',
    'IDE auxiliary context:',
    `- Active editor file: @${cursor.file}:${cursor.line}`,
    '- This context was attached only because the user referred to the active editor. Ignore it if it is not relevant to the task.',
  ].join('\n');
}

export async function findMentionFiles(query: string): Promise<string[]> {
  const root = getWorkspaceCwd();
  if (!root) return [];

  const normalizedQuery = normalizeMentionPath(query);
  const pattern = makeFileSearchPattern(query);
  let uris = await vscode.workspace.findFiles(
    new vscode.RelativePattern(root, pattern),
    FILE_SEARCH_EXCLUDE,
    FILE_SEARCH_LIMIT,
  );

  if (normalizedQuery.includes('_')) {
    const filtered = uris.filter(uri =>
      normalizeMentionPath(relativeToRoot(root, uri)).includes(normalizedQuery),
    );
    if (!filtered.length) {
      uris = await vscode.workspace.findFiles(
        new vscode.RelativePattern(root, '**/*'),
        FILE_SEARCH_EXCLUDE,
        FILE_SEARCH_FALLBACK_LIMIT,
      );
    }
  }

  const fileResults = uris
    .map(uri => relativeToRoot(root, uri))
    .filter(file => !normalizedQuery || normalizeMentionPath(file).includes(normalizedQuery))
    .sort((a, b) => {
      const an = normalizeMentionPath(a);
      const bn = normalizeMentionPath(b);
      const aBase = path.posix.basename(an);
      const bBase = path.posix.basename(bn);
      const aScore = (an.startsWith(normalizedQuery) ? 0 : 2) +
        (aBase.startsWith(normalizedQuery) ? 0 : 1);
      const bScore = (bn.startsWith(normalizedQuery) ? 0 : 2) +
        (bBase.startsWith(normalizedQuery) ? 0 : 1);
      return aScore - bScore || a.length - b.length || a.localeCompare(b);
    })
    .slice(0, FILE_SUGGESTION_LIMIT);

  const specialMentions = ['terminal', 'folder', 'problems'].filter(m =>
    !normalizedQuery || m.includes(normalizedQuery)
  );

  return [...specialMentions, ...fileResults];
}

export function getCustomToolSearchRoots(): string[] {
  const roots = new Set<string>();
  const workspace = getWorkspaceCwd();
  if (workspace) roots.add(workspace);
  const corePath = getTheseusPathSetting('corePath');
  if (corePath) roots.add(corePath);
  const fallbackCore = getCoreRootPathFallback();
  if (fallbackCore) roots.add(fallbackCore);
  if (workspace) {
    const nestedCore = path.join(workspace, 'backend', 'theseus-core-server');
    if (hasTheseusEngine(nestedCore)) roots.add(nestedCore);
  }
  return [...roots];
}

export async function findMetaFiles(pattern: string, root: string): Promise<vscode.Uri[]> {
  return vscode.workspace.findFiles(
    new vscode.RelativePattern(root, pattern),
    FILE_SEARCH_EXCLUDE,
    FILE_SEARCH_FALLBACK_LIMIT,
  );
}

function normalizeMentionPath(value: string): string {
  return value.replace(/^"/, '').replace(/"$/, '').replace(/\\/g, '/').replace(/^\/+/, '').toLowerCase();
}

function userMentionedAnyFile(text: string): boolean {
  return /@(?:"[^"]+"|[^\s]+)/.test(text);
}

function shouldAttachActiveCursorContext(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) return false;
  return [
    /현재\s*(열린|보고\s*있는|켜진)?\s*(파일|문서|코드|탭|창)/,
    /(현재|지금)?\s*(ide|vscode|에디터)?\s*(에\s*)?(떠\s*있는|열려\s*있는|보고\s*있는|켜져\s*있는)\s*(파일|문서|코드|탭|창)/,
    /(이|해당)\s*(파일|문서|코드|부분)/,
    /(여기|이거|이 부분)\s*(봐|분석|수정|고쳐|설명|리뷰|확인)?/,
    /\b(this|current|active|opened)\s+(file|document|code|editor|tab)\b/,
    /\b(here|this)\s+(code|file|section)\b/,
  ].some(pattern => pattern.test(normalized));
}

function escapeGlobSegment(value: string): string {
  return value.replace(/[{}[\]*?\\]/g, (m) => `[${m}]`);
}

function makeFileSearchPattern(query: string): string {
  const normalized = normalizeMentionPath(query).trim();
  if (!normalized) return '**/*';

  const segments = normalized.split('/').filter(Boolean);
  const last = segments[segments.length - 1] || normalized;
  return `**/*${escapeGlobSegment(last)}*`;
}

export async function resolveContextMentions(text: string): Promise<string> {
  let resolvedText = text;

  if (resolvedText.includes('@problems')) {
    const diagnostics = vscode.languages.getDiagnostics();
    const problems = diagnostics.flatMap(([uri, diags]) =>
      diags.map(d => `${vscode.workspace.asRelativePath(uri)}:${d.range.start.line + 1} - ${d.message} [${d.source || 'unknown'}]`)
    ).slice(0, 50).join('\n');

    resolvedText = resolvedText.replace(/@problems/g, problems ? `\n--- VSCode Problems ---\n${problems}\n-----------------------\n` : '\n--- No Problems found ---\n');
  }

  if (resolvedText.includes('@folder')) {
    const root = getWorkspaceCwd();
    let tree = 'No workspace opened.';
    if (root) {
      try {
        // Very simple flat list of top-level files for brevity
        const files = await vscode.workspace.findFiles(new vscode.RelativePattern(root, '**/*'), FILE_SEARCH_EXCLUDE, 100);
        tree = files.map(f => relativeToRoot(root, f)).sort().join('\n');
      } catch (err) {
        tree = 'Error reading folder structure.';
      }
    }
    resolvedText = resolvedText.replace(/@folder/g, `\n--- Folder Structure ---\n${tree}\n------------------------\n`);
  }

  if (resolvedText.includes('@terminal')) {
    resolvedText = resolvedText.replace(/@terminal/g, `\n--- Terminal ---\n(Terminal reading is not directly supported by VSCode API. Please copy-paste the logs manually.)\n----------------\n`);
  }

  return resolvedText;
}
