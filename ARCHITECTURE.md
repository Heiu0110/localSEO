# Architecture · SEO Local Workspace v0.1

## Luồng dữ liệu

`MockProvider → DashboardService → FastAPI/Pydantic → REST → TanStack Query → React components`

Ứng dụng gồm hai tiến trình local độc lập. Vite chỉ proxy `/api` tới loopback backend. Không có cloud deployment, database, login hay request đến website demo. Backend không phục vụ static frontend trong v0.1.

## Nguồn sự thật và phép tổng hợp

`MockProvider` tạo một fixture có seed cố định cho từng site. Grain của fact là **date × page × query × country**. Mỗi observation có clicks nguyên không âm, impressions nguyên không âm và position. 200 ngày từ **04/04/2026 đến 20/10/2026** bao phủ cả 90 ngày hiện tại và 90 ngày trước. Dataset có weekday seasonality, giai đoạn giảm và tăng trưởng; hai site có quy mô và trend riêng. Timestamp “last updated” là giá trị mock cố định và luôn ghi nhãn.

Mỗi website có 12 pages, 16 queries, 5 countries. Mọi observation liên kết với một URL/query/country cụ thể. Các dimension response mang `coverage: complete`; tổng clicks/impressions của pages, queries, countries và daily series phải khớp overview. Page details chỉ lọc facts của page đó, nên related queries và chuỗi ngày cũng đối chiếu được.

- `clicks = sum(clicks)`
- `impressions = sum(impressions)`
- `ctr = sum(clicks) / sum(impressions) × 100`
- `position = sum(position × impressions) / sum(impressions)`
- Khi không có impressions, CTR/position = 0, không NaN/Infinity.
- Phần trăm thay đổi `(current − previous) / previous × 100`; baseline = 0 trả `null` và UI ghi “No prior data”/“—”.
- UI dùng delta **percentage points** cho CTR, **places** cho position. Position giảm được đánh dấu tốt, có tooltip nhắc ảnh hưởng của query mix.
- Giữ độ chính xác trong service/API; chỉ làm tròn ở UI hoặc file CSV (4 chữ số thập phân).

Khoảng hiện tại kết thúc ở ngày cuối fixture, bao gồm hai đầu mút. Khoảng trước là N ngày liền trước đó. Performance response gắn `previous_date` với từng điểm để so sánh theo offset; không giả vờ hai kỳ có cùng ngày. Metric selector giữ từng đơn vị trên trục riêng theo lựa chọn; không overlay clicks/impressions/CTR/position trên một Y axis.

## Ranh giới module

- `providers/base.py`: `DataProvider` Protocol và immutable Observation. Không phụ thuộc FastAPI.
- `providers/mock_provider.py`: tất cả định nghĩa synthetic fixture, site/page/query labels.
- `services/dashboard_service.py`: aggregation, period windows, partitions, page detail. Không chứa HTTP routing hoặc UI formatting. Provider được tái sử dụng trong process qua dependency cache.
- `models.py`: schema response cụ thể, số liệu có đơn vị trong mô tả.
- `api/routes.py`: endpoint mỏng, site ID validation, enum ngày 7/28/90. Main chuyển lỗi không tồn tại thành 404; validation thành 422 qua FastAPI.
- Frontend `services/`: typed fetch, cancellation theo AbortSignal, API errors, query keys theo `(report, site, days)`. Cache 5 phút; retry lỗi tạm thời, không retry 4xx cho các report.
- `DashboardPage`: website/date URL state, query orchestration. Chờ đủ cùng context rồi render report; không trộn overview cũ với bảng mới khi đổi filter. Các query độc lập, data sources lỗi riêng không che số liệu performance.
- `components/dashboard`: display và UI state: chọn metric, search/sort/pagination, panel. KPI và report data luôn tới từ API, không tạo số liệu trong React.
- `components/ui`: các primitives có thể tái sử dụng; Radix cung cấp keyboard/focus behavior cho Sheet và Tooltip.

Không thêm Redux, event bus, repository layer, hàng đợi job hoặc service rỗng cho các module tương lai. Search/sort/pagination chạy client vì fixture đầy đủ chỉ 12/16 dòng. Khi dữ liệu lớn, chuyển query/filter/pagination sang server và khai báo coverage/top-N trong contract.

## API contract

Swagger `/docs`, OpenAPI `/openapi.json` là contract backend. TypeScript mirror tại `frontend/src/types/api.ts`; khi sửa schema, phải sửa mirror và chạy cả API/browser tests. JSON dùng ISO date `YYYY-MM-DD`, timestamp có timezone, CTR/share phần trăm 0–100 (không dùng fraction 0–1).

| Endpoint GET | Response |
|---|---|
| `/api/health` | Health (`ok`, provider `mock`, version) |
| `/api/sites` | Site[] |
| `/api/dashboard/overview` | Overview (current, previous, changes, periods, provenance) |
| `/api/dashboard/performance` | Performance (aligned daily points) |
| `/api/dashboard/pages` | DimensionReport (complete pages) |
| `/api/dashboard/queries` | DimensionReport (complete queries) |
| `/api/dashboard/countries` | CountryReport (click share) |
| `/api/dashboard/pages/{page_id}` | PageDetail (URL, metrics, timeseries, related queries) |
| `/api/dashboard/sources` | DataSource[] |

Report endpoints nhận `site_id` bắt buộc, `days` mặc định 28, chỉ chấp nhận 7/28/90. 404 cho site/page không có, 422 cho query parameters không hợp lệ. CORS chỉ cho `http://127.0.0.1:5173` và `http://localhost:5173`, phương thức GET. Runner bind loopback; không yêu cầu secrets.

## State, CSV và offline

Server state qua TanStack Query; local UI state qua React; website/date qua URL. Đổi site/date tạo context mới, đóng details và reset table filters để tránh xem nhầm page cùng ID của site khác. Sidebar preference qua localStorage với fallback khi storage không khả dụng. Table search/sort chỉ thay views, không mutate API data.

CSV được tạo từ các rows đã lọc/sắp xếp của report hiện tại, trước pagination; UTF-8 BOM, CRLF, quote/escape double quotes. Chỉ text không tin cậy có thể bị thêm apostrophe để chống spreadsheet formula injection; số âm vẫn là numeric. Tên file có site, start/end và tiền tố mock. Export không phụ thuộc dịch vụ ngoài.

Sau cài dependencies, runtime không cần Internet. Không có external fonts, CDNs, telemetry hoặc third-party scripts. Start helpers lưu fingerprint và bỏ qua cài đặt nếu lock không thay đổi. Snapshot filesystem giữ dependencies; process phải được chạy lại ở lần mở workspace tiếp theo.

## Chuyển sang GSC/SQLite ở v0.2

Provider abstraction hiện tại mô tả **complete synthetic facts**. GSC có giới hạn row, privacy/anonymized queries và semantics aggregation riêng; không được coi page/query/country reports là các phân hoạch đầy đủ rồi cộng tùy ý. Provider thật cần giữ site-level totals và dimension reports đúng aggregation type, khai báo coverage/freshness, kiểm tra cách weighted position được trả về. Có thể mở rộng provider thành report-level methods lúc tích hợp thực tế; không ép GSC trả một full fact cube không tồn tại.

SQLite lưu raw responses/normalized records, property identity, aggregation scope, sync watermark và migrations; incremental sync phải xử lý reprocessing các ngày chưa finalized. OAuth credentials chỉ ở backend/local secure settings, không đưa vào frontend build. Các module khác vẫn placeholder cho tới khi có implementation và validation thật.
