import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { EventEmitter } from "node:events";
import {
  dependencyFingerprint,
  inspectDependencies,
  stampDependencies,
} from "../frontend-dependencies.mjs";
import {
  DEFAULT_INSTALL_TIMEOUT,
  acquireInstallLock,
  installArguments,
  prepareFrontend,
  runCommand,
  stopProcessTree,
} from "../frontend.mjs";

function json(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(data));
}
function fixture(t) {
  const root = mkdtempSync(resolve(tmpdir(), "SEO frontend with spaces "));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const frontend = resolve(root, "frontend");
  const manifest = {
    name: "seo-test",
    version: "0.4.0",
    dependencies: { react: "^19.0.0" },
    devDependencies: { vite: "^7.0.0" },
    scripts: { build: "vite build" },
  };
  const packages = {
    "": { ...manifest, scripts: undefined },
    "node_modules/react": {
      version: "19.1.1",
      resolved: "https://registry.npmjs.org/react/-/react-19.1.1.tgz",
      integrity: "sha512-test",
    },
    "node_modules/vite": {
      version: "7.3.7",
      resolved: "https://registry.npmjs.org/vite/-/vite-7.3.7.tgz",
      integrity: "sha512-vite",
      dev: true,
    },
    "node_modules/@esbuild/win32-x64": {
      version: "0.28.2",
      optional: true,
      os: ["win32"],
      cpu: ["x64"],
    },
  };
  const lock = {
    name: manifest.name,
    version: manifest.version,
    lockfileVersion: 3,
    packages,
  };
  json(resolve(frontend, "package.json"), manifest);
  json(resolve(frontend, "package-lock.json"), lock);
  function install() {
    const hidden = {
      lockfileVersion: 3,
      packages: Object.fromEntries(
        Object.entries(packages).filter(
          ([path]) => path && !packages[path].optional,
        ),
      ),
    };
    json(resolve(frontend, "node_modules/.package-lock.json"), hidden);
    for (const [path, entry] of Object.entries(hidden.packages))
      json(resolve(frontend, path, "package.json"), {
        name: path,
        version: entry.version,
      });
    mkdirSync(resolve(frontend, "node_modules/vite/bin"), { recursive: true });
    writeFileSync(resolve(frontend, "node_modules/vite/bin/vite.js"), "");
  }
  install();
  return { root, frontend, manifest, lock, install };
}

test("releases and JSON formatting reuse existing dependencies without npm", async (t) => {
  const f = fixture(t);
  const calls = [];
  await prepareFrontend({
    root: f.root,
    run: async (script) => calls.push(script),
  });
  assert.equal(calls.length, 1);
  assert.match(calls[0], /frontend-probe.mjs$/);
  const fingerprint = inspectDependencies(f.frontend).fingerprint;
  f.manifest.version = "0.5.0";
  f.lock.version = "0.5.0";
  f.lock.packages[""].version = "0.5.0";
  json(resolve(f.frontend, "package.json"), f.manifest);
  writeFileSync(
    resolve(f.frontend, "package-lock.json"),
    JSON.stringify(f.lock, null, 4) + "\r\n",
  );
  assert.equal(inspectDependencies(f.frontend).fingerprint, fingerprint);
  await prepareFrontend({
    root: f.root,
    run: async () =>
      assert.fail("A release number must not invoke npm or the probe twice"),
  });
  assert.ok(
    existsSync(resolve(f.frontend, "node_modules/.workspace-lock.sha256")),
  );
});

test("direct npm installation without custom stamps is adopted offline after probing", async (t) => {
  const f = fixture(t);
  const scripts = [];
  assert.equal(inspectDependencies(f.frontend).ready, true);
  await prepareFrontend({
    root: f.root,
    run: async (script) => scripts.push(script),
  });
  assert.equal(scripts.length, 1);
  assert.match(scripts[0], /probe/);
  assert.equal(inspectDependencies(f.frontend).needsProbe, false);
});

test("required missing nested package and modified manifest cannot be treated as installed", (t) => {
  const f = fixture(t);
  f.lock.packages["node_modules/nested"] = { version: "1.0.0" };
  json(resolve(f.frontend, "package-lock.json"), f.lock);
  assert.equal(inspectDependencies(f.frontend).ready, false);
  f.manifest.dependencies.other = "^2.0.0";
  json(resolve(f.frontend, "package.json"), f.manifest);
  assert.throws(() => inspectDependencies(f.frontend), /chưa đồng bộ/);
});

