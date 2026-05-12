import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { findMetaFiles, getCustomToolSearchRoots } from '../workspace/WorkspaceContext';

export type CustomToolSummary = {
  toolName: string;
  fileName: string;
  permissionLevel: number | string;
  status: string;
  isActive: boolean;
  validationResult?: unknown;
  modulePath?: string;
  metadataPath: string;
};

export type ToolValidationResult = {
  success: boolean;
  message: string;
};

export type CustomToolChange = {
  action: string;
  file: string;
  metadataPath: string;
  validation: ToolValidationResult;
};

function readJsonObject(filePath: string): Record<string, unknown> | undefined {
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : undefined;
  } catch {
    return undefined;
  }
}

export function validateCustomToolPair(metadataPath: string): ToolValidationResult {
  const meta = readJsonObject(metadataPath);
  if (!meta) return { success: false, message: 'Invalid meta.json' };
  const fileName = typeof meta.fileName === 'string'
    ? meta.fileName
    : `${path.basename(metadataPath).replace(/\.meta\.json$/i, '')}.py`;
  const modulePath = path.join(path.dirname(metadataPath), fileName);
  if (!fs.existsSync(modulePath)) {
    return { success: false, message: `Missing module file: ${fileName}` };
  }
  try {
    const code = fs.readFileSync(modulePath, 'utf8');
    if (!/\bBaseTool\b/.test(code) || !/\bexecute\s*\(/.test(code)) {
      return { success: false, message: `${fileName} does not look like a BaseTool module` };
    }
  } catch (err) {
    return { success: false, message: err instanceof Error ? err.message : String(err) };
  }
  return { success: true, message: `${fileName} and ${path.basename(metadataPath)} look valid` };
}

export async function updateCustomToolPermission(
  metadataPath: string,
  permissionLevel: number,
): Promise<ToolValidationResult> {
  if (!Number.isInteger(permissionLevel) || permissionLevel < 1 || permissionLevel > 5) {
    return { success: false, message: 'permissionLevel must be an integer from 1 to 5' };
  }
  const meta = readJsonObject(metadataPath);
  if (!meta) return { success: false, message: 'Invalid meta.json' };
  meta.permissionLevel = permissionLevel;
  meta.updatedAt = new Date().toISOString();
  await fs.promises.writeFile(metadataPath, JSON.stringify(meta, null, 2) + '\n', 'utf8');
  return validateCustomToolPair(metadataPath);
}

export async function loadCustomToolSummaries(): Promise<CustomToolSummary[]> {
  const roots = getCustomToolSearchRoots();
  if (!roots.length) return [];

  const seen = new Set<string>();
  const patterns = [
    'theseus_engine/custom_tools/*.meta.json',
    '**/theseus_engine/custom_tools/*.meta.json',
    'custom_tools/*.meta.json',
    '**/custom_tools/*.meta.json',
    'custom_tools/projects/**/*.meta.json',
    '**/custom_tools/projects/**/*.meta.json',
  ];
  const uris = (await Promise.all(
    roots.flatMap(root => patterns.map(pattern => findMetaFiles(pattern, root))),
  )).flat();

  const tools: CustomToolSummary[] = [];
  for (const uri of uris) {
    const metadataPath = uri.fsPath;
    if (seen.has(metadataPath)) continue;
    seen.add(metadataPath);

    const meta = readJsonObject(metadataPath);
    if (!meta) continue;
    const fallbackName = path.basename(metadataPath).replace(/\.meta\.json$/i, '');
    const fileName = typeof meta.fileName === 'string'
      ? meta.fileName
      : `${fallbackName}.py`;
    const modulePath = path.join(path.dirname(metadataPath), fileName);
    tools.push({
      toolName: String(meta.toolName || fallbackName),
      fileName,
      permissionLevel: typeof meta.permissionLevel === 'number' || typeof meta.permissionLevel === 'string'
        ? meta.permissionLevel
        : '',
      status: String(meta.status || 'unknown'),
      isActive: meta.isActive !== false,
      validationResult: meta.validationResult,
      modulePath,
      metadataPath,
    });
  }

  return tools.sort((a, b) => a.toolName.localeCompare(b.toolName));
}

export function createCustomToolWatchers(
  onChange: (change: CustomToolChange) => void,
): vscode.FileSystemWatcher[] {
  const toolCodeWatcher = vscode.workspace.createFileSystemWatcher('**/custom_tools/**/*.py');
  const toolMetaWatcher = vscode.workspace.createFileSystemWatcher('**/custom_tools/**/*.meta.json');
  const emitToolChange = (action: string) => (uri: vscode.Uri) => {
    const file = vscode.workspace.asRelativePath(uri);
    const metadataPath = uri.fsPath.endsWith('.meta.json')
      ? uri.fsPath
      : uri.fsPath.replace(/\.py$/i, '.meta.json');
    const validation = fs.existsSync(metadataPath)
      ? validateCustomToolPair(metadataPath)
      : { success: false, message: 'Missing meta.json' };
    onChange({ action, file, metadataPath, validation });
  };
  for (const watcher of [toolCodeWatcher, toolMetaWatcher]) {
    watcher.onDidCreate(emitToolChange('created'));
    watcher.onDidChange(emitToolChange('changed'));
    watcher.onDidDelete(emitToolChange('deleted'));
  }
  return [toolCodeWatcher, toolMetaWatcher];
}
