# Architecture · SEO Local Workspace v0.8 Core · Phase 8

Phase 8 thêm AI Visibility: immutable observations/extraction revisions → cohort metrics → 9 deterministic GEO rules → existing AIManager verification/review. Migration006 thêm 15 bảng; 9 read-only tools mới, không thêm AI stack/live provider. [Kiến trúc](docs/AI_VISIBILITY_ARCHITECTURE.md), [dữ liệu](docs/AI_VISIBILITY_DATA_MODEL.md), [Agent](docs/GEO_AGENT_INTEGRATION.md).

Phase 7 thêm `Keyword Research → stored source adapters → Research SQLite → review → explicit add-only Tracking transfer`, 10 bảng riêng trong migration005 và 7 read-only tools vào Agent hiện có. Không thêm provider live hoặc lịch chạy nền. Xem [kiến trúc Research](docs/KEYWORD_RESEARCH_ARCHITECTURE.md).

Phase 6 thêm `AI Workspace → AIManager → ToolRegistry → existing SEO services`, evidence/review/history/usage riêng trong 6 bảng Agent. OpenAI là provider tùy chọn HTTPS cố định, OS keyring, consent/budget; mặc định local_report không dùng LLM. Không có publishing, arbitrary SQL/shell hoặc AI calls nền. Topical Map chưa có service, không đăng ký tool giả. Xem [kiến trúc Agent](docs/AI_AGENT_ARCHITECTURE.md) và [security](docs/AI_AGENT_SECURITY.md).

Keyword Tracking thêm đường dữ liệu riêng: `Keyword Set → tuần/profile → MANUAL observations → SQLite → grid/overview/history`. GSC keyword cache dùng exact query và scope property/page qua OAuth/client sẵn có; không ghép query/page totals, không biến Average Position thành rank thủ công. Queue, import preview/commit và các bảng được thêm bằng migration003. Dashboard chỉ thêm thẻ nhỏ; route Keyword Tracking tải riêng. Xem [kiến trúc Keyword Tracking](docs/KEYWORD_TRACKING_ARCHITECTURE.md).

Technical SEO bổ sung một đường dữ liệu độc lập: `Audit Project → safe HTTP crawler → SQLite snapshots → rules / reports / backlog`. Crawler không dùng OAuth; chỉ đọc GSC page facts đã lưu khi project có property phù hợp. Dashboard có thẻ tóm tắt khi đã có audit live khớp website. Không thay MockProvider hoặc DashboardService. Xem [kiến trúc Technical SEO](docs/TECHNICAL_SEO_ARCHITECTURE.md), [crawler](docs/TECHNICAL_CRAWLER.md), [data model](docs/TECHNICAL_DATA_MODEL.md) và [rules](docs/TECHNICAL_RULES.md).

## Hai đường dữ liệu, cùng Dashboard

```text
MockProvider → DashboardService ────────────────────────────────┐
                                                              ├→ FastAPI → TanStack Query → Dashboard
Google OAuth → GoogleGSCClient → SyncManager → SQLite           │
                                           ↓                  │
                                   SQLiteAnalyticsProvider ────┘
                                           ↓
                                      GSC Analytics
```

Frontend/backend vẫn là hai tiến trình loopback. Giữ React/TypeScript/Vite/Tailwind/Radix/Recharts, palette kem–be–nâu đồng–espresso, sidebar, card/table/chart và Windows launchers. Không tạo project mới, cloud deployment, login, Redis/Celery hoặc database server.

MockProvider và DashboardService v0.1 giữ nguyên. Factory trong api/routes.py chỉ chọn Mock cho hai demo IDs cố định; active property UUID dùng SQLiteAnalyticsProvider. Không fallback từ property thiếu dữ liệu sang Mock. FixtureGSCClient là nguồn thử nghiệm thứ ba ghi SQLite, có nhãn fixture và domain .example, không dùng quyền/quota Google.

## Ranh giới module

- db/models.py, db/database.py, migrations/: SQLAlchemy, foreign keys/WAL, versioned Alembic schema. Không lưu token/client JSON trong SQL.
- gsc/vault.py: OS-backed keyring; từ chối plaintext backends, không có file-key fallback hoặc production memory token store.
- gsc/oauth.py: Desktop Authorization Code/PKCE, một read-only scope, callback loopback, one-time state 10 phút, refresh/revoke. Không thêm profile scope để lấy email/avatar.
- gsc/client.py: Sites API, Search Analytics, timeout, safe error normalization và retry/backoff. Google requests chỉ ở backend. Fixture dùng cùng protocol nhưng không được coi là Google thật.
- gsc/sync.py: một worker, durable queue/checkpoints; dataset/ngày thay atomically sau khi lấy/validate hết trang. Unique constraints chống nhân đôi và active jobs trùng property.
- gsc/repository.py: exact property identifiers và membership. Bỏ property khỏi workspace không xóa lịch sử.
- providers/sqlite_provider.py: report-level provider, aggregation cùng scope, SQL server pagination/sort/search, missing-day gaps, coverage và page detail.
- api/gsc_routes.py: integration/sync/analytics/export endpoints và CSV spooling. api/routes.py giữ Dashboard endpoints, thêm provider resolution.
- Frontend services/gscApi.ts và types/gsc.ts: typed integration API và cache keys theo property/ngày/type/filter.
- features/settings, components/gsc/SyncPanel: OAuth file picker/status, property management, fixture creation, progress/cancel/retry; polling chỉ khi active, invalidation sau hoàn tất.
- features/gsc, components/gsc/AnalyticsTable: năm tabs, server pagination/sort/search và CSV dữ liệu đã lưu. Reuse MetricCard, PerformanceChart, PageDetailPanel và UI primitives hiện có.