test("hidden lock alone is insufficient when files were removed or altered", (t) => {
  const f = fixture(t);
  stampDependencies(f.frontend, inspectDependencies(f.frontend).fingerprint);
  rmSync(resolve(f.frontend, "node_modules/react/package.json"));
  assert.equal(inspectDependencies(f.frontend).ready, false);
  json(resolve(f.frontend, "node_modules/react/package.json"), {
    version: "18.0.0",
  });
  assert.equal(inspectDependencies(f.frontend).ready, false);
});

test("actual lock dependency changes install once; installed tree and native probe must pass", async (t) => {
  const f = fixture(t);
  stampDependencies(f.frontend, inspectDependencies(f.frontend).fingerprint);
  f.lock.packages["node_modules/react"].version = "19.2.0";
  json(resolve(f.frontend, "package-lock.json"), f.lock);
  const calls = [];
  await prepareFrontend({
    root: f.root,
    run: async (script, args) => {
      calls.push({ script, args });
      if (args[0] === "ci") f.install();
    },
  });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].args[0], "ci");
  assert.match(calls[1].script, /probe/);
  assert.equal(inspectDependencies(f.frontend).ready, true);
  await prepareFrontend({
    root: f.root,
    run: async () => assert.fail("Do not reinstall twice"),
  });
});

test("failed install and failed native probe never record success, and release the install lock", async (t) => {
  const f = fixture(t);
  rmSync(resolve(f.frontend, "node_modules"), { recursive: true });
  await assert.rejects(
    prepareFrontend({
      root: f.root,
      run: async () => {
        throw new Error("registry timeout");
      },
    }),
    /registry timeout/,
  );
  assert.equal(
    existsSync(
      resolve(f.frontend, "node_modules/.workspace-dependencies.json"),
    ),
    false,
  );
  assert.equal(
    existsSync(resolve(f.root, ".cache/frontend-install.lock")),
    false,
  );
  f.install();
  await assert.rejects(
    prepareFrontend({
      root: f.root,
      run: async () => {
        throw new Error("native binary missing");
      },
    }),
    /native binary missing/,
  );
  assert.equal(
    existsSync(
      resolve(f.frontend, "node_modules/.workspace-dependencies.json"),
    ),
    false,
  );
});

test("repair is explicit, still verifies npm output and respects native script policy", async (t) => {
  const f = fixture(t);
  stampDependencies(f.frontend, inspectDependencies(f.frontend).fingerprint);
  const calls = [];
  await prepareFrontend({
    root: f.root,
    repair: true,
    run: async (_, args) => calls.push(args),
  });
  assert.equal(calls[0][0], "ci");
  assert.ok(calls[0].includes("--foreground-scripts"));
  assert.equal(
    calls[0].some((arg) =>
      /ignore-scripts|allow-scripts|approve|strict-ssl=false/.test(arg),
    ),
    false,
  );
});

test("lifecycle and override changes invalidate the dependency fingerprint", (t) => {
  const f = fixture(t);
  const before = dependencyFingerprint(f.manifest, f.lock);
  f.manifest.scripts.postinstall = "node install.mjs";
  assert.notEqual(dependencyFingerprint(f.manifest, f.lock), before);
  delete f.manifest.scripts.postinstall;
  f.manifest.overrides = { react: "19.0.0" };
  assert.notEqual(dependencyFingerprint(f.manifest, f.lock), before);
});

test("Node ABI changes require an offline probe instead of forcing downloads", async (t) => {
  const f = fixture(t);
  const fingerprint = inspectDependencies(f.frontend).fingerprint;
  json(resolve(f.frontend, "node_modules/.workspace-dependencies.json"), {
    fingerprint,
    platform: process.platform,
    arch: process.arch,
    nodeAbi: "old",
  });
  let calls = 0;
  await prepareFrontend({
    root: f.root,
    run: async (_, args) => {
      assert.deepEqual(args, []);
      calls++;
    },
  });
  assert.equal(calls, 1);
});

