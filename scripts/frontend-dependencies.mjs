import { createHash } from "node:crypto";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    );
  return value;
}
export function dependencyFingerprint(manifest, lock) {
  const root = { ...lock.packages[""] };
  // App releases and JSON formatting do not change installed dependencies.
  delete root.name;
  delete root.version;
  const lifecycle = Object.fromEntries(
    ["preinstall", "install", "postinstall", "prepare"]
      .filter((key) => manifest.scripts?.[key])
      .map((key) => [key, manifest.scripts[key]]),
  );
  const input = {
    lockfileVersion: lock.lockfileVersion,
    packages: { ...lock.packages, "": root },
    dependencies: manifest.dependencies,
    devDependencies: manifest.devDependencies,
    optionalDependencies: manifest.optionalDependencies,
    overrides: manifest.overrides,
    lifecycle,
  };
  return createHash("sha256")
    .update(JSON.stringify(canonical(input)))
    .digest("hex");
}
function samePackage(expected, installed) {
  if (
    expected.version !== installed.version ||
    Boolean(expected.link) !== Boolean(installed.link)
  )
    return false;
  if (expected.integrity) return expected.integrity === installed.integrity;
  return expected.resolved === installed.resolved;
}

export function inspectDependencies(frontend) {
  const manifest = readJson(resolve(frontend, "package.json"));
  const lock = readJson(resolve(frontend, "package-lock.json"));
  if (!manifest || !lock?.packages?.[""] || lock.lockfileVersion < 2)
    throw new Error(
      "package.json hoặc package-lock.json không hợp lệ. Khôi phục tệp từ Git rồi thử lại.",
    );
  for (const key of [
    "dependencies",
    "devDependencies",
    "optionalDependencies",
  ]) {
    if (
      JSON.stringify(canonical(manifest[key] || {})) !==
      JSON.stringify(canonical(lock.packages[""][key] || {}))
    )
      throw new Error(
        "package.json và package-lock.json chưa đồng bộ dependency. Khôi phục đúng cặp tệp từ Git; không xóa node_modules.",
      );
  }
  const fingerprint = dependencyFingerprint(manifest, lock);
  const stamp = readJson(
    resolve(frontend, "node_modules/.workspace-dependencies.json"),
  );
  const hidden = readJson(resolve(frontend, "node_modules/.package-lock.json"));
  const reasons = [];
  if (!hidden?.packages)
    reasons.push("Chưa có bản cài npm hoàn tất để đối chiếu.");
  else {
    // npm's hidden lock contains the actual platform-specific tree. Optional packages
    // for other OS/CPU architectures are deliberately absent, especially on Windows.
    for (const [path, installed] of Object.entries(hidden.packages)) {
      if (
        !path.startsWith("node_modules/") ||
        path.includes("\\") ||
        path.includes(":") ||
        path.split("/").includes("..")
      ) {
        reasons.push("Bản ghi node_modules không hợp lệ.");
        break;
      }
      const expected = lock.packages[path];
      if (!expected || !samePackage(expected, installed)) {
        reasons.push(`Dependency đã đổi: ${path}.`);
        break;
      }
      const actual = readJson(resolve(frontend, path, "package.json"));
      if (!actual || actual.version !== expected.version) {
        reasons.push(`Thiếu hoặc sai phiên bản: ${path}.`);
        break;
      }
    }
    if (!reasons.length) {
      for (const [path, expected] of Object.entries(lock.packages)) {
        if (path && !expected.optional && !hidden.packages[path]) {
          reasons.push(`Thiếu dependency bắt buộc: ${path}.`);
          break;
        }
      }
    }
    if (!reasons.length) {
      for (const name of Object.keys({
        ...manifest.dependencies,
        ...manifest.devDependencies,
      })) {
        if (!hidden.packages[`node_modules/${name}`]) {
          reasons.push(`Thiếu dependency trực tiếp: ${name}.`);
          break;
        }
      }
    }
  }
  if (!existsSync(resolve(frontend, "node_modules/vite/bin/vite.js")))
    reasons.push("Chưa có Vite.");
  // A previous stamp also freezes install lifecycle/overrides, which are not fully
  // represented in npm's hidden lock. Never adopt a different dependency signature.
  const treeReady = reasons.length === 0;
  if (stamp && stamp.fingerprint !== fingerprint)
    reasons.push("Cấu hình dependency hoặc install script đã đổi.");
  const sameRuntime =
    stamp?.platform === process.platform &&
    stamp?.arch === process.arch &&
    stamp?.nodeAbi === process.versions.modules;
  return {
    treeReady,
    ready: reasons.length === 0,
    needsProbe: !stamp || !sameRuntime,
    fingerprint,
    reasons,
  };
}
export function stampDependencies(frontend, fingerprint) {
  const path = resolve(frontend, "node_modules/.workspace-dependencies.json");
  const temporary = `${path}.${process.pid}.tmp`;
  const content =
    JSON.stringify({
      schema: 1,
      fingerprint,
      platform: process.platform,
      arch: process.arch,
      nodeAbi: process.versions.modules,
    }) + "\n";
  if (!existsSync(path) || readFileSync(path, "utf8") !== content) {
    writeFileSync(temporary, content);
    renameSync(temporary, path);
  }
  // Retain compatibility with older launchers after checking the installed tree.
  const digest = createHash("sha256")
    .update(readFileSync(resolve(frontend, "package-lock.json")))
    .digest("hex");
  const legacy = resolve(frontend, "node_modules/.workspace-lock.sha256");
  if (!existsSync(legacy) || readFileSync(legacy, "utf8") !== digest)
    writeFileSync(legacy, digest);
}
