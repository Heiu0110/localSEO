import { expect, test } from '@playwright/test';
import type { AuditProject, AuditRun } from '../src/types/technical';

test.describe('Technical SEO fixture workflow',()=>{
  test.describe.configure({mode:'serial'});
  let project='';let first='';let second='';let partial='';

  test('create fixture project, launch real audit worker and show stored findings',async({page,request})=>{
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('/technical-seo');
    await expect(page.getByRole('heading',{level:1,name:/^Technical SEO/})).toBeVisible();
    const fixture=page.getByRole('button',{name:'Tạo bộ thử nghiệm Technical SEO',exact:true});
    if(!await fixture.isVisible())await page.getByRole('button',{name:'Dự án mới',exact:true}).click();
    const response=page.waitForResponse(r=>r.url().endsWith('/api/technical/fixtures')&&r.request().method()==='POST');
    await fixture.click();const created:AuditProject=await (await response).json();project=created.id;
    await expect(page.getByLabel('Dự án Technical SEO',{exact:true})).toHaveValue(project);
    await page.getByRole('button',{name:'Chạy audit mới',exact:true}).click();
    await expect(page.getByRole('region',{name:'Tiến độ audit'}).getByRole('status')).toHaveText('Hoàn tất',{timeout:20000});
    first=new URL(page.url()).searchParams.get('audit')!;
    const run:AuditRun=await (await request.get(`/api/technical/audits/${first}`)).json();
    expect(run.status).toBe('completed');expect(run.summary.crawled).toBeGreaterThan(0);expect(run.summary.broken_links).toBeGreaterThan(0);
    await expect(page.getByText('Thử nghiệm ngoại tuyến',{exact:true}).first()).toBeVisible();
    await expect(page.getByRole('button',{name:'Liên kết nội bộ trỏ tới URL lỗi',exact:true}).first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('inventory sorting/search, URL evidence and indexability filters',async({page})=>{
    await page.goto(`/technical-seo?project=${project}&audit=${first}&tab=urls`);
    const table=page.getByRole('region',{name:'URL Inventory',exact:true});
    await expect(table.locator('tbody tr').first()).toBeVisible();
    await page.getByRole('button',{name:'Sắp xếp URL Inventory theo HTTP',exact:true}).click();
    await expect(table.locator('th[aria-sort="ascending"]')).toBeVisible();
    await page.getByLabel('Số dòng URL Inventory',{exact:true}).selectOption('10');
    await page.getByLabel('Tìm URL Inventory',{exact:true}).fill('/about');
    await expect(table.locator('tbody tr')).toHaveCount(1);
    await table.getByRole('button',{name:'https://audit.fixture.example/about',exact:true}).click();
    const panel=page.getByRole('dialog');
    await expect(panel).toContainText('Google index status');
    await expect(panel).toContainText('Chưa có URL Inspection');
    await expect(panel).toContainText('Độ sâu HTML quan sát');
    await page.keyboard.press('Escape');
    await page.getByLabel('Tìm URL Inventory',{exact:true}).fill('');
    await page.getByLabel('Lọc indexability',{exact:true}).selectOption('robots_blocked');
    await expect(table.locator('tbody tr')).toHaveCount(1);
    await expect(table.locator('tbody tr')).toContainText('/private');
  });

  test('filter issues, inspect evidence and update persistent backlog notes',async({page})=>{
    await page.goto(`/technical-seo?project=${project}&audit=${first}&tab=issues`);
    await page.getByLabel('Lọc mức độ vấn đề',{exact:true}).selectOption('high');
    const table=page.getByRole('region',{name:'Issue Explorer',exact:true});
    await expect(table.locator('tbody tr').first()).toBeVisible();
    await table.locator('.table-link').first().click();
    await expect(page.getByRole('dialog')).toContainText('Lý do ưu tiên');
    await expect(page.getByRole('dialog')).toContainText('Cách xác minh');
    await page.getByRole('button',{name:'Mở backlog xử lý',exact:true}).click();
    const backlog=page.getByRole('region',{name:'Action Backlog',exact:true});
    await backlog.locator('.table-link').first().click();
    await page.getByLabel('Trạng thái công việc',{exact:true}).selectOption('fixed');
    await page.getByLabel('Người xử lý',{exact:true}).fill('SEO');
    await page.getByLabel('Ghi chú công việc',{exact:true}).fill('Kiểm tra lại sau lần crawl tiếp theo.');
    await page.getByRole('button',{name:'Lưu công việc',exact:true}).click();
    await expect(page.getByRole('dialog')).toBeHidden();
    await expect(backlog).toContainText('Chờ audit xác minh');
    await expect(backlog).toContainText('SEO');
  });

  test('recrawl, compare equal scopes and export CSV/JSON/printable HTML',async({page,request})=>{
    await page.goto(`/technical-seo?project=${project}&audit=${first}`);
    const startedResponse=page.waitForResponse(response=>response.url().endsWith('/api/technical/audits')&&response.request().method()==='POST');
    await page.getByRole('button',{name:'Chạy audit mới',exact:true}).click();
    const started=await (await startedResponse).json();
    await expect(page.getByLabel('Snapshot audit',{exact:true})).toHaveValue(started.id);
    await expect(page.getByRole('region',{name:'Tiến độ audit'}).getByRole('status')).toHaveText('Hoàn tất',{timeout:20000});
    second=new URL(page.url()).searchParams.get('audit')!;expect(second).not.toBe(first);
    for(const name of ['Xuất CSV','Xuất JSON','Xuất HTML','CSV URL Inventory']){
      const download=page.waitForEvent('download');await page.getByRole('button',{name,exact:true}).click();
      expect((await download).suggestedFilename()).toContain('technical-');
    }
    await page.getByRole('button',{name:'So sánh audits',exact:true}).click();
    await page.getByLabel('Audit trước',{exact:true}).selectOption(first);
    await page.getByLabel('Audit sau',{exact:true}).selectOption(second);
    await page.getByRole('button',{name:'So sánh audit',exact:true}).click();
    await expect(page.getByText(/Vẫn còn:/)).toBeVisible();
    const compare=await (await request.get(`/api/technical/compare?before=${first}&after=${second}`)).json();
    expect(compare.comparable).toBe(true);expect(compare.counts.persistent).toBeGreaterThan(0);
    await page.getByRole('tab',{name:'Action Backlog',exact:true}).click();
    await expect(page.getByRole('region',{name:'Action Backlog',exact:true})).toContainText('Tái xuất hiện');
  });

  test('sitemaps, links, honest advanced status, CSV preview and custom limits',async({page})=>{
    await page.goto(`/technical-seo?project=${project}&audit=${second}`);
    await page.getByRole('tab',{name:'Sitemaps',exact:true}).click();
    await expect(page.getByRole('region',{name:'XML Sitemaps',exact:true})).toContainText('urlset');
    await page.getByRole('tab',{name:'Liên kết nội bộ',exact:true}).click();
    await expect(page.getByRole('region',{name:'Liên kết đã quan sát',exact:true})).toContainText('breadcrumb');
    await page.getByRole('tab',{name:'Hiệu suất',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Hiệu suất · chưa tích hợp CWV/PageSpeed',exact:true})).toBeVisible();
    await page.getByRole('tab',{name:'Cấu hình audit',exact:true}).click();
    await page.getByLabel('Nhập CSV URL quan trọng',{exact:true}).setInputFiles({name:'important.csv',mimeType:'text/csv',buffer:Buffer.from('url,priority,should_index,notes\nhttps://audit.fixture.example/orphan,critical_money,yes,Important\n')});
    await expect(page.getByText(/1 URL. Chưa áp dụng/)).toBeVisible();
    await page.getByRole('button',{name:'Xác nhận nhập URL',exact:true}).click();
    await expect(page.getByRole('status').filter({hasText:'Đã nhập 1 URL'})).toBeVisible();
    await page.getByLabel('Tối đa URL audit',{exact:true}).fill('2');
    const saved=page.waitForResponse(r=>r.url().includes(`/api/technical/projects/${project}`)&&r.request().method()==='PATCH');
    await page.getByRole('button',{name:'Lưu cấu hình',exact:true}).click();await saved;
    await expect(page.getByText('robots.txt luôn bật · HTML gốc · tối đa 2 URL',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Chạy audit mới',exact:true}).click();
    await expect(page.getByRole('region',{name:'Tiến độ audit'}).getByRole('status')).toHaveText('Kết quả một phần',{timeout:20000});
    partial=new URL(page.url()).searchParams.get('audit')!;
    await page.getByRole('button',{name:'So sánh audits',exact:true}).click();
    await page.getByLabel('Audit trước',{exact:true}).selectOption(second);await page.getByLabel('Audit sau',{exact:true}).selectOption(partial);
    await page.getByRole('button',{name:'So sánh audit',exact:true}).click();
    await expect(page.getByText('Audit không cùng scope/version hoặc chưa hoàn tất coverage. Vắng lỗi không có nghĩa đã sửa.',{exact:true})).toBeVisible();
  });

  test('cancel control uses explicit request and reflects cancelled status (mocked running job)',async({page,request})=>{
    const stored=await (await request.get(`/api/technical/audits/${partial}`)).json();let cancelled=false;
    await page.route(`**/api/technical/audits/${partial}`,route=>route.fulfill({json:{...stored,status:cancelled?'cancelled':'running',phase:cancelled?'Đã hủy':'Đang crawl'}}));
    await page.route(`**/api/technical/audits/${partial}/cancel`,route=>{cancelled=true;return route.fulfill({json:{...stored,status:'cancelled'}});});
    await page.goto(`/technical-seo?project=${project}&audit=${partial}`);
    await page.getByRole('button',{name:'Hủy audit',exact:true}).click();
    await expect(page.getByRole('region',{name:'Tiến độ audit'}).getByRole('status')).toHaveText('Đã hủy');
    expect(cancelled).toBe(true);
  });
});

test('unsafe website input is rejected before crawling',async({page})=>{
  await page.goto('/technical-seo');
  if(!await page.getByLabel('Website URL audit',{exact:true}).isVisible())await page.getByRole('button',{name:'Dự án mới',exact:true}).click();
  await page.getByLabel('Website URL audit',{exact:true}).fill('http://127.0.0.1/');
  await page.getByRole('button',{name:'Tạo dự án và bắt đầu audit',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Không crawl localhost');
});

for(const width of [1366,768,390]){
  test(`Technical SEO responsive at ${width}px`,async({page,request})=>{
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setViewportSize({width,height:1000});await page.goto('/technical-seo');
    await expect(page.getByRole('heading',{level:1,name:/^Technical SEO/})).toBeVisible();
    if(!await page.getByLabel('Dự án Technical SEO',{exact:true}).isVisible()){
      const session=await (await request.get('/api/session')).json();
      await request.post('/api/technical/fixtures',{data:{},headers:{'X-CSRF-Token':session.csrf_token}});
      await page.reload();await expect(page.getByLabel('Dự án Technical SEO',{exact:true})).toBeVisible();
    }
    for(const tab of ['Tổng quan','Crawl Explorer','Vấn đề','Cấu hình audit']){
      await page.getByRole('tab',{name:tab,exact:true}).click();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    }
    expect(errors).toEqual([]);
  });
}
