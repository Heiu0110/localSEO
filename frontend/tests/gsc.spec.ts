import { expect, test } from '@playwright/test';
import type { GSCProperty, IntegrationStatus } from '../src/types/gsc';

test.describe('SQLite GSC workflow', () => {
  test.describe.configure({ mode: 'serial' });
  let propertyId = '';
  let start = '';
  let end = '';

  test('Settings creates isolated fixture, syncs SQLite and shows real progress', async ({ page, request }) => {
    test.setTimeout(60_000);
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Tích hợp Google Search Console', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Tạo bộ thử nghiệm SQLite', exact: true }).click();
    const checkbox = page.getByRole('checkbox', { name: 'Thêm sc-domain:fixture.example vào workspace', exact: true });
    await expect(checkbox).toBeVisible();
    if (!await checkbox.isChecked()) await checkbox.check();
    await expect(page.getByLabel('Property cần đồng bộ', { exact: true })).toBeVisible();
    const props: GSCProperty[] = await (await request.get('/api/integrations/gsc/properties')).json();
    propertyId = props.find(p=>p.site_url==='sc-domain:fixture.example')!.id;
    await page.getByLabel('Property cần đồng bộ', { exact: true }).selectOption(propertyId);
    const status: IntegrationStatus = await (await request.get('/api/integrations/gsc/status')).json();
    end = status.latest_final_date;
    start = new Date(Date.parse(end+'T00:00:00Z')-13*86400000).toISOString().slice(0,10);
    await page.getByLabel('Đồng bộ từ ngày', { exact: true }).fill(start);
    await page.getByLabel('Đồng bộ đến ngày', { exact: true }).fill(end);
    await page.getByLabel('Chế độ đồng bộ', { exact: true }).selectOption('refresh');
    await page.getByRole('button', { name: 'Bắt đầu đồng bộ', exact: true }).click();
    await expect(page.getByTestId('sync-job').first()).toContainText('Đã hoàn tất', { timeout: 40_000 });
    await expect(page.getByTestId('sync-job').first()).toContainText('14/14 ngày');
    await expect(page.getByTestId('sync-job').first().getByRole('progressbar')).toHaveAttribute('value','14');
    const jobs = await (await request.get(`/api/gsc/sync/jobs?property_id=${propertyId}`)).json();
    expect(jobs[0].status).toBe('completed');
    const overview = await (await request.get(`/api/dashboard/overview?site_id=${propertyId}&days=7`)).json();
    expect(overview.source).toBe('fixture');
    expect(overview.current.clicks).toBeGreaterThan(0);
  });

  test('Dashboard switches SQLite/demo without mixing their KPI sources', async ({ page, request }) => {
    await page.goto(`/?site=${propertyId}&days=7`);
    const o=await (await request.get(`/api/dashboard/overview?site_id=${propertyId}&days=7`)).json();
    await expect(page.getByTestId('metric-clicks')).toHaveText(o.current.clicks.toLocaleString('vi-VN'));
    await expect(page.getByRole('heading',{name:/^Tổng quan SEO/})).toContainText('Thử nghiệm SQLite');
    await expect(page.getByText('KPI dùng dữ liệu tổng cấp property', { exact: false })).toBeVisible();
    await page.getByLabel('Website', { exact: true }).selectOption('xuong-may');
    const mock=await (await request.get('/api/dashboard/overview?site_id=xuong-may&days=7')).json();
    await expect(page.getByTestId('metric-clicks')).toHaveText(mock.current.clicks.toLocaleString('vi-VN'));
    await page.getByLabel('Website',{exact:true}).selectOption(propertyId);
    await page.getByRole('navigation',{name:'Điều hướng chính'}).getByRole('link',{name:'Phân tích GSC',exact:true}).click();
    await expect(page.getByLabel('Property phân tích',{exact:true})).toHaveValue(propertyId);
  });

  test('analytics tabs, server pagination/search/sort, scope warnings, page details and all CSV exports', async ({ page }) => {
    const errors: string[]=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`/gsc-analytics?site=${propertyId}&start=${start}&end=${end}`);
    await expect(page.getByTestId('metric-clicks')).toBeVisible();
    for (const [label,dataset] of [['URL','pages'],['Truy vấn','queries'],['Quốc gia','countries'],['Thiết bị','devices']] as const) {
      await page.getByRole('tab',{name:label,exact:true}).click();
      const table=page.getByRole('region',{name:`Phân tích ${label}`,exact:true});
      await expect(table.locator('tbody tr').first()).toBeVisible();
      await table.getByRole('button',{name:`Sắp xếp ${label} GSC theo Lượt nhấp`,exact:true}).click();
      await expect(table.locator('th[aria-sort="ascending"]')).toBeVisible();
      const download=page.waitForEvent('download');
      await table.getByRole('button',{name:`Xuất ${label} CSV`,exact:true}).click();
      expect((await download).suggestedFilename()).toContain(`stored-${dataset}`);
    }
    await page.getByRole('tab',{name:'URL',exact:true}).click();
    const pages=page.getByRole('region',{name:'Phân tích URL',exact:true});
    await page.getByLabel('Số dòng URL GSC',{exact:true}).selectOption('10');
    await expect(pages.locator('tbody tr')).toHaveCount(10);
    await page.getByRole('button',{name:'Trang sau URL GSC',exact:true}).click();
    await expect(pages.locator('tbody tr')).toHaveCount(2);
    await page.getByLabel('Tìm URL GSC',{exact:true}).fill('trang-1');
    await expect(pages.locator('tbody tr')).toHaveCount(4);
    await pages.locator('.table-link').first().click();
    const panel=page.getByRole('dialog');
    await expect(panel).toContainText('Chưa đồng bộ quan hệ URL–query');
    await panel.getByRole('button',{name:'Lượt hiển thị',exact:true}).click();
    await expect(panel.getByRole('region',{name:'Biểu đồ Lượt hiển thị',exact:true})).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByLabel('Search type phân tích',{exact:true}).selectOption('image');
    await page.getByRole('tab',{name:'Tổng quan',exact:true}).click();
    await expect(page.getByText('Chưa có dữ liệu tổng trong kỳ này',{exact:true})).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('stored data is readable offline and shows insufficient comparison without fabricated deltas', async ({ page }) => {
    const external: string[]=[];
    await page.route('**/*',async route=>{
      const hostname=new URL(route.request().url()).hostname;
      if(!['127.0.0.1','localhost'].includes(hostname)){external.push(hostname);await route.abort();}
      else await route.continue();
    });
    await page.goto(`/?site=${propertyId}&days=90`);
    await expect(page.getByTestId('metric-clicks')).toBeVisible();
    await expect(page.getByText('Chưa đủ dữ liệu so sánh',{exact:true})).toHaveCount(4);
    await expect(page.getByRole('region',{name:'Biểu đồ Lượt nhấp',exact:true}).locator('.recharts-line-curve')).toHaveCount(1);
    expect(external).toEqual([]);
  });
});

