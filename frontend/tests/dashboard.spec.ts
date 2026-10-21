import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { DimensionReport, Overview, PageDetail } from '../src/types/api';
import { pagesCsv } from '../src/features/dashboard/utils/csv';

for (const site of ['xuong-may', 'cong-ty']) {
  for (const days of [7, 28, 90]) {
    test(`UI metrics match API: ${site}, ${days} days`, async ({ page, request }) => {
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await page.goto('/');
      await page.getByLabel('Website', { exact: true }).selectOption(site);
      await page.getByLabel('Date range', { exact: true }).selectOption(String(days));
      const overview: Overview = await (await request.get(`/api/dashboard/overview?site_id=${site}&days=${days}`)).json();
      await expect(page.getByTestId('metric-clicks')).toHaveText(overview.current.clicks.toLocaleString('en-US'));
      await expect(page.getByTestId('metric-impressions')).toHaveText(overview.current.impressions.toLocaleString('en-US'));
      await expect(page.getByTestId('metric-ctr')).toHaveText(`${overview.current.ctr.toFixed(2)}%`);
      await expect(page.getByTestId('metric-position')).toHaveText(overview.current.position.toFixed(1));
      const chart = page.getByRole('region', { name: 'Clicks performance chart', exact: true });
      await expect(chart.locator('.recharts-line-curve')).toHaveCount(2);
      await page.getByRole('button', { name: 'CTR', exact: true }).click();
      await expect(page.getByRole('region', { name: 'CTR performance chart', exact: true })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Top pages', exact: true }).locator('tbody tr')).toHaveCount(5);
      await expect(page).toHaveURL(new RegExp(`site=${site}.*days=${days}`));
      expect(errors).toEqual([]);
    });
  }
}

test('tables search, sort, paginate, empty state, and query selection', async ({ page, request }) => {
  await page.goto('/?site=xuong-may&days=28');
  const pages = page.getByRole('region', { name: 'Top pages', exact: true });
  await expect(pages.locator('tbody tr')).toHaveCount(5);
  await pages.getByRole('button', { name: 'Next pages page' }).click();
  await expect(pages.getByText('6–10 of 12', { exact: false })).toBeVisible();
  await page.getByLabel('Rows per pages page').selectOption('20');
  await expect(pages.locator('tbody tr')).toHaveCount(12);
  const report: DimensionReport = await (await request.get('/api/dashboard/pages?site_id=xuong-may&days=28')).json();
  for (const key of ['clicks', 'impressions', 'ctr', 'position'] as const) {
    await page.getByRole('button', { name: `Sort pages by ${key}`, exact: true }).click();
    const header = pages.locator('th').filter({ has: page.getByRole('button', { name: `Sort pages by ${key}`, exact: true }) });
    const direction = await header.getAttribute('aria-sort');
    const sorted = [...report.rows].sort((a, b) => (a.metrics[key] - b.metrics[key]) * (direction === 'ascending' ? 1 : -1));
    await expect(pages.locator('tbody tr').first().getByRole('button')).toHaveAttribute('title', sorted[0].label);
  }
  await page.getByLabel('Search URL', { exact: true }).fill('may-balo');
  expect(await pages.locator('tbody tr').count()).toBeGreaterThan(0);
  for (const label of await pages.locator('.table-link').allTextContents()) expect(label).toContain('may-balo');
  await page.getByLabel('Search URL', { exact: true }).fill('nothing-matches-123');
  await expect(pages.getByText('No matching results')).toBeVisible();
  await expect(pages.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
  await page.getByRole('button', { name: 'Clear pages search' }).click();
  await expect(pages.locator('tbody tr')).toHaveCount(12);
  const queries = page.getByRole('region', { name: 'Top queries', exact: true });
  await page.getByLabel('Search queries', { exact: true }).fill('túi');
  await page.getByRole('button', { name: 'Sort queries by impressions', exact: true }).click();
  for (const label of await queries.locator('.table-link').allTextContents()) expect(label).toContain('túi');
  const rowText = await queries.locator('.table-link').first().textContent();
  await queries.locator('.table-link').first().click();
  await expect(page.getByRole('dialog')).toContainText(rowText!);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('page detail metrics and related queries match the API', async ({ page, request }) => {
  await page.goto('/?site=cong-ty&days=90');
  const rows: DimensionReport = await (await request.get('/api/dashboard/pages?site_id=cong-ty&days=90')).json();
  const first = rows.rows[0];
  await page.getByRole('region', { name: 'Top pages', exact: true }).getByRole('button', { name: new URL(first.label).pathname, exact: true }).click();
  const detail: PageDetail = await (await request.get(`/api/dashboard/pages/${first.id}?site_id=cong-ty&days=90`)).json();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText(first.label);
  await expect(dialog.locator('.detail-kpis')).toContainText(detail.current.clicks.toLocaleString('en-US'));
  for (const row of detail.queries) await expect(dialog).toContainText(row.label);
  await dialog.getByRole('button', { name: 'Close page details' }).click();
  await expect(dialog).toHaveCount(0);
});

test('CSV includes all filtered rows and the selected reporting context', async ({ page, request }) => {
  await page.goto('/?site=cong-ty&days=7');
  await page.getByLabel('Search URL', { exact: true }).fill('balo');
  const report: DimensionReport = await (await request.get('/api/dashboard/pages?site_id=cong-ty&days=7')).json();
  const expected = report.rows.filter(r => r.label.includes('balo'));
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(`mock-pages-cong-ty-${report.period.start}-${report.period.end}.csv`);
  const csv = readFileSync((await download.path())!, 'utf8');
  expect(csv).toBe(pagesCsv(expected));
  expect(csv.split('\r\n')).toHaveLength(expected.length + 1);
});

test('comparison, chart series, sidebar, navigation and URL restoration', async ({ page }) => {
  await page.goto('/?site=cong-ty&days=7');
  const chart = page.getByRole('region', { name: 'Clicks performance chart', exact: true });
  await expect(chart.locator('.recharts-line-curve')).toHaveCount(2);
  await page.getByLabel('Compare to previous period').uncheck();
  await expect(chart.locator('.recharts-line-curve')).toHaveCount(1);
  await page.getByLabel('Compare to previous period').check();
  await chart.getByRole('button', { name: 'Current period', exact: true }).click();
  await expect(chart.locator('.recharts-line-curve')).toHaveCount(1);
  await chart.getByRole('button', { name: 'Previous period', exact: true }).click();
  await expect(chart.getByText('Select a series above to display the chart.')).toBeVisible();
  await chart.getByRole('button', { name: 'Current period', exact: true }).click();
  await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
  await expect(page.locator('aside')).toHaveClass(/collapsed/);
  await page.getByRole('link', { name: 'Technical SEO', exact: true }).click();
  await expect(page.getByText('Module is planned for a future release.')).toBeVisible();
  await page.getByRole('link', { name: 'Back to Dashboard', exact: true }).click();
  await expect(page.getByLabel('Website', { exact: true })).toHaveValue('cong-ty');
  await expect(page.getByLabel('Date range', { exact: true })).toHaveValue('7');
  await page.reload();
  await expect(page.locator('aside')).toHaveClass(/collapsed/);
  await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
  await expect(page.locator('aside')).not.toHaveClass(/collapsed/);
});

test('loading, API error, retry and invalid site recovery', async ({ page }) => {
  let failing = true;
  await page.route('**/api/dashboard/overview?**', async route => {
    if (failing) await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"temporarily unavailable"}' });
    else await route.continue();
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('API request failed (503)');
  failing = false;
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByTestId('metric-clicks')).toBeVisible();
  await page.goto('/?site=missing&days=28');
  await expect(page.getByRole('alert')).toContainText('not found');
  await page.getByLabel('Website', { exact: true }).selectOption('xuong-may');
  await expect(page.getByTestId('metric-clicks')).toBeVisible();
  await page.route('**/api/dashboard/overview?**', async route => { await new Promise(resolve => setTimeout(resolve, 350)); await route.continue(); });
  await page.getByLabel('Date range', { exact: true }).selectOption('90');
  await expect(page.getByLabel('Loading dashboard', { exact: true })).toBeVisible();
  await expect(page.getByTestId('metric-clicks')).toBeVisible();
});

for (const width of [1366, 1024, 768, 390]) {
  test(`responsive layout has no page overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByTestId('metric-clicks')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByRole('region', { name: 'Clicks performance chart', exact: true }).locator('svg').last()).toBeVisible();
  });
}

test('runtime needs no external network resources', async ({ page }) => {
  const external: string[] = [];
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.hostname !== '127.0.0.1' && url.hostname !== 'localhost') { external.push(url.hostname); await route.abort(); }
    else await route.continue();
  });
  await page.goto('/');
  await expect(page.getByTestId('metric-clicks')).toBeVisible();
  await expect(page.getByText('Google Search Console', { exact: true })).toBeVisible();
  expect(external).toEqual([]);
});

test('CSV quotes labels, neutralizes formulas and preserves signed numeric values', () => {
  const metrics = { clicks: 2, impressions: 100, ctr: 2, position: 4 };
  const result = pagesCsv([{ id: 'x', label: '=HYPERLINK("bad")', metrics, previous: metrics, click_change_pct: -12.5 }]);
  expect(result).toContain('"\'=HYPERLINK(""bad"")"');
  expect(result).toContain('"-12.5"');
  expect(result.startsWith('\uFEFF')).toBe(true);
});

test('interactive API documentation works without a CDN', async ({ page }) => {
  const external: string[] = [];
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) { external.push(url.hostname); await route.abort(); }
    else await route.continue();
  });
  await page.goto('http://127.0.0.1:8000/docs');
  await expect(page.locator('.swagger-ui .info .title')).toContainText('SEO Local Workspace');
  const health = page.locator('.opblock').filter({ has: page.locator('[data-path="/api/health"]') });
  await health.locator('.opblock-summary').click();
  await health.getByRole('button', { name: 'Try it out', exact: true }).click();
  await health.getByRole('button', { name: 'Execute', exact: true }).click();
  await expect(health.locator('.live-responses-table')).toContainText('"provider": "mock"');
  expect(external).toEqual([]);
});
