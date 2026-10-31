import { test, expect } from "@playwright/test";
import type { ChatGPTStatus } from "../src/types/ai";
const base: ChatGPTStatus = {
  provider: "chatgpt",
  status: "not_connected",
  secure_storage_available: true,
  authorization_status: "idle",
  pending_authorization: false,
  account: null,
  connection_id: null,
  granted_scopes: [],
  plan_usage_authorized: false,
  access_expires_at: null,
  refresh_expires_at: null,
  models: [],
  selected_model: null,
  models_stale: true,
  last_error: null,
  eligibility: {
    status: "pending_live_verification",
    repository_license_found: false,
    user_review_required: true,
    note: "Eligibility và license cần người sở hữu rà soát.",
  },
  live_verification: "pending_live_verification",
  quota: {
    status: "unknown",
    remaining: null,
    note: "Chưa xác định hạn mức còn lại.",
  },
  documentation: ["https://developers.openai.com/siwc/quickstart"],
  full_preview_limitations_verified: false,
  fallback_to_api_key: false,
};

test("manual refresh explicitly reports no connection result instead of silently doing nothing", async ({ page }) => {
  let reads = 0;
  await page.route("**/api/ai/chatgpt/status", route => {
    reads++;
    return route.fulfill({ json: base });
  });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", { name: "ChatGPT Connection", exact: true });
  await panel.getByRole("button", { name: "Làm mới trạng thái ChatGPT", exact: true }).click();
  await expect(panel.getByRole("status")).toContainText("chưa có kết nối hoặc kết quả đăng nhập");
  await expect(panel.getByRole("status")).toContainText("không tải lại callback cũ");
  expect(reads).toBeGreaterThan(1);
});

test("callback failure shows the error code and stage and can start a fresh attempt", async ({ page }) => {
  let state: ChatGPTStatus = { ...base, authorization_status: "failed", last_error: {
    code: "secure_storage_unavailable",
    detail: "Không thể ghi token vào kho khóa hệ điều hành.",
    stage: "credential_storage",
  } };
  await page.addInitScript(() => { window.open = () => null; });
  await page.route("**/api/ai/chatgpt/status", route => route.fulfill({ json: state }));
  await page.route("**/api/ai/chatgpt/connect", route => {
    state = { ...base, authorization_status: "waiting", pending_authorization: true };
    return route.fulfill({ json: { authorization_url: "https://auth.openai.com/api/accounts/authorize?state=fresh-test" } });
  });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", { name: "ChatGPT Connection", exact: true });
  await expect(panel.getByRole("alert")).toContainText("secure_storage_unavailable");
  await expect(panel.getByRole("alert")).toContainText("Lưu vào OS Credential Vault");
  await panel.getByRole("button", { name: "Làm mới trạng thái ChatGPT", exact: true }).click();
  await expect(panel.getByRole("status")).toContainText("Xem mã lỗi và bước xử lý");
  await panel.getByLabel("Xác nhận đã rà soát eligibility ChatGPT").check();
  await panel.getByLabel("Trình duyệt cùng máy LocalSEO").check();
  await panel.getByRole("button", { name: "Continue with ChatGPT", exact: true }).click();
  await expect(panel.getByRole("alert")).toHaveCount(0);
  await expect(panel.getByRole("link", { name: /Tiếp tục đến trang đăng nhập ChatGPT/ })).toHaveAttribute("href", /state=fresh-test/);
  await expect(panel).toContainText("Pending Live Verification");
});

