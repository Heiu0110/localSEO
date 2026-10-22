# Technical SEO v0.3 Core

Module bổ sung vào ứng dụng hiện có. Dashboard, MockProvider, SQLiteAnalyticsProvider, Google OAuth và sync GSC được giữ riêng. Không đổi theme, không đưa OAuth token vào crawler.

```text
Audit form → FastAPI validation → AuditProject + AuditRun (SQLite)
                                  ↓ một worker Technical SEO
Scope → DNS/IP pinned transport → robots → sitemaps → URL frontier
                                  ↓ checkpoint từng URL
                          HTML/headers + link graph
                                  ↓
                     deterministic rule engine (versioned)
                                  ↓
               immutable findings + remediation task updates
                                  ↓
Overview / server-paged explorers / history / comparison / exports
```

## Ranh giới

- `technical/urls.py`: định danh URL, glob include/exclude, host allowlist và chặn URL hành động.
- `technical/fetch.py`: transport httpx/httpcore, DNS validation và IP pinning tại socket; TLS vẫn xác thực hostname gốc. Chỉ GET, không proxy/env credentials, không cookie đăng nhập của người dùng. Rate limit, timeout, redirect guard, retry tối đa một lần cho lỗi tạm thời.
- `technical/robots.py`: nhóm user-agent, wildcard, longest-match/allow tie; crawler dùng UA nhận diện riêng. Googlebot là mô phỏng rules, không impersonate.
- `technical/sitemap.py`, `extract.py`: parser có giới hạn, XML chống DTD/entity, metadata/links/fingerprint; không lưu toàn bộ HTML.
- `technical/jobs.py`: một worker trong process, queue bền vững qua AuditRun, cancellation và checkpoint theo URL. GSC worker riêng, SQLite WAL/busy timeout dùng chung. Không Redis/Celery.
- `technical/rules.py` + `catalog.json`: catalog 138 checks, 63 capability tự động gồm thu thập tín hiệu và workflow; 39 rule sinh loại finding. Capability không đồng nghĩa đã đánh giá/đạt trong audit.
- `technical/reports.py`: SQL pagination/filter/sort, URL detail, rule states và so sánh thận trọng.
- `api/technical_routes.py`: project/run lifecycle, explorers, backlog, URL intent, CSV preview/commit, retention và CSV/JSON/HTML exports. Mutations dùng CSRF/Origin của ứng dụng; PATCH được thêm vào CORS local.
- `features/technical`: UI tiếng Việt dùng lại cards/tables/Sheet/Query và palette kem–be–nâu đồng. Không dựng kết quả cho website chưa audit.

## Tính nhất quán

Cấu hình và URL intent được snapshot khi bắt đầu. Lưu metadata từng URL rồi đánh giá graph/rules trong transaction cuối. Không ghi đè audit cũ khi recrawl. Backlog là trạng thái công việc hiện tại, tách khỏi bằng chứng lịch sử; xuất JSON ghi rõ `action_plan_current`.

So sánh xác nhận resolved chỉ khi hai audit hoàn tất coverage, cùng project/scope hash/rule version và check của URL thật sự được đánh giá lại. Task verification cũng cần snapshot trước có scope/version khớp. Audit gián đoạn/partial không chứng minh lỗi đã sửa.

GSC chỉ đọc **page/byPage/web** đã lưu trong 28 ngày tính tới ngày page dataset mới nhất, tối đa 5.000 seeds. Có ghi kỳ và nguồn exposure. Không gọi OAuth/Google mới để crawl, không cộng page totals thành KPI site, không tạo query–page pair hoặc Page Indexing giả.

Dashboard chỉ thêm thẻ tóm tắt khi có audit live khớp website/property; mặc định hai demo không phát sinh crawl. Fixture Technical SEO là nguồn thử nghiệm riêng, cố định `audit.fixture.example`, dùng MockTransport ngoại tuyến với cùng crawler/parser/rule engine và luôn gắn nhãn.

## Startup và offline

Alembic thêm revision `002_technical_audits`, không rebuild/xóa bảng GSC. Startup phục hồi queued/running thành interrupted, giữ kết quả đã lưu; Chạy lại tạo snapshot mới từ đầu. Dữ liệu cached, explorers, backlog và export dùng được khi mất Internet. Crawl mới cần truy cập website; không có monitoring khi backend tắt.
