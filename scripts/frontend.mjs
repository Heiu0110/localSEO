import {
  existsSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import {
  inspectDependencies,
  stampDependencies,
} from "./frontend-dependencies.mjs";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
export const repositoryRoot = resolve(scriptDirectory, "..");
// A cold Windows install can legitimately spend several minutes downloading
// tarballs. This budget applies only when npm is needed, not on every launch.
export const DEFAULT_INSTALL_TIMEOUT = 600_000;
export function npmCli() {
  // Node -> npm-cli.js avoids cmd.exe quoting in Windows paths containing spaces.
  const dirs = [
    dirname(process.execPath),
    ...(process.env.PATH ?? "").split(delimiter).filter(Boolean),
  ];
  for (const dir of dirs) {
    const candidates = [
      resolve(dir, "node_modules/npm/bin/npm-cli.js"),
      resolve(dir, "../lib/node_modules/npm/bin/npm-cli.js"),
    ];
    const executable = resolve(
      dir,
      process.platform === "win32" ? "npm.cmd" : "npm",
    );
    try {
      if (existsSync(executable))
        candidates.push(
          resolve(dirname(realpathSync(executable)), "npm-cli.js"),
        );
    } catch {
      /* Ignore broken PATH entries. */
    }
    const cli = candidates.find(existsSync);
    if (cli) return cli;
  }
  throw new Error(
    "Không tìm thấy npm. Cài Node.js LTS kèm npm rồi mở lại terminal.",
  );
}
export function installArguments(root, timeoutMs = DEFAULT_INSTALL_TIMEOUT) {
  const args = [
    "ci",
    "--include=dev",
    "--include=optional",
    "--no-fund",
    "--no-audit",
    "--prefer-offline",
    "--fetch-retries=1",
    "--fetch-retry-mintimeout=1000",
    "--fetch-retry-maxtimeout=3000",
    `--fetch-timeout=${Math.min(120_000, Math.floor(timeoutMs / 3))}`,
    "--loglevel=http",
    "--foreground-scripts",
    "--progress=false",
  ];
  // Keep a warm repository cache from older releases. Otherwise use npm's shared
  // OS cache (or the user's configured cache), avoiding a fresh cache per ZIP.
  const configured =
    process.env.npm_config_cache || process.env.NPM_CONFIG_CACHE;
  if (!configured && existsSync(resolve(root, ".cache/npm/_cacache")))
    args.push("--cache", resolve(root, ".cache/npm"));
  return args;
}
export function stopProcessTree(
  child,
  platform = process.platform,
  spawnProcess = spawn,
) {
  if (!child.pid || child.exitCode !== null) return;
  if (platform === "win32") {
    const taskkill = resolve(
      process.env.SystemRoot || "C:\\Windows",
      "System32",
      "taskkill.exe",
    );
    const terminator = spawnProcess(
      taskkill,
      ["/PID", String(child.pid), "/T", "/F"],
      { stdio: "ignore", windowsHide: true, shell: false },
    );
    const fallback = () => {
      try {
        child.kill("SIGKILL");
      } catch {
        /* Already stopped. */
      }
    };
    terminator.once("error", fallback);
    terminator.once("close", (code) => {
      if (code !== 0) fallback();
    });
  } else {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      try {
        child.kill("SIGKILL");
      } catch {
        /* Already stopped. */
      }
    }
  }
}
export async function runCommand(
  script,
  args,
  { cwd, timeoutMs = 0, installing = false, spawnProcess = spawn } = {},
) {
  const child = spawnProcess(process.execPath, [script, ...args], {
    cwd,
    stdio: "inherit",
    shell: false,
    detached: process.platform !== "win32",
  });
  let interrupted = false;
  let timedOut = false;
  const started = Date.now();
  const interrupt = () => {
    interrupted = true;
    stopProcessTree(child);
  };
  process.on("SIGINT", interrupt);
  process.on("SIGTERM", interrupt);
  const heartbeat = installing
    ? setInterval(() => {
        console.log(
          `[Frontend] npm đã chạy ${Math.round((Date.now() - started) / 1000)} giây / giới hạn ${Math.round(timeoutMs / 1000)} giây; xem dòng npm http để biết gói đang tải.`,
        );
      }, 15_000)
    : null;
  const timer = timeoutMs
    ? setTimeout(() => {
        // The exit notification may still be queued at the deadline. Never
        // terminate a process that Node already knows has finished.
        if (child.exitCode !== null || child.signalCode != null) return;
        timedOut = true;
        stopProcessTree(child);
      }, timeoutMs)
    : null;
  try {
    const code = await new Promise((resolveCode, reject) => {
      child.once("error", reject);
      // stdio is inherited, so no captured output needs draining. Waiting for
      // close can keep the deadline alive after npm has exited successfully.
      child.once("exit", (status) => resolveCode(status ?? 1));
    });
    if (interrupted) {
      const error = new Error("Đã dừng frontend theo yêu cầu.");
      error.exitCode = 130;
      throw error;
    }
    // On Windows taskkill is asynchronous: npm can finish normally between the
    // deadline firing and termination. Its real zero exit status wins that race;
    // prepareFrontend still checks the installed tree and native tools below.
    if (timedOut && code !== 0) {
      const error = new Error(
        `Cài/kiểm tra thư viện vượt giới hạn ${Math.round(timeoutMs / 1000)} giây. Đã dừng tiến trình con; không ghi nhận cài thành công. ${installing ? "Giữ nguyên node_modules và chạy lại cùng thư mục: bản cài hoàn chỉnh sẽ được kiểm tra ngoại tuyến để dùng lại. Nếu vẫn cần tải qua mạng chậm, có thể tăng giới hạn bằng --install-timeout=1200. Xem dòng npm http/ERR gần nhất." : "Kiểm tra cấu hình Vite và dependency; dùng --repair nếu bản cài bị hỏng."}`,
      );
      error.exitCode = 124;
      throw error;
    }
    if (code !== 0) {
      const error = new Error(
        `Tiến trình kết thúc với mã ${code}. Xem lỗi phía trên; không xóa node_modules hoặc tắt TLS để thử tăng tốc.`,
      );
      error.exitCode = code;
      throw error;
    }
  } finally {
    if (heartbeat) clearInterval(heartbeat);
    if (timer) clearTimeout(timer);
    process.removeListener("SIGINT", interrupt);
    process.removeListener("SIGTERM", interrupt);
  }
}
function processAlive(pid) {
  if (!Number.isInteger(pid) || pid < 1) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code !== "ESRCH";
  }
}
export function acquireInstallLock(root) {
  mkdirSync(resolve(root, ".cache"), { recursive: true });
  const path = resolve(root, ".cache/frontend-install.lock");
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      writeFileSync(
        path,
        JSON.stringify({
          pid: process.pid,
          startedAt: new Date().toISOString(),
        }),
        { flag: "wx" },
      );
      return () => {
        try {
          unlinkSync(path);
        } catch {
          /* Already removed. */
        }
      };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      let owner;
      try {
        owner = JSON.parse(readFileSync(path, "utf8"));
      } catch {
        /* A concurrent writer may still be writing. */
      }
      if (
        owner
          ? processAlive(owner.pid)
          : Date.now() - statSync(path).mtimeMs < 60_000
      )
        throw new Error(
          `Một cửa sổ frontend khác đang chuẩn bị thư viện${owner?.pid ? ` (PID ${owner.pid})` : ""}. Chờ hoặc dừng cửa sổ đó trước; không chạy hai npm ci đồng thời.`,
        );
      try {
        unlinkSync(path);
      } catch {
        /* Another launcher may have recovered it. */
      }
    }
  }
  throw new Error(
    "Không lấy được khóa cài thư viện. Thử lại sau khi cửa sổ khác đã dừng.",
  );
}
export async function prepareFrontend({
  root = repositoryRoot,
  repair = false,
  timeoutMs = DEFAULT_INSTALL_TIMEOUT,
  run = runCommand,
} = {}) {
  const frontend = resolve(root, "frontend");
  const release = acquireInstallLock(root);
  try {
    let state = inspectDependencies(frontend);
    if (state.ready && !repair) {
      if (state.needsProbe) {
        console.log(
          "[Frontend] Tìm thấy bản cài khớp lockfile. Kiểm tra để dùng lại, không tải lại npm.",
        );
        await run(resolve(scriptDirectory, "frontend-probe.mjs"), [], {
          cwd: frontend,
          timeoutMs: 30_000,
        });
      } else
        console.log(
          "[Frontend] Dependency không đổi, dùng lại node_modules; bỏ qua npm ci.",
        );
      stampDependencies(frontend, state.fingerprint);
      return;
    }
    console.log(
      `[Frontend] ${repair ? "Đã yêu cầu sửa bản cài bằng --repair." : state.reasons.join(" ")}`,
    );
    console.log(
      `[Frontend] Cài dependency bằng npm; hiện log HTTP, request tối đa ${Math.min(120, Math.floor(timeoutMs / 3000))} giây, retry 1 lần; toàn lượt tối đa ${Math.round(timeoutMs / 1000)} giây.`,
    );
    const args = installArguments(root, timeoutMs);
    console.log(
      args.includes("--cache")
        ? "[Frontend] Dùng lại npm cache của dự án."
        : "[Frontend] Dùng npm cache chung của máy hoặc cấu hình hiện có.",
    );
    await run(npmCli(), args, { cwd: frontend, installing: true, timeoutMs });
    state = inspectDependencies(frontend);
    // A changed prior stamp is expected after a deliberate successful install.
    if (!state.treeReady)
      throw new Error(
        `npm đã kết thúc nhưng bản cài chưa đủ: ${state.reasons.join(" ")}`,
      );
    await run(resolve(scriptDirectory, "frontend-probe.mjs"), [], {
      cwd: frontend,
      timeoutMs: 30_000,
    });
    stampDependencies(frontend, state.fingerprint);
  } finally {
    release();
  }
}
export async function main(argv = process.argv.slice(2)) {
  const started = Date.now();
  console.log(
    `[Frontend] Node.js ${process.versions.node}. Đang kiểm tra dependency...`,
  );
  const [major, minor] = process.versions.node.split(".").map(Number);
  if (major < 22 || (major === 22 && minor < 12))
    throw new Error("Cần Node.js 22.12 trở lên (khuyến nghị Node 24 LTS).");
  const timeoutArg = argv.find((arg) => arg.startsWith("--install-timeout="));
  const seconds = timeoutArg
    ? Number(timeoutArg.split("=")[1])
    : DEFAULT_INSTALL_TIMEOUT / 1000;
  if (!Number.isFinite(seconds) || seconds < 30 || seconds > 1800)
    throw new Error("--install-timeout cần từ 30 đến 1800 giây.");
  if (
    argv.some(
      (arg) =>
        !["--run", "--repair"].includes(arg) &&
        !arg.startsWith("--install-timeout="),
    )
  )
    throw new Error("Tùy chọn hợp lệ: --run, --repair, --install-timeout=600.");
  await prepareFrontend({
    repair: argv.includes("--repair"),
    timeoutMs: seconds * 1000,
  });
  console.log(
    `[Frontend] Chuẩn bị xong sau ${((Date.now() - started) / 1000).toFixed(1)} giây.`,
  );
  if (argv.includes("--run")) {
    console.log(
      "[Frontend] Đang mở Vite tại http://127.0.0.1:5173 — giữ cửa sổ này mở khi sử dụng.",
    );
    await runCommand(
      resolve(repositoryRoot, "frontend/node_modules/vite/bin/vite.js"),
      ["--host", "127.0.0.1", "--port", "5173", "--strictPort"],
      { cwd: resolve(repositoryRoot, "frontend") },
    );
  } else console.log("[Frontend] Có thể chạy run-frontend.bat để mở ứng dụng.");
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().catch((error) => {
    console.error(`[Frontend] ${error.message}`);
    process.exitCode = error.exitCode || 1;
  });
}