test("Continue with ChatGPT requires explicit eligibility and local-browser review, opens only OAuth URL (mocked)", async ({
  page,
}) => {
  let state = { ...base };
  let body: unknown;
  await page.addInitScript(() => {
    window.open = () => null;
  });
  await page.route("**/api/ai/chatgpt/status", (route) =>
    route.fulfill({ json: state }),
  );
  await page.route("**/api/ai/chatgpt/connect", (route) => {
    body = route.request().postDataJSON();
    state = {
      ...state,
      authorization_status: "waiting",
      pending_authorization: true,
    };
    return route.fulfill({
      json: {
        authorization_url:
          "https://auth.openai.com/api/accounts/authorize?client_id=dynamic_agent_client&state=mock-state",
        expires_in: 600,
      },
    });
  });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", {
    name: "ChatGPT Connection",
    exact: true,
  });
  await expect(panel).toContainText("Pending Live Verification");
  const button = panel.getByRole("button", {
    name: "Continue with ChatGPT",
    exact: true,
  });
  await expect(button).toBeDisabled();
  await panel.getByLabel("Xác nhận đã rà soát eligibility ChatGPT").check();
  await expect(button).toBeDisabled();
  await panel.getByLabel("Trình duyệt cùng máy LocalSEO").check();
  await button.click();
  await expect(
    panel.getByRole("link", { name: /Tiếp tục đến trang đăng nhập ChatGPT/ }),
  ).toHaveAttribute(
    "href",
    /^https:\/\/auth.openai.com\/api\/accounts\/authorize/,
  );
  expect(body).toEqual({
    eligibility_acknowledged: true,
    localhost_acknowledged: true,
  });
  await expect(page.getByLabel("Model AI", { exact: true })).toBeAttached();
});

