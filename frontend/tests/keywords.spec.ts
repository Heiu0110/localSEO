import { expect, test } from "@playwright/test";
import type { KeywordSet, Keyword } from "../src/types/keywords";

test.describe("Keyword Tracking persisted workflow", () => {
  test.describe.configure({ mode: "serial" });
  let set = "";
  let profile = "";
  let first = "";
  let second = "";
  test("create set and group with Vietnamese metadata", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/keyword-tracking?site=xuong-may&tab=sets");
    await expect(
      page.getByRole("heading", { level: 1, name: /Theo dõi từ khóa/ }),
    ).toBeVisible();
    const form = page.getByRole("form", {
      name: "Tạo bộ từ khóa",
      exact: true,
    });
    if (!(await form.isVisible()))
      await page
        .getByRole("button", { name: "Bộ từ khóa mới", exact: true })
        .click();
    await form
      .getByLabel("Tên bộ từ khóa", { exact: true })
      .fill("Kiểm thử Keyword " + Date.now());
    await form.getByLabel("Ngày bắt đầu theo dõi").fill("2026-10-19");
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/keyword-tracking/sets") &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Tạo bộ từ khóa", exact: true })
      .click();
    const created: KeywordSet = await (await response).json();
    set = created.id;
    profile = created.profiles[0].id;
    await expect(page.getByLabel("Bộ từ khóa", { exact: true })).toHaveValue(
      set,
    );
    await page.getByRole("tab", { name: "Cấu hình", exact: true }).click();
    await page.getByLabel("Tên nhóm mới").fill("Pillar");
    await page.getByRole("button", { name: "Thêm nhóm", exact: true }).click();
    await expect(page.getByLabel("Tên nhóm Pillar")).toBeVisible();
    expect(errors).toEqual([]);
  });
  test("add keywords, sticky grid, inline rank, NA, validation and history", async ({
    page,
  }) => {
    await page.goto(
      `/keyword-tracking?site=xuong-may&set=${set}&profile=${profile}&week=1`,
    );
    for (const [keyword, url] of [
      ["Balo tiếng Việt", "https://example.com/balo/"],
      ["Túi xách thủ công", "https://example.com/tui/"],
    ]) {
      await page
        .getByRole("button", { name: "Thêm từ khóa", exact: true })
        .click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Từ khóa", { exact: true }).fill(keyword);
      await dialog.getByLabel("URL đích", { exact: true }).fill(url);
      const response = page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/keyword-tracking/keywords") &&
          r.request().method() === "POST",
      );
      await dialog
        .getByRole("button", { name: "Lưu từ khóa", exact: true })
        .click();
      const created: Keyword = await (await response).json();
      if (!first) first = created.id;
      else second = created.id;
      await expect(dialog).not.toBeVisible();
    }
    const region = page.getByRole("region", { name: "Bảng theo dõi 35 tuần" });
    await expect(region.locator("th")).toHaveCount(42);
    await expect(region.locator("tbody tr")).toHaveCount(2);
    const before = await region
      .locator("tbody tr")
      .first()
      .locator("td")
      .nth(5)
      .boundingBox();
    await region.evaluate((el) => (el.scrollLeft = 1500));
    const after = await region
      .locator("tbody tr")
      .first()
      .locator("td")
      .nth(5)
      .boundingBox();
    expect(Math.abs(before!.x - after!.x)).toBeLessThan(2);
    await region.evaluate((el) => (el.scrollLeft = 0));
    await page
      .getByText("Nhập lịch sử: chỉ biết tuần, không có ngày giờ chính xác", {
        exact: true,
      })
      .click();
    const cell = region.locator(
      `tr[data-keyword-id="${first}"] button[data-week="1"]`,
    );
    await cell.click();
    const input = page.getByLabel("Rank tuần 1", { exact: true });
    await input.fill("0");
    await input.press("Enter");
    await expect(page.getByRole("alert")).toContainText("Nhập số nguyên");
    await input.fill("20");
    await input.press("Enter");
    await expect(cell).toContainText("20");
    await cell.click();
    await input.fill("8");
    await input.press("Tab");
    await expect(cell).toContainText("8");
    const next = region.locator(
      `tr[data-keyword-id="${first}"] button[data-week="2"]`,
    );
    await expect(next).toBeFocused();
    const na = region.locator(
      `tr[data-keyword-id="${second}"] button[data-week="1"]`,
    );
    await na.click();
    await input.fill("NA");
    await input.press("Enter");
    await expect(na).toHaveText("NA");
    await page
      .getByRole("button", { name: "Balo tiếng Việt", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Tất cả lần ghi nhận (2)");
    await expect(dialog.getByLabel("Biểu đồ lịch sử rank")).toBeVisible();
    await expect(dialog).toContainText("Chỉ biết tuần; không có giờ kiểm tra");
    await page.keyboard.press("Escape");
    await page.reload();
    await expect(cell).toContainText("8");
    await expect(na).toHaveText("NA");
  });
  test("filter sort, bulk metadata, weekly workflow and overview", async ({
    page,
  }) => {
    await page.goto(
      `/keyword-tracking?site=xuong-may&set=${set}&profile=${profile}&week=1`,
    );
    await page.getByLabel("Lọc rank", { exact: true }).selectOption("na");
    await expect(page.locator(".kw-table tbody tr")).toHaveCount(1);
    await page.getByLabel("Lọc rank", { exact: true }).selectOption("");
    await page.getByLabel("Sắp xếp từ khóa").selectOption("rank");
    await page.getByRole("button", { name: "Chọn trang", exact: true }).click();
    await page
      .locator('.kw-bulk-bar select[name="value"]')
      .selectOption({ label: "Pillar" });
    await page
      .getByRole("button", { name: "Áp dụng cho các dòng đã chọn" })
      .click();
    await expect(page.locator(".kw-table tbody .kw-group")).toHaveCount(2);
    await page.getByLabel("Tìm từ khóa hoặc URL").fill("balo");
    await expect(page.locator(".kw-table tbody tr")).toHaveCount(1);
    await page.getByRole("tab", { name: "Kiểm tra tuần", exact: true }).click();
    await expect(
      page.getByRole("heading", {
        level: 2,
        name: "Balo tiếng Việt",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Mở Google Search" }),
    ).toHaveAttribute("href", /https:\/\/www.google.com\/search\?q=Balo/);
    await page
      .getByText("Nhập lịch sử: chỉ biết tuần, không có ngày giờ chính xác", {
        exact: true,
      })
      .click();
    await page.getByLabel("Rank kiểm tra tuần").fill("5");
    await page
      .getByLabel("Ghi chú kiểm tra")
      .fill("Quan sát thủ công kiểm thử");
    await page.getByRole("button", { name: "Lưu và tiếp tục" }).click();
    await expect(page.getByRole("status").last()).toContainText("Đã lưu");
    await page.getByRole("tab", { name: "Tổng quan", exact: true }).click();
    await expect(page.locator(".kw-kpis")).toContainText("Top 10");
    await expect(page.locator(".kw-completion")).toContainText("2/2");
  });
  test("paste block preview atomically saves and exports both formats", async ({
    page,
  }) => {
    await page.goto(
      `/keyword-tracking?site=xuong-may&set=${set}&profile=${profile}&week=2`,
    );
    await page
      .getByText("Nhập lịch sử: chỉ biết tuần, không có ngày giờ chính xác", {
        exact: true,
      })
      .click();
    const cell = page.locator(
      `tr[data-keyword-id="${first}"] button[data-week="2"]`,
    );
    await cell.evaluate((el) => {
      const data = new DataTransfer();
      data.setData("text/plain", "3\tNA\n9\t");
      el.dispatchEvent(
        new ClipboardEvent("paste", {
          clipboardData: data,
          bubbles: true,
          cancelable: true,
        }),
      );
    });
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("4 ô");
    await dialog
      .getByRole("button", { name: "Xác nhận lưu toàn bộ rank" })
      .click();
    await expect(dialog).not.toBeVisible();
    await expect(cell).toHaveText("3");
    for (const format of ["CSV", "XLSX"]) {
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: format, exact: true }).click();
      expect((await download).suggestedFilename()).toBe(
        `keyword-tracking.${format.toLowerCase()}`,
      );
    }
  });
  test("CSV preview errors, acceptance and historical import", async ({
    page,
  }) => {
    await page.goto(
      `/keyword-tracking?site=xuong-may&set=${set}&profile=${profile}&tab=import`,
    );
    await page.getByLabel("Tệp bảng tính").setInputFiles({
      name: "từ-khóa.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "Từ khóa,Nhóm,URL,Tuần 1,Tuần 2\nTừ khóa nhập,Pillar,https://example.com/nhap/,NA,15\nDòng lỗi,,,0,\n",
        "utf8",
      ),
    });
    await page
      .getByRole("button", { name: "Xem trước tệp nhập", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: /Xem trước ·/ }),
    ).toBeVisible();
    await expect(
      page.getByText("Tuần 1: rank không hợp lệ.", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Xác nhận nhập dữ liệu" }),
    ).toBeDisabled();
    await page
      .getByText("Tôi chấp nhận bỏ qua toàn bộ dòng lỗi", { exact: true })
      .click();
    await page.getByRole("button", { name: "Xác nhận nhập dữ liệu" }).click();
    await expect(
      page.getByRole("button", { name: "Từ khóa nhập", exact: true }),
    ).toBeVisible();
  });
});
for (const width of [1366, 768, 390])
  test(`keyword responsive at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    await page.goto("/keyword-tracking?site=xuong-may");
    await expect(
      page.getByRole("heading", { level: 1, name: /Theo dõi từ khóa/ }),
    ).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
  });

test("GSC property selection, controlled sync, page scope and independent rank calendar", async ({
  page,
  request,
}) => {
  const { csrf_token } = await (await request.get("/api/session")).json();
  const headers = { "X-CSRF-Token": csrf_token };
  const properties = await (
    await request.post("/api/integrations/gsc/fixtures", { headers, data: {} })
  ).json();
  const property = properties.find((p: { site_url: string }) =>
    p.site_url.startsWith("sc-domain:"),
  );
  await request.post("/api/integrations/gsc/properties", {
    headers,
    data: { property_id: property.id, is_active: true },
  });
  const response = await request.post("/api/keyword-tracking/sets", {
    headers,
    data: {
      site_id: property.id,
      name: "GSC Keyword fixture " + Date.now(),
      start_date: "2026-10-19",
    },
  });
  expect(response.ok()).toBeTruthy();
  const set: KeywordSet = await response.json();
  const keyword = await (
    await request.post("/api/keyword-tracking/keywords", {
      headers,
      data: {
        keyword_set_id: set.id,
        keyword_text: "túi xách thử nghiệm 1",
        target_url: "https://fixture.example/trang-1",
      },
    })
  ).json();
  await page.goto(
    `/keyword-tracking?site=${property.id}&set=${set.id}&profile=${set.profiles[0].id}&week=4`,
  );
  await expect(page.getByLabel("Website theo dõi từ khóa")).toHaveValue(
    property.id,
  );
  await expect(page.getByLabel("Tuần theo dõi", { exact: true })).toHaveValue(
    "4",
  );
  const start = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/keyword-tracking/gsc-sync") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Đồng bộ GSC", exact: true }).click();
  const job = await (await start).json();
  await expect(page.locator(`[data-keyword-job="${job.id}"]`)).toContainText(
    "completed",
  );
  await expect(
    page.locator(`tr[data-keyword-id="${keyword.id}"] td`).nth(3),
  ).not.toHaveText("—");
  await page.getByLabel("Phạm vi GSC từ khóa").selectOption("page");
  await page.getByLabel("Kỳ GSC từ khóa").selectOption("7");
  const next = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/keyword-tracking/gsc-sync") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Đồng bộ GSC", exact: true }).click();
  const pageJob = await (await next).json();
  await expect(
    page.locator(`[data-keyword-job="${pageJob.id}"]`),
  ).toContainText("completed");
  await expect(
    page.locator(`tr[data-keyword-id="${keyword.id}"] td`).nth(5),
  ).toHaveText("7,5");
  await expect(page.getByLabel("Tuần theo dõi", { exact: true })).toHaveValue(
    "4",
  );
  await expect(
    page.locator(`tr[data-keyword-id="${keyword.id}"] button[data-week="4"]`),
  ).toHaveText("—");
});

test("server paging bounds the grid and keeps six columns and vertical headers fixed", async ({
  page,
  request,
}) => {
  const { csrf_token } = await (await request.get("/api/session")).json();
  const headers = { "X-CSRF-Token": csrf_token };
  const set: KeywordSet = await (
    await request.post("/api/keyword-tracking/sets", {
      headers,
      data: {
        site_id: "xuong-may",
        name: "UI pagination fixture " + Date.now(),
        start_date: "2026-10-19",
      },
    })
  ).json();
  const csv =
    "Từ khóa,Nhóm,URL\n" +
    Array.from(
      { length: 60 },
      (_, i) =>
        `Từ khóa phân trang ${String(i).padStart(3, "0")},,https://example.com/page-${i}/`,
    ).join("\n");
  const preview = await (
    await request.post("/api/keyword-tracking/import", {
      headers,
      multipart: {
        file: {
          name: "paging.csv",
          mimeType: "text/csv",
          buffer: Buffer.from(csv),
        },
        set_id: set.id,
        profile_id: set.profiles[0].id,
        mode: "keywords",
      },
    })
  ).json();
  const commit = await request.post(
    `/api/keyword-tracking/import/${preview.id}/commit`,
    { headers, data: { confirm: true } },
  );
  expect(commit.ok()).toBeTruthy();
  const started = Date.now();
  await page.goto(
    `/keyword-tracking?site=xuong-may&set=${set.id}&profile=${set.profiles[0].id}&week=1`,
  );
  const region = page.getByRole("region", { name: "Bảng theo dõi 35 tuần" });
  await expect(region.locator("tbody tr")).toHaveCount(25);
  test
    .info()
    .annotations.push({
      type: "grid-ready-ms",
      description: String(Date.now() - started),
    });
  await page.getByLabel("Số dòng từ khóa").selectOption("50");
  await expect(region.locator("tbody tr")).toHaveCount(50);
  const header = await region.locator("th").first().boundingBox();
  const fixed = await region
    .locator("tbody tr")
    .first()
    .locator("td")
    .evaluateAll((cells) =>
      cells.slice(0, 6).map((c) => c.getBoundingClientRect().x),
    );
  await region.evaluate((el) => {
    el.scrollLeft = 1900;
    el.scrollTop = 700;
  });
  const after = await region.locator("th").first().boundingBox();
  expect(Math.abs(header!.y - after!.y)).toBeLessThan(2);
  const x = await region
    .locator("tbody tr")
    .first()
    .locator("td")
    .evaluateAll((cells) =>
      cells.slice(0, 6).map((c) => c.getBoundingClientRect().x),
    );
  for (let i = 0; i < 6; i++) expect(Math.abs(fixed[i] - x[i])).toBeLessThan(2);
  await page.getByRole("button", { name: "Sau", exact: true }).click();
  await expect(region.locator("tbody tr")).toHaveCount(10);
});
