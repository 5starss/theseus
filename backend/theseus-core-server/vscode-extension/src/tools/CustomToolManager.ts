import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { execFile } from 'child_process';
import { promisify } from 'util';

import { getConfiguredPythonPath, getCustomToolSearchRoots, getPythonPath } from '../workspace/WorkspaceContext';

const execFileAsync = promisify(execFile);
const PYTHON_PROBE_MAX_BUFFER = 1024 * 1024 * 4;
const SAFE_PACKAGE_NAME = /^[A-Za-z0-9_.-]+$/;
const PACKAGE_DENYLIST = new Set(['theseus_engine', 'src']);

export type CustomToolSummary = {
  toolName: string;
  fileName: string;
  permissionLevel: number | string;
  status: string;
  isActive: boolean;
  loadState?: 'available' | 'unavailable' | 'inactive' | string;
  importError?: string;
  missingModules?: string[];
  installCandidates?: string[];
  dependencies?: string[];
  canInstall?: boolean;
  installDisabledReason?: string;
  canRegister?: boolean;
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

type PythonInventoryItem = CustomToolSummary & Record<string, unknown>;

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

function uniqueStrings(values: Iterable<string | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

function hasTheseusEngine(root: string): boolean {
  return fs.existsSync(path.join(root, 'theseus_engine'));
}

function resolveCoreRoot(roots: string[]): string | undefined {
  return roots.find(hasTheseusEngine);
}

function customToolDirsFromRoots(roots: string[]): string[] {
  const candidates: string[] = [];
  for (const root of roots) {
    candidates.push(path.join(root, 'custom_tools'));
    candidates.push(path.join(root, 'theseus_engine', 'custom_tools'));
  }
  return uniqueStrings(candidates.map(candidate => fs.existsSync(candidate) ? candidate : undefined));
}

function listRuntimeMetadataFiles(roots: string[]): string[] {
  const files: string[] = [];
  const seen = new Set<string>();
  for (const dir of customToolDirsFromRoots(roots)) {
    let names: string[] = [];
    try {
      names = fs.readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of names) {
      if (!name.endsWith('.meta.json') || name.startsWith('_')) continue;
      const filePath = path.join(dir, name);
      const key = pathKey(filePath);
      if (seen.has(key)) continue;
      seen.add(key);
      files.push(filePath);
    }
  }
  return files;
}

function pathKey(filePath: string | undefined): string {
  return path.normalize(String(filePath || '')).toLowerCase();
}

function safePackageNames(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return uniqueStrings(
    values
      .map(value => String(value || '').trim())
      .filter(value => SAFE_PACKAGE_NAME.test(value) && !PACKAGE_DENYLIST.has(value)),
  );
}

async function runPythonInventoryProbe(roots: string[]): Promise<PythonInventoryItem[]> {
  const coreRoot = resolveCoreRoot(roots);
  if (!coreRoot) return [];
  const pythonExec = getPythonPath();
  if (!pythonExec) return [];
  const extraDirs = customToolDirsFromRoots(roots);
  const script = [
    'import json, sys',
    'from theseus_engine.tools.core.tool_factory import scan_custom_tool_inventory',
    'extra_dirs = json.loads(sys.argv[1])',
    'print(json.dumps(scan_custom_tool_inventory(extra_dirs=extra_dirs), ensure_ascii=False))',
  ].join('; ');
  const env = {
    ...process.env,
    PYTHONPATH: uniqueStrings([coreRoot, process.env.PYTHONPATH]).join(path.delimiter),
  };
  const { stdout } = await execFileAsync(
    pythonExec,
    ['-c', script, JSON.stringify(extraDirs)],
    { cwd: coreRoot, env, maxBuffer: PYTHON_PROBE_MAX_BUFFER },
  );
  const parsed = JSON.parse(stdout || '[]');
  return Array.isArray(parsed) ? parsed as PythonInventoryItem[] : [];
}

function mergeProbeSummary(
  base: CustomToolSummary,
  probe: PythonInventoryItem | undefined,
): CustomToolSummary {
  const hasInstallPython = Boolean(getConfiguredPythonPath());
  if (!probe) {
    const validation = validateCustomToolPair(base.metadataPath);
    return {
      ...base,
      loadState: base.isActive === false ? 'inactive' : validation.success ? 'available' : 'unavailable',
      validationResult: base.validationResult || validation,
      importError: validation.success ? '' : validation.message,
      missingModules: [],
      installCandidates: [],
      dependencies: safePackageNames((base as Record<string, unknown>).dependencies),
      canInstall: false,
      canRegister: validation.success && base.isActive !== false,
    };
  }
  const loadState = String(probe.loadState || (probe.isActive === false ? 'inactive' : 'available'));
  const importError = typeof probe.importError === 'string' ? probe.importError : '';
  const installCandidates = safePackageNames(probe.installCandidates);
  const canInstall = hasInstallPython && Boolean(probe.canInstall) && installCandidates.length > 0;
  return {
    ...base,
    ...probe,
    loadState,
    importError,
    missingModules: safePackageNames(probe.missingModules),
    installCandidates,
    dependencies: safePackageNames(probe.dependencies),
    canInstall,
    installDisabledReason: !canInstall && installCandidates.length > 0 && !hasInstallPython
      ? 'Set theseus.pythonPath to install dependencies.'
      : '',
    canRegister: Boolean(probe.canRegister) && loadState === 'available',
    validationResult: {
      success: loadState === 'available',
      message: loadState === 'available'
        ? 'Tool imports successfully.'
        : importError || String(probe.status || 'Tool is not available.'),
    },
  };
}

export function validateCustomToolPair(metadataPath: string): ToolValidationResult {
  const meta = readJsonObject(metadataPath);
  if (!meta) return { success: false, message: 'Invalid meta.json' };
  const configuredModulePath = typeof meta.modulePath === 'string'
    ? meta.modulePath
    : typeof meta.module_path === 'string'
      ? meta.module_path
      : '';
  const modulePathLooksLikeFile = /[\\/]/.test(configuredModulePath) || configuredModulePath.endsWith('.py');
  const fileName = typeof meta.fileName === 'string'
    ? meta.fileName
    : modulePathLooksLikeFile
      ? path.basename(configuredModulePath)
    : `${path.basename(metadataPath).replace(/\.meta\.json$/i, '')}.py`;
  const modulePath = modulePathLooksLikeFile && path.isAbsolute(configuredModulePath)
    ? configuredModulePath
    : path.join(path.dirname(metadataPath), modulePathLooksLikeFile ? configuredModulePath : fileName);
  if (!fs.existsSync(modulePath)) {
    return { success: false, message: `Missing module file: ${fileName}` };
  }
  try {
    const code = fs.readFileSync(modulePath, 'utf8');
    const hasBaseTool = /\bBaseTool\b/.test(code) || /\bclass\s+\w+\s*\([^)]*Tool[^)]*\)/.test(code);
    const hasExecute = /\b(?:async\s+def|def)\s+execute\s*\(/.test(code);
    if (!hasBaseTool || !hasExecute) {
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

export async function disableCustomTool(metadataPath: string): Promise<ToolValidationResult> {
  const meta = readJsonObject(metadataPath);
  if (!meta) return { success: false, message: 'Invalid meta.json' };
  meta.isActive = false;
  meta.status = 'inactive';
  meta.updatedAt = new Date().toISOString();
  await fs.promises.writeFile(metadataPath, JSON.stringify(meta, null, 2) + '\n', 'utf8');
  return { success: true, message: 'Custom tool disabled.' };
}

function findToolByPath(tools: CustomToolSummary[], metadataPath?: string, modulePath?: string): CustomToolSummary | undefined {
  const metadataKey = pathKey(metadataPath);
  const moduleKey = pathKey(modulePath);
  return tools.find(tool =>
    (metadataKey && pathKey(tool.metadataPath) === metadataKey)
    || (moduleKey && pathKey(tool.modulePath) === moduleKey)
  );
}

export async function installCustomToolDependencies(
  metadataPath?: string,
  modulePath?: string,
): Promise<ToolValidationResult & { packages?: string[] }> {
  const tools = await loadCustomToolSummaries();
  const tool = findToolByPath(tools, metadataPath, modulePath);
  if (!tool) return { success: false, message: 'Custom tool not found.' };
  const packages = safePackageNames(tool.installCandidates);
  if (!packages.length) {
    return { success: false, message: 'No safe dependency install candidates were found.' };
  }
  const configuredPythonExec = getConfiguredPythonPath();
  if (!configuredPythonExec) {
    return { success: false, message: 'theseus.pythonPath is not configured.' };
  }
  const choice = await vscode.window.showWarningMessage(
    `Install dependencies for ${tool.toolName || tool.fileName}?\n\n${packages.join(' ')}`,
    { modal: true },
    'Install',
    'Cancel',
  );
  if (choice !== 'Install') {
    return { success: false, message: 'Dependency installation cancelled.', packages };
  }
  const roots = getCustomToolSearchRoots();
  const coreRoot = resolveCoreRoot(roots);
  const env = coreRoot
    ? { ...process.env, PYTHONPATH: uniqueStrings([coreRoot, process.env.PYTHONPATH]).join(path.delimiter) }
    : process.env;
  try {
    await execFileAsync(
      configuredPythonExec,
      ['-m', 'pip', 'install', ...packages],
      { cwd: coreRoot || undefined, env, maxBuffer: PYTHON_PROBE_MAX_BUFFER },
    );
    return {
      success: true,
      message: `Installed dependencies: ${packages.join(', ')}`,
      packages,
    };
  } catch (err) {
    return {
      success: false,
      message: `Dependency installation failed: ${err instanceof Error ? err.message : String(err)}`,
      packages,
    };
  }
}

export async function registerCustomTool(metadataPath: string): Promise<ToolValidationResult> {
  const validation = validateCustomToolPair(metadataPath);
  if (!validation.success) return validation;
  return { success: true, message: 'Custom tool is valid. Refreshing runtime registry.' };
}

export async function loadCustomToolSummaries(): Promise<CustomToolSummary[]> {
  const roots = getCustomToolSearchRoots();
  if (!roots.length) return [];

  const seen = new Set<string>();
  const metadataFiles = listRuntimeMetadataFiles(roots);

  const probeItems = await runPythonInventoryProbe(roots).catch(() => []);
  const probeByMetadata = new Map(probeItems.map(item => [pathKey(item.metadataPath), item]));
  const probeByModule = new Map(probeItems.map(item => [pathKey(item.modulePath), item]));
  const tools: CustomToolSummary[] = [];
  for (const metadataPath of metadataFiles) {
    if (seen.has(metadataPath)) continue;
    seen.add(metadataPath);

    const meta = readJsonObject(metadataPath);
    if (!meta) continue;
    const fallbackName = path.basename(metadataPath).replace(/\.meta\.json$/i, '');
    const fileName = typeof meta.fileName === 'string'
      ? meta.fileName
      : `${fallbackName}.py`;
    const modulePath = path.join(path.dirname(metadataPath), fileName);
    const summary = {
      toolName: String(meta.toolName || fallbackName),
      fileName,
      permissionLevel: typeof meta.permissionLevel === 'number' || typeof meta.permissionLevel === 'string'
        ? meta.permissionLevel
        : '',
      status: String(meta.status || 'unknown'),
      isActive: meta.isActive !== false,
      validationResult: meta.validationResult,
      dependencies: safePackageNames(meta.dependencies),
      modulePath,
      metadataPath,
    };
    tools.push(mergeProbeSummary(
      summary,
      probeByMetadata.get(pathKey(metadataPath)) || probeByModule.get(pathKey(modulePath)),
    ));
  }

  const known = new Set([
    ...tools.map(tool => pathKey(tool.metadataPath)).filter(Boolean),
    ...tools.map(tool => pathKey(tool.modulePath)).filter(Boolean),
  ]);
  for (const item of probeItems) {
    const metadataKey = pathKey(item.metadataPath);
    const moduleKey = pathKey(item.modulePath);
    if ((metadataKey && known.has(metadataKey)) || (moduleKey && known.has(moduleKey))) continue;
    tools.push(mergeProbeSummary({
      toolName: String(item.toolName || item.fileName || 'unknown'),
      fileName: String(item.fileName || path.basename(String(item.modulePath || '')) || 'unknown.py'),
      permissionLevel: typeof item.permissionLevel === 'number' || typeof item.permissionLevel === 'string'
        ? item.permissionLevel
        : '',
      status: String(item.status || 'unknown'),
      isActive: item.isActive !== false,
      modulePath: typeof item.modulePath === 'string' ? item.modulePath : undefined,
      metadataPath: typeof item.metadataPath === 'string' ? item.metadataPath : '',
    }, item));
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