test("authenticated account without direct permission cannot choose model or send inference (mocked)", async ({
  page,
}) => {
  const state = {
    ...base,
    status: "connected_not_authorized",
    account: { sub: "fixture", name: "Tài khoản mô phỏng" },
    connection_id: "test-session",
    granted_scopes: ["openid"],
  };
  await page.route("**/api/ai/chatgpt/status", (route) =>
    route.fulfill({ json: state }),
  );
  await page.route("**/api/ai/conversations/*/estimate?*", (route) =>
    route.fulfill({
      status: 403,
      json: {
        code: "chatgpt_plan_not_authorized",
        detail: "Connected — ChatGPT Plan Usage Not Authorized.",
      },
    }),
  );
  const paid: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/messages?") && r.method() === "POST")
      paid.push(r.url());
  });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", { name: "ChatGPT Connection" });
  await expect(panel).toContainText(
    "Connected — ChatGPT Plan Usage Not Authorized",
  );
  await expect(panel.getByLabel("Model ChatGPT của tài khoản")).toBeDisabled();
  await page.goto("/ai-workspace?project=xuong-may");
  await page.getByLabel("Chế độ phân tích AI").selectOption("chatgpt");
  await page.getByLabel("Câu hỏi SEO").fill("Phân tích bằng ChatGPT.");
  await page
    .getByRole("button", {
      name: "Kiểm tra quyền và model ChatGPT cho lượt này",
    })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Plan Usage Not Authorized",
  );
  await expect(
    page.getByRole("button", { name: "Gửi phân tích", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Chế độ phân tích AI")).toHaveValue("chatgpt");
  expect(paid).toEqual([]);
});

test("model picker, consent and quota failure never silently select API key provider (mocked)", async ({
  page,
}) => {
  let state: ChatGPTStatus = {
    ...base,
    status: "connected_authorized",
    account: { sub: "fixture", name: "Tài khoản mô phỏng" },
    connection_id: "test-session",
    plan_usage_authorized: true,
    granted_scopes: ["chatgpt.tokens.use.direct"],
    models: [
      { slug: "model-a", display_name: "Model A" },
      { slug: "model-b", display_name: "Model B" },
    ],
    selected_model: "model-a",
    models_stale: false,
  };
  let selected: unknown;
  let sent: Record<string, unknown> | undefined;
  await page.route("**/api/ai/chatgpt/status", (route) =>
    route.fulfill({ json: state }),
  );
  await page.route("**/api/ai/chatgpt/model", (route) => {
    selected = route.request().postDataJSON();
    state = { ...state, selected_model: "model-b" };
    return route.fulfill({ json: state });
  });
  await page.route("**/api/ai/conversations/*/estimate?*", (route) =>
    route.fulfill({
      json: {
        provider: "chatgpt",
        model: "model-b",
        connection_id: "test-session",
        max_calls: 8,
        requires_external_consent: true,
        billing_source: "chatgpt_plan",
        quota_remaining: null,
        estimated_cost_usd: null,
        fallback_to_api_key: false,
      },
    }),
  );
  await page.route("**/api/ai/conversations/*/messages?*", (route) => {
    sent = route.request().postDataJSON();
    return route.fulfill({
      status: 429,
      json: {
        code: "chatgpt_quota",
        detail: "ChatGPT đã đạt hạn mức. Không chuyển API trả phí.",
      },
    });
  });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", { name: "ChatGPT Connection" });
  await panel.getByLabel("Model ChatGPT của tài khoản").selectOption("model-b");
  await panel
    .getByRole("button", { name: "Lưu model ChatGPT", exact: true })
    .click();
  await expect(panel).toContainText("Đã chọn model ChatGPT");
  expect(selected).toEqual({ slug: "model-b" });
  await page.goto("/ai-workspace?project=xuong-may");
  await page.getByLabel("Chế độ phân tích AI").selectOption("chatgpt");
  await page.getByLabel("Câu hỏi SEO").fill("Phân tích bằng model đã chọn.");
  await expect(
    page.getByRole("button", { name: "Gửi phân tích", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", {
      name: "Kiểm tra quyền và model ChatGPT cho lượt này",
    })
    .click();
  await page.getByLabel("Xác nhận gửi ChatGPT Plan Usage").check();
  await page
    .getByRole("button", { name: "Gửi phân tích", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Không chuyển API trả phí",
  );
  expect(sent).toMatchObject({
    provider: "chatgpt",
    approved_model: "model-b",
    approved_connection_id: "test-session",
    acknowledge_external_processing: true,
  });
  await expect(page.getByLabel("Chế độ phân tích AI")).toHaveValue("chatgpt");
});

test("ChatGPT settings remain usable on mobile without OS vault", async ({
  page,
}) => {
  await page.route("**/api/ai/chatgpt/status", (route) =>
    route.fulfill({ json: { ...base, secure_storage_available: false } }),
  );
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.goto("/ai-workspace?project=xuong-may&tab=settings");
  const panel = page.getByRole("region", { name: "ChatGPT Connection" });
  await expect(panel).toContainText("Chưa mở được OS Credential Vault");
  await expect(
    panel.getByRole("button", { name: "Continue with ChatGPT", exact: true }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
});

for (const failure of [
  {
    reason: "audience_mismatch",
    detail: "Audience của ID token không khớp issued client ID của lượt đăng nhập.",
  },
  {
    reason: "nonce_missing",
    detail: "ID token không chứa nonce đã yêu cầu trong lượt OAuth.",
  },
  {
    reason: "issued_in_future",
    detail: "Thời điểm phát hành ID token vượt quá 60 giây so với đồng hồ backend. Trên Windows nhấn Sync now, rồi đăng nhập lại.",
  },
]) {
  test(`ID token failure shows safe specific reason ${failure.reason} after refresh (mocked)`, async ({ page }) => {
    let state: ChatGPTStatus = { ...base };
    await page.route("**/api/ai/chatgpt/status", (route) =>
      route.fulfill({ json: state }),
    );
    const commands: string[] = [];
    page.on("request", (request) => {
      if (request.method() !== "GET" && request.url().includes("/api/ai/"))
        commands.push(request.url());
    });
    await page.goto("/ai-workspace?project=xuong-may&tab=settings");
    const panel = page.getByRole("region", { name: "ChatGPT Connection", exact: true });
    await expect(panel).toContainText("Chưa kết nối");
    state = {
      ...base,
      authorization_status: "failed",
      last_error: {
        code: "chatgpt_invalid_id_token",
        stage: "id_token_validation",
        reason: failure.reason,
        detail: failure.detail,
      },
    };
    await panel.getByRole("button", { name: "Làm mới trạng thái ChatGPT", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText(failure.reason);
    await expect(panel.getByRole("alert")).toContainText(failure.detail);
    await expect(panel.getByRole("alert")).toContainText("Xác minh ID token");
    await expect(panel).toContainText("Pending Live Verification");
    await expect(panel.getByLabel("Model ChatGPT của tài khoản")).toBeDisabled();
    expect(commands).toEqual([]);
  });
}