test("concurrent installers are blocked and abandoned locks can be recovered", (t) => {
  const f = fixture(t);
  const release = acquireInstallLock(f.root);
  assert.throws(() => acquireInstallLock(f.root), /cửa sổ frontend khác/);
  release();
  json(resolve(f.root, ".cache/frontend-install.lock"), { pid: 2147483647 });
  const recovered = acquireInstallLock(f.root);
  recovered();
  assert.equal(
    existsSync(resolve(f.root, ".cache/frontend-install.lock")),
    false,
  );
});

test("npm uses bounded requests/retry, shows downloads and reuses configured or warm cache", (t) => {
  const f = fixture(t);
  const args = installArguments(f.root);
  assert.equal(DEFAULT_INSTALL_TIMEOUT, 600_000);
  assert.ok(args.includes("--fetch-timeout=120000"));
  assert.ok(installArguments(f.root, 180_000).includes("--fetch-timeout=60000"));
  assert.ok(args.includes("--fetch-retries=1"));
  assert.ok(args.includes("--loglevel=http"));
  assert.equal(args.includes("--cache"), false); // Use shared OS/user cache for a new checkout.
  mkdirSync(resolve(f.root, ".cache/npm/_cacache"), { recursive: true });
  if (!process.env.npm_config_cache && !process.env.NPM_CONFIG_CACHE)
    assert.equal(
      installArguments(f.root).at(-1),
      resolve(f.root, ".cache/npm"),
    );
});

test("cold install receives ten minutes; a validated install is then reused without npm", async (t) => {
  const f = fixture(t);
  rmSync(resolve(f.frontend, "node_modules"), { recursive: true });
  const calls = [];
  await prepareFrontend({
    root: f.root,
    run: async (_, args, options) => {
      calls.push({ args, options });
      if (args[0] === "ci") f.install();
    },
  });
  assert.equal(calls[0].options.timeoutMs, 600_000);
  assert.equal(calls[0].options.installing, true);
  assert.equal(calls[1].options.timeoutMs, 30_000);
  assert.equal(inspectDependencies(f.frontend).needsProbe, false);
  await prepareFrontend({
    root: f.root,
    run: async () => assert.fail("A completed install must not download again"),
  });
});

test("successful exit is accepted without waiting for delayed stdio close", async () => {
  const child = new EventEmitter();
  child.exitCode = null;
  const running = runCommand("npm-cli.js", ["ci"], {
    timeoutMs: 20,
    spawnProcess: () => {
      queueMicrotask(() => {
        child.exitCode = 0;
        child.emit("exit", 0);
        // No close event: inherited handles can outlive the npm process.
      });
      return child;
    },
  });
  await running;
});

test("a queued successful exit at the deadline is not treated as a timeout", async () => {
  const child = new EventEmitter();
  child.exitCode = null;
  await runCommand("npm-cli.js", ["ci"], {
    timeoutMs: 10,
    spawnProcess: () => {
      queueMicrotask(() => { child.exitCode = 0; });
      setTimeout(() => {
        child.emit("exit", 0);
        child.emit("close", 0);
      }, 30);
      return child;
    },
  });
});

test("normal zero exit wins a race with asynchronous timeout termination", async () => {
  const child = new EventEmitter();
  child.exitCode = null;
  await runCommand("npm-cli.js", ["ci"], {
    timeoutMs: 10,
    spawnProcess: () => {
      // No PID: simulate a pending asynchronous terminator without killing an
      // actual process. npm reports success just after the deadline fired.
      setTimeout(() => {
        child.exitCode = 0;
        child.emit("exit", 0);
        child.emit("close", 0);
      }, 30);
      return child;
    },
  });
});

test("a nonzero npm exit is preserved when close is delayed", async () => {
  const child = new EventEmitter();
  child.exitCode = null;
  await assert.rejects(runCommand("npm-cli.js", ["ci"], {
    timeoutMs: 1000,
    spawnProcess: () => {
      queueMicrotask(() => {
        child.exitCode = 7;
        child.emit("exit", 7);
      });
      return child;
    },
  }), (error) => error.exitCode === 7);
});

test("runner supports executable paths with spaces without using a shell", async (t) => {
  const f = fixture(t);
  const script = resolve(f.root, "a script with spaces.mjs");
  writeFileSync(
    script,
    `import fs from 'node:fs';fs.writeFileSync(process.argv[2],process.argv[3]);`,
  );
  const output = resolve(f.root, "result.txt");
  await runCommand(script, [output, "literal $HOME & symbols"], {
    cwd: f.root,
    timeoutMs: 5000,
  });
  assert.equal(readFileSync(output, "utf8"), "literal $HOME & symbols");
});

