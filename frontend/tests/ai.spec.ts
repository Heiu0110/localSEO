import { expect, test } from "@playwright/test";
import type { AIConversation } from "../src/types/ai";

test.describe("AI Workspace local evidence workflow", () => {
  test.describe.configure({ mode: "serial" });
  let conversation = "";
  let firstMessage = "";
  test("create scoped conversation and inspect truthful source context without calling AI", async ({
    page,
  }) => {
    const calls: string[] = [];
    page.on("request", (r) => {
      if (r.method() === "POST") calls.push(new URL(r.url()).pathname);
    });
    await page.goto("/ai-workspace?project=xuong-may");
    await expect(
      page.getByRole("heading", { level: 1, name: /AI Workspace/ }),
    ).toBeVisible();
    await expect(page.getByLabel("Website AI Workspace")).toHaveValue(
      "xuong-may",
    );
    await page
      .getByRole("button", { name: "Ngữ cảnh & nguồn", exact: true })
      .click();
    const panel = page.getByRole("dialog");
    await expect(panel).toContainText("Topical Map");
    await expect(panel).toContainText("Chưa triển khai");
    await page.keyboard.press("Escape");
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/ai/conversations") &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Hội thoại mới", exact: true })
      .click();
    const created: AIConversation = await (await response).json();
    conversation = created.id;
    await expect(page).toHaveURL(new RegExp(`conversation=${conversation}`));
    expect(calls).toEqual(["/api/ai/conversations"]);
  });
  test("read actual demo metrics through tools, show evidence and persist history", async ({
    page,
    request,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      `/ai-workspace?project=xuong-may&conversation=${conversation}`,
    );
    await page
      .getByLabel("Câu hỏi SEO")
      .fill("Phân tích hiệu suất SEO 28 ngày gần nhất.");
    const response = page.waitForResponse(
      (r) =>
        r.url().includes(`/conversations/${conversation}/messages`) &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Gửi phân tích", exact: true })
      .click();
    const queued = await (await response).json();
    firstMessage = queued.id;
    const answer = page.locator(`[data-ai-message="${firstMessage}"]`);
    await expect(answer).toContainText("Hoàn tất", { timeout: 20000 });
    await expect(answer).toContainText("không gọi AI");
    await expect(answer.locator(".ai-grounded-metrics").first()).toContainText(
      "44.499",
    );
    await answer
      .getByRole("button", { name: "Mở bằng chứng GSC mô phỏng", exact: true })
      .first()
      .click();
    const panel = page.getByRole("dialog");
    await expect(panel).toContainText("site/byProperty");
    await expect(panel).toContainText("Mở báo cáo gốc");
    await expect(panel).toContainText("44499");
    await page.keyboard.press("Escape");
    await page.reload();
    await expect(
      page.locator(`[data-ai-message="${firstMessage}"]`),
    ).toContainText("Hoàn tất");
    expect(errors).toEqual([]);
    const usage = await (await request.get("/api/ai/usage")).json();
    expect(usage.total).toBe(0);
  });
  test("human approval stores notes and never executes SEO actions", async ({
    page,
  }) => {
    await page.goto(
      `/ai-workspace?project=xuong-may&conversation=${conversation}`,
    );
    const recommendation = page.locator(".ai-recommendation").first();
    await expect(recommendation).toBeVisible();
    await recommendation.getByRole("combobox").selectOption("approved");
    await recommendation
      .getByRole("textbox")
      .fill("Đã rà soát bằng chứng; chỉ lưu kế hoạch.");
    const response = page.waitForResponse(
      (r) =>
        r.url().includes("/api/ai/recommendations/") &&
        r.request().method() === "PATCH",
    );
    await recommendation
      .getByRole("button", { name: "Lưu review", exact: true })
      .click();
    const saved = await (await response).json();
    expect(saved.execution_triggered).toBe(false);
    await expect(page.getByRole("status")).toContainText("Đã lưu review");
    await page.reload();
    await expect(
      page.locator(`[data-recommendation="${saved.id}"]`).getByRole("combobox"),
    ).toHaveValue("approved");
    await expect(
      page.locator(`[data-recommendation="${saved.id}"]`).getByRole("textbox"),
    ).toHaveValue("Đã rà soát bằng chứng; chỉ lưu kế hoạch.");
  });
  test("follow-up keeps the reporting period and changing project clears conversation", async ({
    page,
  }) => {
    await page.goto(
      `/ai-workspace?project=xuong-may&conversation=${conversation}`,
    );
    await expect(page.getByLabel("Kỳ báo cáo AI")).toHaveValue("28");
    await page.getByLabel("Kỳ báo cáo AI").selectOption("7");
    await page
      .getByLabel("Câu hỏi SEO")
      .fill("Tiếp tục phân tích hiệu suất trong kỳ này.");
    await page
      .getByRole("button", { name: "Gửi phân tích", exact: true })
      .click();
    await expect(page.locator(".ai-answer").last()).toContainText("Hoàn tất");
    await page.reload();
    await expect(page.getByLabel("Kỳ báo cáo AI")).toHaveValue("7");
    await page.getByLabel("Website AI Workspace").selectOption("cong-ty");
    await expect(page).not.toHaveURL(/conversation=/);
    await expect(page.getByRole("status")).toContainText("Đã đổi website");
    await expect(
      page.locator(`[data-ai-message="${firstMessage}"]`),
    ).not.toBeVisible();
  });
  test("missing Topical Map is explicit and local report works with external traffic blocked", async ({
    page,
  }) => {
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      return ["localhost", "127.0.0.1"].includes(url.hostname)
        ? route.continue()
        : route.abort();
    });
    await page.goto(
      `/ai-workspace?project=xuong-may&conversation=${conversation}`,
    );
    await page
      .getByLabel("Câu hỏi SEO")
      .fill("Chủ đề nào trong Topical Map chưa có URL phù hợp?");
    await page
      .getByRole("button", { name: "Gửi phân tích", exact: true })
      .click();
    const answer = page.locator(".ai-answer").last();
    await expect(answer).toContainText("Hoàn tất");
    await expect(answer).toContainText("Topical Map chưa triển khai");
  });
  test("settings never collect a browser API key; show estimates, usage and saved sessions", async ({
    page,
  }) => {
    await page.goto(
      `/ai-workspace?project=xuong-may&conversation=${conversation}`,
    );
    const star = page.locator(
      '.ai-history-row.active button[title="Lưu phiên"]',
    );
    if (await star.isVisible()) await star.click();
    await page.getByRole("tab", { name: "AI Settings", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "OpenAI API Key Provider · cấu hình tại localhost" }),
    ).toBeVisible();
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
    await expect(page.locator(".ai-command")).toContainText(
      "configure_ai_provider.py",
    );
    await expect(page.getByLabel("Model AI")).toHaveValue("gpt-4.1-mini");
    await page
      .getByRole("tab", { name: "Usage & chi phí", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Token và chi phí ước tính" }),
    ).toBeVisible();
    await expect(
      page.getByText("Chưa có request cloud AI được ghi nhận.", { exact: false }),
    ).toBeVisible();
  });
});