test('Settings handles missing/revoked authorization and API errors without credential values in browser', async ({ page }) => {
  await page.route('**/api/integrations/gsc/status',route=>route.fulfill({json:{status:'reauthorization_required',configured:true,secure_storage_available:true,connection_id:'safe-id',display_name:'Google Search Console',message:null,scope:'https://www.googleapis.com/auth/webmasters.readonly',latest_final_date:'2026-10-18',history_start:'2025-06-21',pending_authorization:false}}));
  await page.route('**/api/integrations/gsc/oauth/start',route=>route.fulfill({status:401,json:{code:'reauthorization_required',detail:'Quyền Google đã hết hạn hoặc bị thu hồi. Hãy kết nối lại.'}}));
  await page.goto('/settings');
  await page.getByRole('button',{name:'Kết nối lại Google',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('hết hạn hoặc bị thu hồi');
  const body=await page.locator('body').innerText();
  expect(body).not.toContain('client_secret');
  expect(body).not.toContain('refresh_token');
});

for (const width of [1366,768,390]) {
  test(`integration screens remain usable at ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:1000});
    for(const path of ['/settings','/gsc-analytics']){
      await page.goto(path);
      await expect(page.getByRole('heading',{name:path==='/settings'?'Cài đặt':/Phân tích GSC/,exact:path==='/settings'})).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    }
  });
}
