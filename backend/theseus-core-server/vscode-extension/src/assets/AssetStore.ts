import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { getCoreRootPathFallback, getWorkspaceCwd } from '../workspace/WorkspaceContext';

function sanitizeAssetName(name: string): string {
  const ext = path.extname(name || '').toLowerCase() || '.png';
  const base = path.basename(name || 'pasted-image', ext).replace(/[^A-Za-z0-9_.-]+/g, '_') || 'image';
  return `${base}-${Date.now()}${ext}`;
}

export async function saveAssetToWorkspace(name: string, data: unknown): Promise<string> {
  const root = getWorkspaceCwd();
  if (!root) throw new Error('No workspace is open.');
  if (typeof data !== 'string' || !data) throw new Error('Image payload is empty.');
  const assetDir = path.join(root, '.theseus', 'assets');
  await fs.promises.mkdir(assetDir, { recursive: true });
  const fileName = sanitizeAssetName(name);
  const base64 = data.replace(/^data:[^;]+;base64,/, '');
  await fs.promises.writeFile(path.join(assetDir, fileName), Buffer.from(base64, 'base64'));
  return `.theseus/assets/${fileName}`.replace(/\\/g, '/');
}

export async function resolveReadableUri(candidate: unknown): Promise<vscode.Uri | undefined> {
  if (typeof candidate !== 'string' || !candidate.trim()) return undefined;
  const raw = candidate.trim();
  const roots = [getWorkspaceCwd(), getCoreRootPathFallback()].filter((v): v is string => !!v);
  const paths = path.isAbsolute(raw)
    ? [raw]
    : roots.map(root => path.resolve(root, raw));
  for (const p of paths) {
    if (fs.existsSync(p)) return vscode.Uri.file(p);
  }
  return undefined;
}