for (const width of [1366, 768, 390])
  test(`AI Workspace responsive at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    await page.goto("/ai-workspace?project=xuong-may");
    await expect(
      page.getByRole("heading", { level: 1, name: /AI Workspace/ }),
    ).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
  });

test("OpenAI disabled fails clearly before any paid call", async ({ page }) => {
  await page.goto("/ai-workspace?project=xuong-may");
  await page.getByLabel("Chế độ phân tích AI").selectOption("openai");
  await page.getByLabel("Câu hỏi SEO").fill("Phân tích bằng AI.");
  await expect(
    page.getByRole("button", { name: "Gửi phân tích", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Xem ước tính lượt này" }).click();
  await expect(page.getByRole("alert")).toContainText("OpenAI đang tắt");
});

test("provider failure after consent is rendered safely (mocked provider API)", async ({
  page,
}) => {
  let approvedBody: Record<string, unknown> | undefined;
  await page.route("**/api/ai/conversations/*/estimate?*", (route) =>
    route.fulfill({
      json: {
        provider: "openai",
        model: "gpt-4.1-mini",
        turn_upper_estimate_usd: 0.01,
        max_calls: 3,
        daily_used_estimate_usd: 0,
        daily_limit_usd: 1,
        requires_external_consent: true,
        within_daily_limit: true,
      },
    }),
  );
  await page.route("**/api/ai/conversations/*/messages?*", (route) => {
    approvedBody = route.request().postDataJSON();
    return route.fulfill({
      status: 503,
      json: {
        code: "ai_provider_network",
        detail: "Không kết nối được OpenAI thử nghiệm; không tự retry.",
      },
    });
  });
  await page.goto("/ai-workspace?project=xuong-may");
  await page.getByLabel("Chế độ phân tích AI").selectOption("openai");
  await page.getByLabel("Câu hỏi SEO").fill("Phân tích provider thất bại.");
  await page.getByRole("button", { name: "Xem ước tính lượt này" }).click();
  await expect(page.getByRole("status")).toContainText("0,01");
  await page.getByLabel("Xác nhận gửi OpenAI").check();
  await page
    .getByRole("button", { name: "Gửi phân tích", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Không kết nối được OpenAI thử nghiệm",
  );
  expect(approvedBody).toMatchObject({
    approved_model: "gpt-4.1-mini",
    approved_max_estimate_usd: 0.01,
    acknowledge_external_processing: true,
  });
});

test("loading a populated conversation scrolls the chat without moving the website controls away", async ({
  page,
  request,
}) => {
  const list = await (
    await request.get("/api/ai/conversations?project_id=xuong-may")
  ).json();
  let id = "";
  for (const conv of list.rows) {
    const detail = await (
      await request.get(`/api/ai/conversations/${conv.id}?project_id=xuong-may`)
    ).json();
    if (
      detail.messages.some(
        (m: { role: string; status: string }) =>
          m.role === "assistant" && m.status === "completed",
      )
    ) {
      id = conv.id;
      break;
    }
  }
  expect(id).not.toBe("");
  await page.setViewportSize({ width: 390, height: 950 });
  await page.goto(`/ai-workspace?project=xuong-may&conversation=${id}`);
  await expect(page.locator(".ai-answer").first()).toBeAttached();
  await page.waitForTimeout(250);
  expect(await page.evaluate(() => scrollY)).toBe(0);
  await expect(
    page.getByRole("heading", { level: 1, name: /AI Workspace/ }),
  ).toBeInViewport();
});