## Data accuracy

Không ép GSC thành cross-product fact cube như synthetic mock. Có 5 independent datasets: site/query/country/device dùng byProperty; page dùng byPage. responseAggregationType phải khớp trước khi commit. Không suy ra URL–query relationship từ hai aggregate tables độc lập.

KPI website chỉ đọc site. CTR = tổng clicks/tổng impressions × 100; position = tổng(position×impressions)/tổng impressions trong cùng scope. Kỳ trước có cùng N ngày, liền trước và không chồng lấn. Không cộng Top Queries/Pages làm tổng traffic website.

Overview thêm has_data, comparison_available, coverage và warnings. Missing daily metrics = null; API trả rỗng chỉ có checkpoint empty. Thiếu lịch sử thì delta/percent null. Dimension vắng trong một kỳ không đồng nghĩa giảm 100%. Share country/device dùng các dòng cùng dimension đã lưu, có ghi rõ basis.

API pagination 25.000 rows/request, cap 50.000/day/type. api_response chỉ nói đã kết thúc truy xuất, không bảo đảm Google cung cấp mọi query/page. api_limited/unknown được lưu và trả metadata. SQLite detail reports luôn coverage partial; Mock vẫn complete và đối chiếu partition như v0.1.

## Consistency và state

Một sync worker, transaction ngắn và SQLite WAL/busy timeout. Shared lock ngăn thay metric facts giữa các truy vấn trong cùng report. Dashboard lấy anchor ngày từ overview và truyền cùng end_date cho chart/table/detail. CSV tạo snapshot trong temporary spool giới hạn RAM, sau đó stream mà không giữ thread-owned lock qua ASGI yields.

TanStack Query giữ API state; URL giữ site/days, GSC thêm start/end/type/tab. Dashboard chống filter updates ghi đè khi route transitions chồng lấn. Sidebar preference vẫn localStorage; không có Google tokens trong browser storage. Sync completion invalidates report/site/property caches, kể cả job xong nhanh trước lần polling đầu.

## API compatibility và security

Swagger /docs dùng assets local; OpenAPI /openapi.json. Site giữ id/domain và thêm source_type. Các endpoint Dashboard cũ giữ shape chính; source enum mở rộng mock/gsc/fixture, PerformancePoint metric nullable khi thiếu, metadata real reports được bổ sung. Demo giữ nguyên số liệu. Health version=0.3.0, provider=hybrid. Technical routes là bổ sung; trạng thái source Technical SEO có Not Audited/Auditing/Audited/Partial, không giả là đã crawl khi chưa có snapshot.

Loopback hosts và CORS allowlist; mutations POST cần Origin hợp lệ nếu có và X-CSRF-Token từ GET /api/session. Upload cần Content-Length (cap 128 KB); OAuth JSON tối đa 64 KB, chỉ Desktop config/Google HTTPS endpoints. GET exports không mutate. Sort allowlist, parameterized search, spreadsheet formula escaping, responses/logs không chứa token; callback query auth code được che. Không phục vụ thư mục data/credentials qua HTTP.

## Recovery và giới hạn

Restart chuyển abandoned queued/running thành partial, có thể tiếp tục. Initial/incremental bỏ qua finalized history và refresh 7 ngày gần nhất; refresh toàn kỳ có semantics retry rõ. Quota/auth/network failures giữ data cũ. Nếu disk không ghi được trạng thái lỗi, process hiển thị failure và restart recovery xử lý sau khi sửa quyền/dung lượng.

Một Google connection và nhiều exact properties; web/image/video/news riêng biệt. Chưa có Discover/Google News feed, query–page sync, GA4, backlinks, AI hoặc multi-user auth. Crawler Technical SEO Core đã triển khai; URL Inspection, rendering, CWV, log analysis và advanced diagnostics còn chưa thực hiện. Live OAuth, Windows keyring thực tế và API sync thật còn Pending Live Verification. Xem docs/GOOGLE_GSC_SETUP.md, docs/DATA_SYNC.md, docs/DATA_MODEL.md và docs/TROUBLESHOOTING.md.
