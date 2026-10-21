import { createHash } from 'node:crypto';
import { existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { delimiter, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cwd = resolve(root, 'frontend');
const started = Date.now();
console.log(`[Frontend] Node.js ${process.versions.node}. Đang kiểm tra thư viện...`);
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
  console.error('Node.js 22.12 or newer is required (Node 24 LTS recommended).');
  process.exit(1);
}
function npmCli() {
  // Invoke npm through Node, avoiding cmd.exe quoting problems in Windows paths with spaces.
  const dirs = [dirname(process.execPath), ...(process.env.PATH ?? '').split(delimiter).filter(Boolean)];
  for (const dir of dirs) {
    const candidates = [resolve(dir, 'node_modules/npm/bin/npm-cli.js'), resolve(dir, '../lib/node_modules/npm/bin/npm-cli.js')];
    const executable = resolve(dir, process.platform === 'win32' ? 'npm.cmd' : 'npm');
    if (existsSync(executable)) candidates.push(resolve(dirname(realpathSync(executable)), 'npm-cli.js'));
    const cli = candidates.find(existsSync);
    if (cli) return cli;
  }
  console.error('[Frontend] Không tìm thấy npm. Hãy cài Node.js LTS kèm npm rồi mở lại terminal.');
  process.exit(1);
}
async function run(script, args, installing = false) {
  const child = spawn(process.execPath, [script, ...args], { cwd, stdio: 'inherit' });
  const forwardInterrupt = () => child.kill('SIGINT');
  process.on('SIGINT', forwardInterrupt);
  const heartbeat = installing ? setInterval(() => {
    console.log(`[Frontend] Đang cài thư viện (${Math.round((Date.now() - started) / 1000)} giây). Lần đầu có thể mất vài phút; nếu npm báo lỗi mạng, kiểm tra kết nối tới registry.npmjs.org.`);
  }, 15_000) : null;
  const code = await new Promise(resolveCode => {
    child.once('error', error => { console.error(`[Frontend] Không thể khởi chạy: ${error.message}`); resolveCode(1); });
    child.once('exit', (status, signal) => resolveCode(status ?? (signal === 'SIGINT' ? 130 : 1)));
  });
  if (heartbeat) clearInterval(heartbeat);
  process.removeListener('SIGINT', forwardInterrupt);
  if (code !== 0) process.exit(code);
}
const digest = createHash('sha256').update(readFileSync(resolve(cwd, 'package-lock.json'))).digest('hex');
const stamp = resolve(cwd, 'node_modules/.workspace-lock.sha256');
if (!existsSync(resolve(cwd, 'node_modules/vite/bin/vite.js')) || !existsSync(stamp) || readFileSync(stamp, 'utf8') !== digest) {
  console.log('[Frontend] Cần cài/cập nhật thư viện: chưa có bản cài hoàn tất hoặc package-lock.json đã đổi.');
  console.log('[Frontend] Dùng npm cache; tiến trình và lỗi cài đặt sẽ hiển thị bên dưới.');
  await run(npmCli(), ['ci', '--no-fund', '--no-audit', '--prefer-offline', '--cache', resolve(root, '.cache/npm')], true);
  writeFileSync(stamp, digest);
} else console.log('[Frontend] Thư viện đã sẵn sàng, bỏ qua npm install.');
console.log(`[Frontend] Chuẩn bị xong sau ${((Date.now() - started) / 1000).toFixed(1)} giây.`);
if (process.argv.includes('--run')) {
  console.log('[Frontend] Đang mở Vite tại http://127.0.0.1:5173 — giữ cửa sổ này mở khi sử dụng.');
  await run(resolve(cwd, 'node_modules/vite/bin/vite.js'), ['--host', '127.0.0.1', '--port', '5173', '--strictPort']);
} else console.log('[Frontend] Có thể chạy run-frontend.bat để mở ứng dụng.');
