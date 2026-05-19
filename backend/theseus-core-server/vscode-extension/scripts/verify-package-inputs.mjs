import { existsSync, statSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const required = [
  'package.json',
  'out/extension.js',
  'out/providers/ChatViewProvider.js',
  'media/main.js',
  'media/dispatcher.js',
  'media/components/ActivityLog.js',
  'media/components/SessionMenu.js',
  'media/components/HealthPanel.js',
  'resources/theseus.svg',
];

const missing = [];
for (const rel of required) {
  const full = join(root, rel);
  if (!existsSync(full) || !statSync(full).isFile()) missing.push(rel);
}

if (missing.length) {
  console.error(`Missing VSIX package inputs:\n${missing.map(item => `- ${item}`).join('\n')}`);
  process.exit(1);
}

const markerFiles = [
  'out/providers/ChatViewProvider.js',
  'media/main.js',
  'media/components/ActivityLog.js',
];

for (const rel of markerFiles) {
  const mtime = statSync(join(root, rel)).mtime.toISOString();
  console.log(`${rel} ${mtime}`);
}

