import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import type {
  CollectionRequest,
  LiveProviderState,
  LiveSettings,
} from "../src/types/visibilityLive";
async function write(request: APIRequestContext, path: string, data: unknown) {
  const token = (await (await request.get("/api/session")).json()).csrf_token;
  const result = await request.post("/api/visibility" + path, {
    headers: { "X-CSRF-Token": token },
    data,
  });
  expect(result.ok(), await result.text()).toBeTruthy();
  return result.json();
}
const cfg: LiveSettings = {
  enabled: true,
  model: "fixture-search-model",
  max_output_tokens: 1500,
  max_tool_calls: 1,
  search_context_size: "low",
  daily_limit_usd: 1,
  input_usd_per_million: 1,
  output_usd_per_million: 2,
  tool_usd_per_thousand_calls: 10,
  search_content_billing: "reported_input",
  search_content_tokens_per_call: 8000,
  pricing_source: "https://platform.openai.com/pricing/",
  pricing_reviewed_on: "2026-10-30",
  pricing_notes: "Synthetic UI fixture, not current API prices",
};
let project = "",
  prompt = "",
  observation = "";
const fixtureID = "ui_fixture_collection_001";
async function mockProvider(
  page: Page,
  mode:
    | "success"
    | "disconnected"
    | "unsupported"
    | "no-search"
    | "unknown" = "success",
) {
  const state: LiveProviderState = {
    provider: "openai_web_search",
    settings: cfg,
    key_configured: mode !== "disconnected",
    secure_storage_available: true,
    capability_status:
      mode === "unsupported" ? "Web Search Unsupported" : "Model Accessible",
    web_search_capability: "Live Check Pending",
    model_accessible: true,
    web_search_supported: false,
    last_validation: null,
    pricing_status: "user_reviewed_estimate",
    daily_used_estimate_usd: 0,
    effective_daily_limit_usd: 1,
    live_verification: "Pending Live Verification",
    limitations: [],
  };
  let current: CollectionRequest | null = null,
    confirms = 0,
    runningReads = 0;
  const complete = () => {
    if (!current) return;
    current.status =
      mode === "no-search"
        ? "PARTIAL"
        : mode === "unknown"
          ? "UNKNOWN_REMOTE_OUTCOME"
          : "COMPLETED";
    current.result = {
      search_execution:
        mode === "no-search" ? "NO_SEARCH_EXECUTED" : "SEARCH_COMPLETED",
      citation_count: 1,
      source_count: 2,
      actual_model: cfg.model!,
      response_id: "resp_ui_fixture",
      ...(mode === "unknown"
        ? {
            error_code: "live_network_unknown",
            detail: "Provider có thể đã tính phí; không tự gửi lại.",
          }
        : {}),
    };
    current.observation_id = mode === "success" ? observation : null;
    current.usage = {
      status: mode === "unknown" ? "unknown" : "completed_estimate",
      input_tokens: mode === "unknown" ? null : 350,
      output_tokens: mode === "unknown" ? null : 120,
      reserved_usd: 0.1,
      estimated_cost_usd: mode === "unknown" ? null : 0.01059,
      data: { provider_reported_dollar_cost: null },
    };
    current.result.provider_response = {
      id: "resp_ui_fixture",
      status: "completed",
      output: [
        {
          type: "web_search_call",
          status: "completed",
          action: {
            type: "search",
            sources: [
              { type: "url", url: "https://beta.test/retrieved-not-cited" },
            ],
          },
        },
        {
          type: "message",
          content: [
            {
              type: "output_text",
              text: "Acme Balo",
              annotations: [
                {
                  type: "url_citation",
                  title: "Acme Official Fixture",
                  url: "https://acme.test/source",
                  start_index: 0,
                  end_index: 9,
                },
              ],
            },
          ],
        },
      ],
    };
  };
  await page.route("**/api/visibility/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/visibility/providers")
      return route.fulfill({ json: state });
    if (path === "/api/visibility/providers/openai-web-search/validate-model")
      return route.fulfill({ json: state });
    if (path === "/api/visibility/collection/preflight") {
      const body = route.request().postDataJSON();
      current = {
        id: fixtureID,
        project_id: project,
        prompt_id: prompt,
        status: "PREFLIGHT_READY",
        binding_hash: "a".repeat(64),
        observation_id: null,
        usage_id: null,
        dispatched_at: null,
        created_at: "2026-10-30T00:00:00Z",
        consent_id: null,
        usage: null,
        result: {},
        snapshot: {
          binding: {
            prompt_snapshot: "Những tiêu chí chọn xưởng may balo?",
            provider: "openai_web_search",
            settings: cfg,
            context: {
              country: body.country,
              language: body.language,
              city: body.city,
              region: body.region,
            },
            authorized_max_usd: body.authorized_max_usd,
          },
          estimate: {
            known_component_estimate_usd: 0.021,
            total_estimate_usd: 0.021,
            model_estimate_usd: 0.011,
            tool_estimate_usd: 0.01,
            estimated_input_tokens: 9000,
            estimated_search_calls: 1,
            unknown_cost_components: [],
            limitations: ["Đây không phải provider billing cap."],
          },
          expires_at: "2099-01-01T00:00:00Z",
          capability_status: state.capability_status,
        },
      };
      return route.fulfill({ status: 201, json: current });
    }
    if (path.endsWith(`/collection/requests/${fixtureID}/confirm`)) {
      confirms++;
      const body = route.request().postDataJSON();
      expect(body.acknowledge_external_processing).toBe(true);
      expect(body.confirm_exact_prompt).toBe(true);
      expect(body.acknowledge_not_billing_cap).toBe(true);
      expect(body.acknowledge_capability_test).toBe(true);
      current!.status = "RUNNING";
      current!.consent_id = "ui_consent_fixture";
      return route.fulfill({ status: 202, json: current });
    }
    if (path.endsWith(`/collection/requests/${fixtureID}`)) {
      if (current?.status === "RUNNING" && ++runningReads >= 3) complete();
      return route.fulfill({ json: current });
    }
    if (path === "/api/visibility/collection/requests")
      return route.fulfill({
        json: {
          rows: current ? [current] : [],
          total: current ? 1 : 0,
          page: 1,
          page_size: 10,
        },
      });
    if (path.endsWith(`/observations/${observation}/search-sources`))
      return route.fulfill({
        json: [
          {
            id: "source-1",
            normalized_url: "https://beta.test/retrieved-not-cited",
            data: {
              type: "SEARCH_SOURCE",
              call_id: "ws_ui",
              source_content_verified: false,
            },
          },
          {
            id: "source-2",
            normalized_url: "https://acme.test/source",
            data: {
              type: "SEARCH_SOURCE",
              call_id: "ws_ui",
              source_content_verified: false,
            },
          },
        ],
      });
    await route.continue();
  });
  return { confirmCount: () => confirms };
}
test.describe("Visibility live controls with provider mocks", () => {
  test.beforeAll(async ({ request }) => {
    const p = await write(request, "/projects", {
      local_project_id: "xuong-may",
      name: `Live UI Fixture ${Date.now()}`,
    });
    project = p.id;
    await write(request, `/entities?project_id=${project}`, {
      name: "Acme Balo",
      domains: [{ domain: "acme.test" }],
    });
    await write(request, `/entities?project_id=${project}`, {
      kind: "competitor",
      name: "Beta Bags",
      domains: [{ domain: "beta.test" }],
    });
    prompt = (
      await write(request, `/prompts?project_id=${project}`, {
        text: "Những tiêu chí chọn xưởng may balo?",
        topic: "May balo",
        intent: "commercial",
      })
    ).id;
    observation = (
      await write(request, `/observations?project_id=${project}`, {
        prompt_id: prompt,
        provider: "openai_web_search_fixture",
        model: "fixture-search-model",
        collection_method: "PROVIDER_API",
        response_text: "Acme Balo <script>window.liveXSS=true</script>",
        grounding: "enabled",
        citation_capability: "capable",
        citation_metadata: "complete",
        citations: [
          {
            url: "https://acme.test/source",
            source_type: "provider_annotation",
            annotation_id: "2:0:0",
            source_verification: "provider_reported",
          },
        ],
        source_metadata: {
          collection_request_id: fixtureID,
          provider_response_id: "resp_ui_fixture",
          search_execution: "SEARCH_COMPLETED",
          answer_citations: [
            {
              annotation_id: "2:0:0",
              title: "Acme Official Fixture",
              normalized_url: "https://acme.test/source",
              span_mapping: {
                status: "unavailable_contract_unit_unverified",
                highlight_verified: false,
              },
            },
          ],
        },
        notes: "Synthetic Playwright fixture. No live provider call.",
      })
    ).id;
  });
  test("disconnected provider keeps manual workflows available without any paid request", async ({
    page,
  }) => {
    const mock = await mockProvider(page, "disconnected");
    await page.goto(
      `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
    );
    await expect(
      page.getByText("Chưa kết nối API key", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Kiểm tra với AI Search · xem preflight",
      }),
    ).toBeDisabled();
    await page.getByRole("tab", { name: "Quan sát", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Nhập phản hồi AI" }),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(0);
  });
  test("unsupported search is shown separately from API key presence", async ({
    page,
  }) => {
    const mock = await mockProvider(page, "unsupported");
    await page.goto(
      `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
    );
    await expect(
      page.getByText(/Web Search Unsupported/).first(),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(0);
  });
  test("preflight disclosure explicit consent running result and reload are safe", async ({
    page,
  }) => {
    const mock = await mockProvider(page);
    await page.goto(
      `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
    );
    await page
      .getByRole("button", { name: "Kiểm tra với AI Search · xem preflight" })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Tính preflight · chưa gửi provider" })
      .click();
    await expect(
      page.getByRole("heading", { name: "Xác nhận đúng một lượt trả phí" }),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(0);
    const form = page.locator("form.visibility-consent");
    for (const box of await form.getByRole("checkbox").all()) await box.check();
    await form
      .getByRole("button", { name: "Xác nhận và gửi một lượt trả phí" })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Đang kiểm tra AI Search",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Đã hoàn tất", exact: true }),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(1);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Đã hoàn tất", exact: true }),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(1);
  });
  test("native citation titles sources QA and GEO remain distinct", async ({
    page,
  }) => {
    const mock = await mockProvider(page);
    await page.goto(
      `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
    );
    await page
      .getByRole("button", { name: "Kiểm tra với AI Search · xem preflight" })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Tính preflight · chưa gửi provider" })
      .click();
    const form = page.locator("form.visibility-consent");
    await expect(form).toBeVisible();
    for (const box of await form.getByRole("checkbox").all()) await box.check();
    await form
      .getByRole("button", { name: "Xác nhận và gửi một lượt trả phí" })
      .click();
    await expect(
      page.getByRole("button", { name: "Mở observation và kiểm tra citation" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Mở observation và kiểm tra citation" })
      .click();
    const panel = page.getByRole("dialog");
    const link = panel.getByRole("link", { name: "Acme Official Fixture" });
    await expect(link).toHaveAttribute("href", "https://acme.test/source");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
    await expect(
      panel.getByRole("heading", {
        name: "Search Sources · không đồng nghĩa được trích dẫn",
      }),
    ).toBeVisible();
    await expect(
      panel.getByRole("link", {
        name: "https://beta.test/retrieved-not-cited",
      }),
    ).toBeVisible();
    expect(await page.evaluate(() => "liveXSS" in window)).toBeFalsy();
    await panel.getByLabel("QA extraction decision").selectOption("confirmed");
    await panel
      .getByLabel("Lý do QA extraction")
      .fill("Checked native answer/citations in synthetic fixture");
    await panel.getByRole("button", { name: "Lưu QA extraction" }).click();
    await expect(panel.getByText(/Review đã lưu:/)).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("tab", { name: "GEO Opportunities" }).click();
    await page
      .getByRole("button", { name: "Phát hiện cơ hội từ evidence" })
      .click();
    await expect(
      page.getByText(
        "Không đủ bằng chứng để đề xuất thay đổi. Không tạo lời khuyên chung để lấp danh sách.",
      ),
    ).toBeVisible();
    expect(mock.confirmCount()).toBe(1);
  });
  for (const [mode, label] of [
    ["no-search", "Không thực hiện search"],
    ["unknown", "Chưa rõ kết quả từ xa / có thể đã tính phí"],
  ] as const) {
    test(`${mode} is not silently successful or retried`, async ({ page }) => {
      const mock = await mockProvider(page, mode);
      await page.goto(
        `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
      );
      await page
        .getByRole("button", { name: "Kiểm tra với AI Search · xem preflight" })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Tính preflight · chưa gửi provider" })
        .click();
      const form = page.locator("form.visibility-consent");
      await expect(form).toBeVisible();
      for (const box of await form.getByRole("checkbox").all())
        await box.check();
      await form
        .getByRole("button", { name: "Xác nhận và gửi một lượt trả phí" })
        .click();
      await expect(
        page.getByText(label, { exact: false }).first(),
      ).toBeVisible();
      await page.reload();
      await expect(
        page.getByText(label, { exact: false }).first(),
      ).toBeVisible();
      expect(mock.confirmCount()).toBe(1);
    });
  }
  test("mobile provider and preflight retain responsive layout", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockProvider(page);
    await page.goto(
      `/ai-visibility?visibility=${project}&tab=live&live_prompt=${prompt}`,
    );
    await expect(
      page.getByRole("heading", {
        name: "OpenAI Web Search · kiểm tra từng prompt",
      }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: "test-results/visibility-live-mobile.png",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Kiểm tra với AI Search · xem preflight" })
      .click();
    await expect(
      page
        .getByRole("dialog")
        .getByRole("button", { name: "Tính preflight · chưa gửi provider" }),
    ).toBeVisible();
  });
});
