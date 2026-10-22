// Verify native tools when adopting an existing installation, after npm, or after
// a Node/architecture change. This never downloads packages or approves scripts.
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const cwd = process.cwd();
const require = createRequire(resolve(cwd, "package.json"));
try {
  require("esbuild").transformSync("const rank: number = 1", { loader: "ts" });
  const { parseAst } = await import(
    pathToFileURL(require.resolve("rollup/parseAst")).href
  );
  parseAst("export default 1");
  const vite = await import(pathToFileURL(require.resolve("vite")).href);
  const config = await vite.loadConfigFromFile(
    { command: "serve", mode: "development" },
    resolve(cwd, "vite.config.ts"),
    cwd,
    "silent",
  );
  if (!config) throw new Error("Không đọc được cấu hình Vite.");
  console.log(
    "[Frontend] Vite, esbuild và plugin đã vượt qua kiểm tra ngoại tuyến.",
  );
} catch (error) {
  console.error(`[Frontend] Kiểm tra thư viện chưa đạt: ${error.message}`);
  console.error(
    "[Frontend] Không tự cấp quyền chạy install script. Nếu npm báo chặn script, kiểm tra chính sách npm và log của gói tương ứng.",
  );
  process.exitCode = 1;
}