test("timeout terminates the actual process and returns a diagnostic instead of hanging", async (t) => {
  const f = fixture(t);
  const script = resolve(f.root, "stall.mjs");
  const pidfile = resolve(f.root, "pid");
  writeFileSync(
    script,
    `import fs from 'node:fs';fs.writeFileSync(process.argv[2],String(process.pid));setInterval(()=>{},1000);`,
  );
  await assert.rejects(
    runCommand(script, [pidfile], { cwd: f.root, timeoutMs: 1000 }),
    (error) => error.exitCode === 124 && /vượt giới hạn/.test(error.message),
  );
  const pid = Number(readFileSync(pidfile, "utf8"));
  assert.throws(() => process.kill(pid, 0), { code: "ESRCH" });
});

test("Windows termination targets only the spawned PID and its descendants with shell disabled", () => {
  const child = { pid: 23456, exitCode: null };
  const calls = [];
  stopProcessTree(child, "win32", (...args) => {
    calls.push(args);
    return new EventEmitter();
  });
  assert.match(calls[0][0], /System32.*taskkill.exe$/);
  assert.deepEqual(calls[0][1], ["/PID", "23456", "/T", "/F"]);
  assert.equal(calls[0][2].shell, false);
});

test(
  "Ctrl+C stops the owned process group and returns 130 (POSIX)",
  { skip: process.platform === "win32" },
  async (t) => {
    const f = fixture(t);
    const pidfile = resolve(f.root, "child-pid");
    const childScript = resolve(f.root, "child.mjs");
    writeFileSync(
      childScript,
      `import fs from 'node:fs';fs.writeFileSync(process.argv[2],String(process.pid));setInterval(()=>{},1000);`,
    );
    const wrapper = resolve(f.root, "wrapper.mjs");
    const runner = new URL("../frontend.mjs", import.meta.url).href;
    writeFileSync(
      wrapper,
      `import {runCommand} from ${JSON.stringify(runner)};try{await runCommand(process.argv[2],[process.argv[3]],{cwd:process.cwd()});}catch(e){process.exitCode=e.exitCode||1;}`,
    );
    const parent = spawn(process.execPath, [wrapper, childScript, pidfile], {
      cwd: f.root,
      stdio: "ignore",
    });
    t.after(() => {
      if (parent.exitCode === null) parent.kill("SIGKILL");
    });
    const deadline = Date.now() + 5000;
    while (!existsSync(pidfile) && Date.now() < deadline)
      await new Promise((resolve) => setTimeout(resolve, 20));
    assert.ok(
      existsSync(pidfile),
      "child must actually start before interruption",
    );
    const closed = new Promise((resolve) => parent.once("close", resolve));
    parent.kill("SIGINT");
    assert.equal(await closed, 130);
    assert.throws(
      () => process.kill(Number(readFileSync(pidfile, "utf8")), 0),
      { code: "ESRCH" },
    );
  },
);

test("a successful npm exit without the required tree is still a failure", async (t) => {
  const f = fixture(t);
  rmSync(resolve(f.frontend, "node_modules"), { recursive: true });
  await assert.rejects(
    prepareFrontend({ root: f.root, run: async () => {} }),
    /bản cài chưa đủ/,
  );
  assert.equal(
    existsSync(
      resolve(f.frontend, "node_modules/.workspace-dependencies.json"),
    ),
    false,
  );
  assert.equal(
    existsSync(resolve(f.root, ".cache/frontend-install.lock")),
    false,
  );
});

test("npm hidden-lock metadata differences do not force a reinstall when integrity and versions match", (t) => {
  const f = fixture(t);
  const path = resolve(f.frontend, "node_modules/.package-lock.json");
  const hidden = JSON.parse(readFileSync(path, "utf8"));
  for (const record of Object.values(hidden.packages)) {
    delete record.resolved;
    record.link = false;
  }
  json(path, hidden);
  assert.equal(inspectDependencies(f.frontend).ready, true);
  hidden.packages["node_modules/react"].integrity = "sha512-different";
  json(path, hidden);
  assert.equal(inspectDependencies(f.frontend).ready, false);
});
