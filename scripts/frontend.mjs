import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cwd = resolve(root, 'frontend');
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
  console.error('Node.js 22.12 or newer is required (Node 24 LTS recommended).');
  process.exit(1);
}
function npm(args) {
  const child = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', args, { cwd, stdio: 'inherit', shell: process.platform === 'win32' });
  if (child.error) { console.error('Cannot start npm. Install Node.js with npm and reopen the terminal.'); process.exit(1); }
  if (child.status !== 0) process.exit(child.status ?? 1);
}
const digest = createHash('sha256').update(readFileSync(resolve(cwd, 'package-lock.json'))).digest('hex');
const stamp = resolve(cwd, 'node_modules/.workspace-lock.sha256');
if (!existsSync(resolve(cwd, 'node_modules/vite/bin/vite.js')) || !existsSync(stamp) || readFileSync(stamp, 'utf8') !== digest) {
  npm(['ci', '--no-fund', '--cache', resolve(root, '.cache/npm')]);
  writeFileSync(stamp, digest);
}
if (process.argv.includes('--run')) npm(['run', 'dev']);
else console.log('Frontend dependencies ready.');
