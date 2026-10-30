import { test, expect } from "@playwright/test";
test.describe("AI Visibility Core evidence workflow", () => {
  test.describe.configure({ mode: "serial" });
  let project = "",
    prompt = "",
    opportunity = "";
  const title = `Visibility E2E ${Date.now()}`;
  test("create project brand competitor and prompt in existing theme", async ({
    page,
    request,
  }) => {
    const existing = await (
      await request.get("/api/visibility/projects")
    ).json();
    if (!existing.length) {
      const token = (await (await request.get("/api/session")).json())
        .csrf_token;
      const seeded = await request.post("/api/visibility/projects", {
        headers: { "X-CSRF-Token": token },
        data: {
          local_project_id: "xuong-may",
          name: "Visibility loading fixture",
        },
      });
      expect(seeded.ok()).toBeTruthy();
    }
    let releaseProjects!: () => void;
    const projectsReady = new Promise<void>((resolve) => {
      releaseProjects = resolve;
    });
    await page.route("**/api/visibility/projects", async (route) => {
      if (route.request().method() === "GET") await projectsReady;
      await route.continue();
    });
    await page.goto("/ai-visibility");
    await expect(
      page.getByRole("heading", { name: "AI Visibility", exact: false }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Dự án Visibility mới" }).click();
    const panel = page.getByRole("dialog");
    await expect(panel).toBeVisible();
    releaseProjects();
    await panel.getByLabel("Website Visibility").selectOption("xuong-may");
    await panel.getByLabel("Tên dự án", { exact: true }).fill(title);
    await panel.getByRole("button", { name: "Lưu", exact: true }).click();
    await expect(panel).not.toBeVisible();
    project = new URL(page.url()).searchParams.get("visibility")!;
    expect(project).toBeTruthy();
    await page.getByRole("button", { name: "Khai báo brand chính" }).click();
    await panel.getByLabel("Tên brand chính").fill("Acme Balo");
    await panel.getByLabel("Domain 1").fill("acme.test");
    await panel.getByRole("button", { name: "Lưu", exact: true }).click();
    await expect(panel).not.toBeVisible();
    await page
      .getByRole("button", { name: "Thêm đối thủ", exact: true })
      .click();
    await panel.getByLabel("Tên đối thủ").fill("Beta Bags");
    await panel.getByLabel("Domain 1").fill("beta.test");
    await panel.getByRole("button", { name: "Lưu", exact: true }).click();
    await expect(panel).not.toBeVisible();
    await page
      .getByRole("tab", { name: "Prompt Library", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Thêm prompt", exact: true })
      .click();
    await panel.getByLabel("Nội dung prompt").fill("Xưởng nào may balo tốt?");
    await panel.getByLabel("Chủ đề", { exact: true }).fill("may balo");
    await panel.getByRole("button", { name: "Lưu", exact: true }).click();
    await expect(panel).not.toBeVisible();
    const rows = await (
      await request.get(`/api/visibility/prompts?project_id=${project}`)
    ).json();
    prompt = rows.rows[0].id;
    await expect(
      page
        .getByRole("cell")
        .filter({ hasText: "Xưởng nào may balo tốt?" })
        .first(),
    ).toBeVisible();
  });
  test("manual response keeps raw text URL and citation separate", async ({
    page,
  }) => {
    await page.goto(`/ai-visibility?visibility=${project}&tab=observations`);
    await page.getByRole("button", { name: "Nhập phản hồi AI" }).click();
    const panel = page.getByRole("dialog");
    await panel
      .getByRole("combobox", { name: /^Prompt của quan sát/ })
      .selectOption(prompt);
    await panel.getByLabel("Provider quan sát").fill("Fixture provider");
    await panel.getByLabel("Model (nếu biết)").fill("model-fixture");
    await panel
      .getByLabel("Toàn bộ phản hồi gốc")
      .fill(
        "  Beta Bags được nhắc. https://acme.test/url-only <script>window.injected=true</script>  ",
      );
    await panel
      .getByRole("button", { name: "Lưu quan sát", exact: true })
      .click();
    await expect(panel).not.toBeVisible();
    await page
      .getByRole("button", { name: "Xem quan sát", exact: true })
      .click();
    await expect(
      panel.getByRole("heading", { name: "Toàn bộ phản hồi gốc" }),
    ).toBeVisible();
    await expect(panel).toContainText("https://acme.test/url-only");
    await expect(panel).toContainText("không phải 0% citation");
    expect(await page.evaluate(() => "injected" in window)).toBeFalsy();
    await page.keyboard.press("Escape");
    await page.getByRole("tab", { name: "Tổng quan", exact: true }).click();
    await expect(
      page.getByText("Unknown", { exact: true }).first(),
    ).toBeVisible();
  });
  test("import preview requires confirmation and preserves complete zero denominator", async ({
    page,
  }) => {
    await page.goto(`/ai-visibility?visibility=${project}&tab=imports`);
    await page.getByLabel("Dán danh sách JSON").fill(
      JSON.stringify([
        {
          prompt_id: prompt,
          provider: "Fixture provider",
          model: "model-fixture",
          response_text: "Acme Balo được nhắc nhưng không có citation.",
          citation_capability: "capable",
          citation_metadata: "complete",
        },
      ]),
    );
    await page
      .getByRole("button", { name: "Xem trước JSON", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Preview 1/1 dòng hợp lệ" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Xác nhận nhập 1 dòng" }).click();
    await expect(
      page.getByText("Đã nhập 1 dòng mới, bỏ qua 0 dòng trùng."),
    ).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Xuất Visibility" }).click();
    expect((await download).suggestedFilename()).toBe(
      "visibility-observations.json",
    );
  });
  test("deterministic rules show evidence review persists and offline Agent reuses history", async ({
    page,
    request,
  }) => {
    await page.goto(`/ai-visibility?visibility=${project}&tab=opportunities`);
    await page
      .getByRole("button", { name: "Phát hiện cơ hội từ evidence" })
      .click();
    const button = page
      .getByRole("button", { name: "Evidence & review" })
      .first();
    await expect(button).toBeVisible();
    await button.click();
    const panel = page.getByRole("dialog");
    await expect(
      panel.getByRole("heading", { name: "Bằng chứng gốc" }),
    ).toBeVisible();
    await panel
      .locator("details.visibility-evidence")
      .first()
      .locator("summary")
      .click();
    await expect(
      panel.getByRole("button", { name: "Mở quan sát gốc" }),
    ).toBeVisible();
    await panel
      .getByLabel("Quyết định review")
      .selectOption("needs_more_evidence");
    await panel
      .getByLabel("Ghi chú review GEO")
      .fill("Cần bổ sung quan sát cùng cohort trước khi thay đổi.");
    await panel.getByRole("button", { name: "Lưu review GEO" }).click();
    await expect(panel).toContainText("Cần thêm bằng chứng");
    const link = panel.getByRole("link", {
      name: "Phân tích sâu trong AI Workspace",
    });
    await expect(link).toHaveAttribute("href", /geo=/);
    const href = await link.getAttribute("href");
    opportunity = new URL(href!, "http://localhost").searchParams.get("geo")!;
    await panel
      .getByRole("button", { name: "Tạo phân tích ngoại tuyến" })
      .click();
    await expect(
      panel.getByRole("link", {
        name: "Mở kết quả và lịch sử trong AI Workspace",
      }),
    ).toBeVisible();
    await expect
      .poll(async () => {
        const data = await (
          await request.get(
            `/api/visibility/opportunities/${opportunity}?project_id=${project}`,
          )
        ).json();
        return data.analyses.length;
      })
      .toBe(1);
    await panel
      .getByRole("link", { name: "Mở kết quả và lịch sử trong AI Workspace" })
      .click();
    await expect(
      page.getByRole("heading", { name: /AI Workspace/, exact: false }),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          "Báo cáo ngoại tuyến từ rule và evidence đã lưu; các diễn giải/hành động cần người dùng xác minh.",
          { exact: false },
        )
        .first(),
    ).toBeVisible();
  });
  test("desktop and mobile evidence pages have no viewport overflow or console crashes", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(`/ai-visibility?visibility=${project}&tab=overview`);
      await expect(
        page.getByRole("heading", { name: "AI Visibility", exact: false }),
      ).toBeVisible();
      await expect(
        page.getByText("Brand Mention Rate", { exact: true }).first(),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: `test-results/visibility-${width}.png`,
        fullPage: true,
      });
    }
    expect(errors).toEqual([]);
  });
});
