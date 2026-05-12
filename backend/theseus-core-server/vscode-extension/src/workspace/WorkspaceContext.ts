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
  if (!cursor || userAlreadyMentionedFile(text, cursor.file)) return text;
  return `@${cursor.file}:${cursor.line}\n${text}`;
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

function normalizeMentionFile(value: string): string {
  return normalizeMentionPath(value).replace(/:\d+$/, '');
}

function userAlreadyMentionedFile(text: string, file: string): boolean {
  const target = normalizeMentionFile(file);
  const matches = text.matchAll(/@(?:"([^"]+)"|([^\s]+))/g);
  for (const match of matches) {
    if (normalizeMentionFile(match[1] || match[2] || '') === target) {
      return true;
    }
  }
  return false;
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
