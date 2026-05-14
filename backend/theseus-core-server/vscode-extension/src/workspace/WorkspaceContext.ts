import * as fs from 'fs';
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

export function hasTheseusEngine(dir: string): boolean {
  return fs.existsSync(path.join(dir, 'theseus_engine'));
}

export function getCoreRoot(context: vscode.ExtensionContext): string | undefined {
  const cfg = vscode.workspace.getConfiguration('theseus');
  const corePath = cfg.get<string>('corePath')?.trim();
  if (corePath) return corePath;

  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    if (hasTheseusEngine(folder.uri.fsPath)) return folder.uri.fsPath;
  }

  const devRoot = path.resolve(context.extensionUri.fsPath, '..');
  if (hasTheseusEngine(devRoot)) return devRoot;

  return undefined;
}

export function getWorkspaceCwd(): string | undefined {
  const cfg = vscode.workspace.getConfiguration('theseus');
  const explicit = cfg.get<string>('workspacePath')?.trim();
  if (explicit) return explicit;
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
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

  return uris
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
}

export function getCustomToolSearchRoots(): string[] {
  const roots = new Set<string>();
  const workspace = getWorkspaceCwd();
  if (workspace) roots.add(workspace);
  const corePath = vscode.workspace.getConfiguration('theseus').get<string>('corePath')?.trim();
  if (corePath) roots.add(corePath);
  const fallbackCore = getCoreRootPathFallback();
  if (fallbackCore) roots.add(fallbackCore);
  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    roots.add(folder.uri.fsPath);
    if (hasTheseusEngine(folder.uri.fsPath)) roots.add(folder.uri.fsPath);
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
