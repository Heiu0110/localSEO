import { test, expect, type APIRequestContext } from "@playwright/test";
async function write(request: APIRequestContext, path: string, data: unknown) {
  const token = (await (await request.get("/api/session")).json()).csrf_token;
  const r = await request.post("/api" + path, {
    headers: { "X-CSRF-Token": token },
    data,
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}
const title = `Research E2E ${Date.now()}`;
test.describe("Research core workflow", () => {
  test.describe.configure({ mode: "serial" });
  let project = "";
  let keyword = "";
  let snapshot = "";
  test("create website-scoped research project from tracking entry", async ({
    page,
  }) => {
    await page.goto("/keyword-tracking?site=xuong-may");
    await page
      .getByRole("link", {
        name: "Keyword Research → Nghiên cứu từ khóa & SERP",
      })
      .click();
    await expect(
      page.getByRole("heading", { name: "Keyword Research", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Dự án mới", exact: true }).click();
    const panel = page.getByRole("dialog");
    await panel.getByLabel("Tên dự án").fill(title);
    await panel
      .getByLabel("Website", { exact: true })
      .selectOption("xuong-may");
    await panel
      .getByLabel("Mục tiêu nghiên cứu")
      .fill("Nghiên cứu dữ liệu có nguồn");
    await panel.getByRole("button", { name: "Tạo dự án", exact: true }).click();
    await expect(panel).not.toBeVisible();
    await expect(
      page.getByLabel("Dự án Research", { exact: true }),
    ).toContainText(title);
    project = new URL(page.url()).searchParams.get("research")!;
    expect(project).toBeTruthy();
  });
  test("seed preview deduplicates accents and keyword details persist", async ({
    page,
  }) => {
    await page.goto(`/keyword-research?research=${project}&tab=imports`);
    await page
      .getByLabel("Seed keywords", { exact: true })
      .fill(
        "may balo học sinh\nMAY BALO HỌC SINH\nxưởng may balo học sinh\ncách chọn balo",
      );
    await page.getByRole("button", { name: "Xem trước nguồn nhập" }).click();
    const panel = page.getByRole("dialog");
    await expect(panel).toContainText("1 dòng trùng");
    await panel.getByRole("button", { name: "Xác nhận nhập 4 dòng" }).click();
    await expect(panel).not.toBeVisible();
    await page
      .getByRole("button", { name: "Keyword Explorer", exact: true })
      .click();
    await expect(page.getByText("Trang 1 · 3 từ khóa")).toBeVisible();
    await page
      .getByRole("button", { name: "may balo học sinh", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel("Search Intent", { exact: true })
      .selectOption("commercial");
    await page
      .getByRole("dialog")
      .getByLabel("Ghi chú", { exact: true })
      .fill("Đã đọc seed, chưa có demand");
    await page.getByRole("button", { name: "Lưu từ khóa Research" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Đã lưu từ khóa Research",
    );
    await page.keyboard.press("Escape");
    await page.reload();
    await expect(
      page.getByRole("cell", { name: "Thương mại", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Chưa có", { exact: true }).first(),
    ).toBeVisible();
  });
  test("manual cluster review stays separate from tracking", async ({
    page,
  }) => {
    await page.goto(`/keyword-research?research=${project}&tab=keywords`);
    await page.getByLabel("Chọn may balo học sinh", { exact: true }).check();
    await page
      .getByLabel("Chọn xưởng may balo học sinh", { exact: true })
      .check();
    await page
      .getByLabel("Tạo cluster từ lựa chọn", { exact: true })
      .fill("Balo học sinh E2E");
    await page
      .getByRole("button", { name: "Tạo cluster", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText(
      "Đã tạo cluster bản nháp",
    );
    await page.getByRole("button", { name: "Clusters", exact: true }).click();
    await page
      .getByRole("button", { name: "Balo học sinh E2E", exact: true })
      .click();
    const panel = page.getByRole("dialog");
    await panel.getByLabel("Review cluster").selectOption("approved");
    await panel.getByLabel("Ghi chú & bằng chứng").fill("Đã rà soát thủ công");
    await panel.getByRole("button", { name: "Lưu review cluster" }).click();
    await expect(panel).not.toBeVisible();
    await expect(
      page.getByRole("cell", { name: "Đã duyệt", exact: true }),
    ).toBeVisible();
  });
  test("GSC imports keep impressions distinct and opportunities can be reviewed", async ({
    page,
    request,
  }) => {
    await page.goto(`/keyword-research?research=${project}&tab=imports`);
    await page.getByLabel("Nguồn nhập Research").selectOption("gsc");
    await page.getByRole("button", { name: "Xem trước nguồn nhập" }).click();
    const panel = page.getByRole("dialog");
    await expect(panel).toContainText("gsc_impressions");
    await panel.getByRole("button", { name: /Xác nhận nhập/ }).click();
    await expect(panel).not.toBeVisible();
    await page.getByRole("button", { name: "Cơ hội", exact: true }).click();
    await page
      .getByRole("button", { name: "Phân tích cơ hội", exact: true })
      .click();
    await page.keyboard.press("Escape");
    await expect(
      page
        .getByRole("heading", { name: /Có hiển thị · chưa duyệt mapping/ })
        .first(),
    ).toBeVisible();
    const card = page
      .locator(".research-panel")
      .filter({
        has: page.getByRole("heading", {
          name: /Có hiển thị · chưa duyệt mapping/,
        }),
      })
      .first();
    await card
      .getByLabel("Review", { exact: true })
      .selectOption("needs_review");
    await card
      .getByLabel("Ghi chú", { exact: true })
      .fill("Cần chọn target URL");
    await card.getByRole("button", { name: "Lưu review cơ hội" }).click();
    await expect(card).toContainText("Cần rà soát");
    const rows = await (
      await request.get(`/api/research/keywords?project_id=${project}`)
    ).json();
    keyword = rows.rows[0].id;
  });
  test("import observed SERP, inspect source profile and compare identical snapshot", async ({
    page,
  }) => {
    await page.goto(`/keyword-research?research=${project}&tab=serp`);
    await page
      .getByLabel("Keyword SERP", { exact: true })
      .selectOption(keyword);
    await page.getByLabel("Provider / nguồn").fill("E2E manual observation");
    await page.getByLabel("Địa điểm", { exact: true }).fill("Việt Nam");
    await page.getByLabel("Độ sâu yêu cầu").fill("2");
    await page
      .getByLabel("Thời điểm quan sát (giờ máy)")
      .fill("2026-10-20T10:00");
    await page
      .getByLabel("Độ đầy đủ", { exact: true })
      .selectOption("complete_observed");
    await page.getByLabel("Kết quả JSON (danh sách)").fill(
      JSON.stringify([
        {
          organic_position: 1,
          url: "https://example.org/a",
          title: "Bằng chứng A",
          snippet: "Dữ liệu nhập thử nghiệm có nhãn",
        },
        {
          organic_position: 2,
          url: "https://example.org/b",
          title: "Bằng chứng B",
        },
      ]),
    );
    await page
      .getByRole("button", { name: "Xem trước SERP", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Xác nhận nhập 1 dòng" })
      .click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    const option = page
      .getByLabel("Snapshot A", { exact: true })
      .locator("option")
      .filter({ hasText: "E2E manual observation" })
      .first();
    snapshot = (await option.getAttribute("value"))!;
    await page.getByLabel("Snapshot A", { exact: true }).selectOption(snapshot);
    await expect(
      page.getByRole("link", { name: "Bằng chứng A", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Organic position", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("not_found_within_observed_top_n", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("Snapshot B", { exact: true }).selectOption(snapshot);
    await page.getByRole("button", { name: "So sánh snapshots" }).click();
    await expect(page.getByRole("dialog")).toContainText("comparable");
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Đối thủ", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Đối thủ", exact: true }),
    ).toHaveClass(/active/);
    await expect(page.locator(".research-panel")).toContainText(
      "sampled_serps",
    );
    await expect(page.locator(".research-panel")).toContainText("example.org");
  });
  test("approved keyword transfer has a separate preview and no rank writes", async ({
    page,
    request,
  }) => {
    const ks = await write(request, "/keyword-tracking/sets", {
      site_id: "xuong-may",
      name: `Research transfer ${Date.now()}`,
      start_date: "2026-10-19",
    });
    await page.goto(`/keyword-research?research=${project}&tab=keywords`);
    await page.getByLabel("Tìm từ khóa Research").fill("may balo học sinh");
    await page.getByLabel("Chọn may balo học sinh", { exact: true }).check();
    await page.getByRole("button", { name: "Duyệt từ khóa đã chọn" }).click();
    // Approval clears the selection after the save; wait before reselecting.
    await expect(page.getByRole("status")).toContainText(
      "Đã lưu Research; chưa thay đổi Tracking.",
    );
    await page.getByLabel("Chọn may balo học sinh", { exact: true }).check();
    await page
      .getByLabel("Bộ Tracking đích", { exact: true })
      .selectOption(ks.id);
    await page
      .getByRole("button", { name: "Xem trước chuyển sang Tracking" })
      .click();
    await expect(page.getByRole("dialog")).toContainText("create");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Xác nhận nhập 1 dòng" })
      .click();
    await expect(page.getByRole("status")).toContainText(
      '"rank_observations_written":0',
    );
    const grid = await (
      await request.get(
        `/api/keyword-tracking/keywords?set_id=${ks.id}&profile_id=${ks.profiles[0].id}&week=1`,
      )
    ).json();
    expect(grid.total).toBe(1);
  });
  test("JSON export download and saved project survive reload", async ({
    page,
  }) => {
    await page.goto(`/keyword-research?research=${project}&tab=imports`);
    const dl = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Xuất báo cáo", exact: true })
      .click();
    expect((await dl).suggestedFilename()).toBe("research-keywords.json");
    await page.reload();
    await expect(
      page.getByLabel("Dự án Research", { exact: true }),
    ).toHaveValue(project);
    await page
      .getByRole("button", { name: "Dự án & cấu hình", exact: true })
      .click();
    await expect(page.getByLabel("Tên dự án", { exact: true })).toHaveValue(
      title,
    );
    await expect(
      page.getByText("not_connected", { exact: true }).first(),
    ).toBeVisible();
  });
});
for (const width of [1366, 768, 390])
  test(`Research responsive ${width}`, async ({ page, request }) => {
    const p = await write(request, "/research/projects", {
      name: `Responsive Research ${width} ${Date.now()}`,
      local_project_id: "xuong-may",
    });
    const j = await write(
      request,
      `/research/discovery/preview?project_id=${p.id}`,
      { source: "seed", text: "xưởng may balo học sinh" },
    );
    await write(request, `/research/import/${j.id}/commit?project_id=${p.id}`, {
      confirm: true,
    });
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`/keyword-research?research=${p.id}&tab=keywords`);
    await expect(
      page.getByRole("button", {
        name: "xưởng may balo học sinh",
        exact: true,
      }),
    ).toBeVisible();
    const selector = await page.getByLabel("Dự án Research", { exact: true }).boundingBox();
    expect(selector).not.toBeNull();
    expect(selector!.x + selector!.width).toBeLessThanOrEqual(width);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: "xưởng may balo học sinh", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(errors).toEqual([]);
  });
