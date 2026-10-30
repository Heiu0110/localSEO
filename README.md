# SEO Local Workspace · v0.8 Core · AI Visibility & GEO

Ứng dụng phân tích SEO chạy local cho một người dùng: React Dashboard + FastAPI + SQLite. Dashboard giữ Mock Provider, GSC dùng SQLite Analytics Provider riêng; Technical SEO có crawler chỉ đọc và audit snapshots độc lập. Có bộ thử nghiệm ngoại tuyến để kiểm tra từng luồng mà không cần Google hoặc crawl domain thật. Không có login ứng dụng, Docker hoặc cloud deployment; không tự truy cập các domain demo.

## Phase 8: AI Visibility & GEO Opportunity Finder

Mở **AI Visibility** ở sidebar: tạo project gắn website → khai báo brand/đối thủ/domain → Prompt Library → nhập quan sát AI hoặc preview/import JSON/CSV → đọc mention/citation theo cohort → phát hiện GEO opportunities → xem evidence và human review. Phân tích ngoại tuyến không cần API key; phân tích sâu tái sử dụng AI Workspace với consent/model/ngân sách hiện có.

Migration `006_ai_visibility` thêm 15 bảng, tự chạy khi khởi động backend; không reset SQLite hoặc sửa totals GSC. Không có dependency mới. Sao lưu SQLite trước nâng cấp, giữ cả credential vault của máy. Dashboard demo và dữ liệu GSC thực tiếp tục tách riêng.

Chỉ đo tập quan sát được nhập: **mention ≠ citation ≠ recommendation**, Unknown citation không phải zero. Các provider/model/locale/grounding/branded cohorts được giữ riêng. Core không có live collector, scheduler, tự crawl citation hoặc publishing. ChatGPT auth tiếp tục **Pending Live Verification**, không cần login để dùng Core.

Xem [hướng dẫn từng bước](docs/AI_VISIBILITY_USER_GUIDE.md), [metrics](docs/AI_VISIBILITY_METRICS.md), [9 rule GEO](docs/GEO_OPPORTUNITY_ENGINE.md), [verifier/accuracy](docs/GEO_EVIDENCE_VERIFICATION.md), [giới hạn](docs/AI_VISIBILITY_LIMITATIONS.md) và [báo cáo nghiệm thu](docs/PHASE8_COMPLETION_REPORT.md).

## Hướng dẫn chạy trên Windows 10/11

### 1. Chuẩn bị

Cài **Python 3.11+** (chọn “Add Python to PATH”) và **Node.js 24 LTS** kèm npm (tối thiểu Node 22.12). Cài thêm Git nếu muốn tải/cập nhật bằng lệnh Git. Sau khi cài, mở terminal PowerShell mới và kiểm tra:

```powershell
python --version
node --version
npm --version
```

Nếu máy dùng Python Launcher, thay `python --version` bằng `py -3 --version`. Lần cài dependency đầu tiên cần Internet; những lần sau script dùng lại thư viện đã cài hợp lệ.

### 2. Mở thư mục dự án

Nếu chưa có mã nguồn, chạy:

```powershell
git clone https://github.com/Heiu0110/localSEO.git
cd localSEO
```

Nếu đã có project, mở thư mục đó trong VS Code rồi chọn **Terminal → New Terminal**. Thư mục hiện tại cần chứa `README.md`, `run-backend.bat`, `run-frontend.bat`, `backend/` và `frontend/`. Nếu tải ZIP từ GitHub, giải nén trước; tên thư mục có thể là `localSEO-main`.

### 3. Chạy backend và frontend ở hai terminal riêng

**Terminal 1 — backend**, chạy từ thư mục gốc:

```powershell
.\run-backend.bat
```

Chờ log `Application startup complete.` và giữ terminal này mở. Script tự tạo `backend/.venv`, cài requirements khi cần và cập nhật schema SQLite.

**Terminal 2 — frontend**, mở terminal mới tại cùng thư mục gốc:

```powershell
.\run-frontend.bat
```

Chờ Vite hiện `Local: http://127.0.0.1:5173/`, rồi mở địa chỉ đó trên trình duyệt. Giữ cả hai terminal mở trong lúc dùng ứng dụng. Cũng có thể double-click hai file `.bat` trong File Explorer.

| Địa chỉ | Mục đích |
|---|---|
| http://127.0.0.1:5173 | Giao diện ứng dụng |
| http://127.0.0.1:8000/api/health | Kiểm tra backend; phản hồi có `status: "ok"` |
| http://127.0.0.1:8000/docs | Tài liệu và thử API |

Backend không có trang tại `http://127.0.0.1:8000/`. Vite proxy `/api` sang backend; **không cần tạo `.env` để chạy mặc định**. Hai server chỉ bind `127.0.0.1`.

**Dừng ứng dụng:** nhấn `Ctrl+C` trong cả hai terminal, xác nhận `Y` nếu Windows hỏi dừng batch job. Lần chạy tiếp theo chỉ cần thực hiện lại bước 3, không cần clone hoặc chạy `npm ci` mỗi lần.

### 4. Sử dụng ngay sau khi mở app

- **Tổng quan:** chọn website `[DEMO]` để xem giao diện và báo cáo mẫu.
- **AI Workspace:** chọn website, nhập “Phân tích hiệu suất SEO 28 ngày gần nhất”, chọn **Báo cáo ngoại tuyến** rồi gửi. Chế độ này đọc dữ liệu đã lưu theo quy tắc, không phải LLM và không cần API key.
- **Technical SEO:** tạo dự án hoặc bộ thử nghiệm để xem URL, findings và bằng chứng.
- **Theo dõi từ khóa:** tạo bộ từ khóa, nhập rank thủ công hoặc import dữ liệu.
- **Keyword Research:** mở link tại Theo dõi từ khóa → tạo dự án → nhập seed/GSC/tệp → phân nhóm/review → nhập SERP đã quan sát. Chuyển keyword đã duyệt sang Tracking có bước xem trước/xác nhận riêng.
- **Dữ liệu GSC thật:** vào **Cài đặt → Tích hợp Google Search Console**, làm theo [hướng dẫn OAuth](docs/GOOGLE_GSC_SETUP.md), thêm property và đồng bộ.

Demo/bộ thử nghiệm dùng được khi chưa cấu hình Google hoặc OpenAI. Sau khi cài đủ dependency, các báo cáo đã lưu và API docs dùng được ngoại tuyến; đồng bộ Google, crawl website và gọi AI cloud cần Internet.

### 5. Sign in with ChatGPT / ChatGPT Plan Usage (tùy chọn)

Vào **AI Workspace → AI Settings → ChatGPT Connection → Continue with ChatGPT**. Luồng open-source/locally hosted dùng dynamic registration, không cần Client ID cấp trước hoặc API key. Token lưu trong OS Credential Vault; chỉ model `visibility=list` của tài khoản được chọn. Chạy trình duyệt và backend trên cùng máy tại localhost/127.0.0.1.

**Pending Live Verification:** LocalSEO chưa được xác nhận eligibility; repo chưa có LICENSE ở thư mục gốc. Người sở hữu cần rà soát điều kiện và quyền sử dụng mã nguồn trước khi chọn các checkbox xác nhận. App không tự công bố license. Đăng nhập thiếu `chatgpt.tokens.use.direct` sẽ bị chặn Plan Usage; app không bịa hạn mức còn lại hoặc tự chuyển API trả phí khi bị giới hạn. Full Preview Limitations chưa được đối chiếu độc lập do docs bị Tunnel403; contract triển khai theo handoff người dùng cung cấp ngày29/10/2026.

Sau khi được cấp quyền: chọn/lưu model ChatGPT → về chat chọn **ChatGPT · Plan Usage** → kiểm tra quyền/model và xác nhận gửi dữ liệu cho lượt này. Responses dùng streaming; kết quả chỉ hoàn tất sau `response.completed` và kiểm tra evidence. Xem [hướng dẫn & bước xác minh localhost](docs/CHATGPT_CONNECTION_SETUP.md) và [kiến trúc/bảo mật](docs/CHATGPT_CONNECTION_ARCHITECTURE.md). Chưa thực hiện login/inference thật trong cloud.

### 6. Bật OpenAI API Key Provider (tùy chọn)

Sau khi backend đã tạo môi trường ảo, mở terminal thứ ba tại thư mục gốc:

```powershell
.\backend\.venv\Scripts\python.exe scripts\configure_ai_provider.py
```

Nhập key tại prompt ẩn. Sau đó mở **AI Workspace → AI Settings**, làm mới trạng thái key, cấu hình model/giá/ngân sách, kiểm tra key/model và bật OpenAI. Khi chat, chọn OpenAI, xem ước tính rồi xác nhận gửi dữ liệu/chi phí.

Key lưu trong kho khóa hệ điều hành, không nhập vào frontend hoặc chat. OpenAI có thể tính phí theo tài khoản API riêng; quyền sử dụng Codex không tự cấp API cho app. Xem [hướng dẫn provider](docs/AI_PROVIDER_SETUP.md) về cấu hình, giới hạn và các bước live verification còn chờ xác minh.

## Cập nhật phiên bản và giữ dữ liệu

Dừng cả hai server bằng `Ctrl+C`. Nếu project được clone bằng Git, chạy tại thư mục gốc trong PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe scripts\backup_database.py
```

Lệnh backup dùng môi trường Python đã tạo khi chạy backend; chỉ chạy khi database đã tồn tại. Với cấu hình mặc định, bản sao được lưu tại `backend/data/backups/` và đường dẫn sẽ được in ra terminal. Sau khi backup báo thành công, cập nhật mã nguồn:

```powershell
git pull origin main
```

Sau khi cập nhật, chạy lại `run-backend.bat` và `run-frontend.bat` ở hai terminal. Backend tự migrate schema. Frontend dùng lại `node_modules` khi dependency không đổi, kể cả khi chỉ tăng version app; chỉ cài lại khi cần.

Dữ liệu mặc định nằm ở `backend/data/seo_workspace.db`; giữ nguyên thư mục `backend/data/`. Nếu tải source bằng ZIP thì không dùng được `git pull`: giữ bản project cũ và backup, cập nhật các file mã nguồn vào thư mục đang dùng, giữ dữ liệu local. Không copy `.venv` hoặc `node_modules` giữa Windows/Linux; để launcher chuẩn bị theo hệ điều hành.

## Khi frontend chuẩn bị lâu hoặc không mở được app

Bước cài thư viện (`npm`) và bước chạy Vite là hai bước riêng. Khi đã hiện `VITE ... ready` cùng địa chỉ `5173`, frontend đã sẵn sàng; terminal tiếp tục chạy để phục vụ app.

| Vấn đề | Cách xử lý |
|---|---|
| Không tìm thấy Python/Node/npm | Cài runtime, mở terminal mới; kiểm tra các lệnh version ở bước 1. |
| Frontend đang “cài thư viện” | Xem log `npm http`/`npm ERR` và kết nối tới `registry.npmjs.org`. Lần cài đầu được phép tối đa **600 giây (10 phút)**; những lần sau dùng lại dependency hợp lệ. Xem [chẩn đoán chi tiết](docs/TROUBLESHOOTING.md#frontend-khởi-động-lâu). |
| Đã hiện `added … packages` rồi launcher cũ báo quá 180 giây | Cập nhật code rồi chạy lại `.\run-frontend.bat` trong **cùng thư mục**, giữ `frontend/node_modules`. Launcher kiểm tra bản cài hoàn chỉnh để dùng lại; không cần chạy `--repair` trước. |
| Mạng chậm hơn 10 phút nhưng vẫn đang tải gói | Dừng frontend rồi chạy `.\run-frontend.bat --install-timeout=1200` để cho phép tối đa 20 phút cho lượt cài đó. Thời gian này không áp dụng cho những lần chỉ dùng lại thư viện. |
| Bản cài frontend bị hỏng | Dừng frontend rồi chạy `.\run-frontend.bat --repair`; tùy chọn này chủ động cài lại, không cần dùng mỗi lần. |
| Giao diện báo không gọi được API hoặc proxy 500 | Kiểm tra backend đã hiện `Application startup complete.` và mở `/api/health`; xem lỗi tại terminal backend rồi bấm **Thử lại** trong app. |
| Port 8000 hoặc 5173 đã được dùng | Dừng terminal ứng dụng cũ rồi chạy lại. Vite dùng strict port để giữ đúng cấu hình kết nối. |
| Môi trường ảo bị xóa một phần | Dừng backend, xóa riêng `backend/.venv` rồi chạy lại `run-backend.bat`; giữ nguyên `backend/data/`. |
| Đã đổi cấu hình `.env` nhưng chưa có tác dụng | Khởi động lại Vite. Cấu hình frontend tùy chỉnh đặt ở `frontend/.env.local`; chạy mặc định không cần file này. |
| Ngày dữ liệu demo không theo hôm nay | Demo có 200 ngày cố định, kết thúc **20/10/2026**; báo cáo tính từ ngày cuối fixture. |

## Chạy trên Linux/macOS

Tại thư mục gốc, mở hai terminal riêng. Terminal backend:

```bash
python3 scripts/backend.py --run
```

Terminal frontend:

```bash
node scripts/frontend.mjs --run
```

Mở http://127.0.0.1:5173 và giữ cả hai terminal chạy. Dùng `python` nếu máy không có lệnh `python3`. Có thể chỉ chuẩn bị dependency bằng cách bỏ `--run`. Cấu hình OpenAI dùng `backend/.venv/bin/python scripts/configure_ai_provider.py` và cần OS keyring khả dụng.

## v0.7 Core: Keyword Research & SERP Intelligence

Research Workspace tại `/keyword-research` bổ sung project theo website, seed/GSC/Tracking/crawl title và CSV/XLSX/JSON; Keyword Explorer có provenance và metric units/kỳ riêng; intent/group/cluster/review; manual/lexical/SERP-overlap clustering; immutable imported SERP snapshots, so sánh theo profile, domain cohorts và cơ hội có bằng chứng. Chỉ chuyển keyword đã duyệt vào bộ Tracking cùng website qua preview/confirmation; mặc định bỏ qua trùng, không sửa lịch sử rank.

Migration005 thêm10bảng Research, giữ dữ liệu cũ. Agent Phase6 có thêm7tools read-only (tổng20), không có tool tự discovery/approve/transfer. GSC impressions không phải search volume, Ads competition không phải organic difficulty, SERP observed position không phải GSC Average Position hoặc rank MANUAL. Topical Map vẫn chưa triển khai.

**Không cần provider trả phí để dùng Core.** Google Ads/SERP API/Trends live, AI clustering nâng cao, scheduled research và publishing chưa triển khai. Dữ liệu người dùng nhập được gắn nguồn, không được mô tả là live-verified.

Tài liệu: [Hướng dẫn Research](docs/KEYWORD_RESEARCH_USER_GUIDE.md) · [Kiến trúc](docs/KEYWORD_RESEARCH_ARCHITECTURE.md) · [Dữ liệu & import](docs/KEYWORD_RESEARCH_DATA_MODEL.md) · [Clustering](docs/KEYWORD_CLUSTERING.md) · [SERP](docs/SERP_INTELLIGENCE.md) · [Providers](docs/KEYWORD_RESEARCH_PROVIDERS.md) · [Agent integration](docs/KEYWORD_RESEARCH_AI_INTEGRATION.md) · [Giới hạn](docs/KEYWORD_RESEARCH_LIMITATIONS.md).

## Phase 6: AI Workspace

AI Analyst chỉ đọc dữ liệu hiện có, không tự thực hiện hành động SEO:

- Hội thoại theo website, lịch sử/lưu phiên, kỳ báo cáo và URL được giữ khi hỏi tiếp.
- Tool registry gồm 20 tool chỉ đọc, tái sử dụng GSC, Technical SEO và Keyword Tracking; không có SQL/shell/file hoặc external write tool.
- Metric cards/bảng từ backend, bằng chứng có nguồn/kỳ/freshness/completeness và liên kết báo cáo; diễn giải/giả thuyết tách riêng.
- Đề xuất có review/ghi chú; Approved chỉ lưu trạng thái, không tạo Technical backlog hoặc publishing.
- Mặc định báo cáo theo quy tắc ngoại tuyến, ghi rõ không phải LLM. OpenAI là tùy chọn riêng, key OS keyring nhập qua terminal, có consent và ước tính/budget mỗi lượt.
- Có token usage, dự phòng chi phí chưa rõ, idempotency và giới hạn tool/context/response; không gọi AI nền khi chỉ mở báo cáo.

Topical Map chưa có triển khai trong repo nên Agent báo thiếu nguồn, không tạo mapping giả. Phase7 Core đã bổ sung Research; các Phase8–11 còn trong roadmap. Không có live API verification/giá hiện hành được ngầm bảo đảm: model ID được đối chiếu SDK chính thức, trang giá bị chặn truy cập trong môi trường triển khai, nên app để giá trống và yêu cầu người dùng xác minh/nhập ước tính trước khi bật OpenAI.

Bắt đầu ngay: **AI Workspace → chọn website → hỏi bằng Báo cáo ngoại tuyến**. Muốn OpenAI, xem [cấu hình provider](docs/AI_PROVIDER_SETUP.md); không gửi API key trong chat hoặc frontend.

Tài liệu: [Hướng dẫn](docs/AI_AGENT_USER_GUIDE.md) · [Kiến trúc](docs/AI_AGENT_ARCHITECTURE.md) · [Tools](docs/AI_AGENT_TOOLS.md) · [Evidence](docs/AI_AGENT_EVIDENCE.md) · [Security](docs/AI_AGENT_SECURITY.md) · [Roadmap](docs/AI_AGENT_ROADMAP.md).

## v0.4 Core: Theo dõi từ khóa

Keyword Tracking đã thay placeholder bằng bảng làm việc 35 tuần, dùng SQLite và UI tiếng Việt hiện tại:

- Bộ từ khóa, nhóm/màu, URL đích, Search Profile, ưu tiên, ghi chú, archive, chuyển bộ cùng lịch và xóa có xác nhận.
- Sáu cột cố định trên desktop, filter/sort/phân trang phía server, nhập inline/NA/clear, dán khối và sửa metadata hàng loạt.
- Lịch tuần theo ngày bắt đầu + timezone; observation giữ snapshot và lịch sử sửa. Rank số, NA và chưa kiểm tra tách biệt; không ghi GSC Average Position vào rank.
- Tổng quan, biến động tuần liền trước, biểu đồ đảo trục và drawer; checklist kiểm tra thủ công kèm shortcut Google.
- Sync exact query qua OAuth hiện có; property scope/page scope, kỳ GSC độc lập, queue/cache và trạng thái thiếu dữ liệu rõ ràng.
- CSV/XLSX preview, ánh xạ, lỗi/trùng, xác nhận commit, xuất đủ 35 tuần và bảo vệ formula injection. Metric bảng tính không được giả làm GSC live.
- Thẻ Dashboard nhỏ khi có bộ theo dõi; mở bằng chứng URL Technical SEO đã lưu, không tự crawl.

Bắt đầu: chạy hai launchers → **Theo dõi từ khóa → chọn Website → Bộ từ khóa mới**. Không cần Google để nhập rank/import. Live GSC dùng Settings như trước. Chưa có automatic SERP, scheduled checks hoặc screenshot evidence.

Tài liệu: [Hướng dẫn sử dụng](docs/KEYWORD_TRACKING_USER_GUIDE.md) · [Kiến trúc](docs/KEYWORD_TRACKING_ARCHITECTURE.md) · [Dữ liệu](docs/KEYWORD_TRACKING_DATA_MODEL.md) · [Nhập/xuất](docs/KEYWORD_TRACKING_IMPORT_EXPORT.md) · [GSC](docs/KEYWORD_TRACKING_GSC_INTEGRATION.md) · [Quy tắc rank](docs/KEYWORD_TRACKING_RANK_RULES.md).

## v0.3 Core: Technical SEO

Vào **Technical SEO → Dự án mới**, nhập website, chọn giới hạn/tốc độ/scope rồi bắt đầu audit. Không cần Google OAuth. Có robots/sitemap, HTTP/redirect diagnostics, metadata/canonical/noindex, observed link graph/depth, Issue Explorer với evidence/confidence, URL Inventory, backlog có ghi chú và xác minh, lịch sử/so sánh, CSV/JSON/printable HTML. Dữ liệu cũ vẫn đọc offline. Dùng **Tạo bộ thử nghiệm Technical SEO** để kiểm tra cùng engine với HTTP fixtures được gắn nhãn rõ.

Crawler chặn SSRF/private IP, pin DNS tại socket, kiểm tra scope/robots tại redirect, giới hạn request/body/discovery và không thực hiện hành động sửa website. Local indexability không phải Google index; không có SEO health score. Hiện có 39 rule sinh finding trong 63 capability automated (gồm thu thập tín hiệu/workflow); catalog toàn master 138 checks thể hiện rõ phần chưa khả dụng. URL Inspection/rendering/CWV/logs chưa triển khai trong Core.

Nâng cấp: dừng server, backup bằng `python scripts/backup_database.py`, lấy source mới rồi chạy lại hai `.bat`. Migration `002_technical_audits` bổ sung bảng, không xóa dữ liệu GSC. Task bị gián đoạn giữ checkpoint; chạy lại tạo snapshot mới.

- [Hướng dẫn audit và CSV](docs/TECHNICAL_AUDIT_USER_GUIDE.md)
- [Kiến trúc module](docs/TECHNICAL_SEO_ARCHITECTURE.md)
- [Crawler, scope, robots và limits](docs/TECHNICAL_CRAWLER.md)
- [Rule catalog và cách đọc bằng chứng](docs/TECHNICAL_RULES.md)
- [Data model, history và retention](docs/TECHNICAL_DATA_MODEL.md)
- [Giới hạn và tích hợp chưa thực hiện](docs/TECHNICAL_LIMITATIONS.md)


## v0.2: Google Search Console và SQLite

1. **Cài đặt → Tích hợp Google Search Console**: nhập Desktop OAuth JSON, kết nối Google, làm mới properties và thêm property vào workspace. Token ở kho khóa hệ điều hành; không vào SQLite/browser.
2. Chọn property và lịch sử 28/90/180 ngày hoặc tối đa khoảng 16 tháng; xem khối lượng ước tính rồi nhấn **Bắt đầu đồng bộ**. Có initial, incremental (refresh 7 ngày gần nhất), manual refresh, hủy và tiếp tục job.
3. **Phân tích GSC**: Tổng quan, URL, Truy vấn, Quốc gia, Thiết bị; lọc ngày/search type, so sánh kỳ bằng nhau, tìm kiếm/sort/server pagination và CSV mọi dòng đã lưu khớp bộ lọc.
4. **Tổng quan**: chọn `[DEMO]`, `[THỬ NGHIỆM SQLITE]` hoặc `[GSC]`. Website/ngày vẫn lưu qua URL; không fallback sang demo khi property thật chưa có dữ liệu.

KPI chỉ dùng site dataset **byProperty**. Page dataset **byPage**, queries/countries/devices là các tập độc lập; không ép tổng chi tiết khớp tổng property. Ngày thiếu là khoảng trống `null`, không phải 0. Kỳ thiếu hoặc chưa có lịch sử có cảnh báo, không dựng phần trăm so sánh giả. Bảng real trong Dashboard là Top 100 đã lưu; Phân tích GSC có pagination/export đầy đủ **dữ liệu SQLite**, vẫn không bảo đảm mọi dòng Google đã bị ẩn/lọc/giới hạn.

Không cần OAuth để kiểm thử: **Cài đặt → Tạo bộ thử nghiệm SQLite**, thêm property `.example`, chọn lịch sử và Sync. Fixture dùng cùng engine sync/database/API, luôn ghi nhãn thử nghiệm, riêng với hai demo v0.1. Sau cài dependency, báo cáo cached/demo và API docs chạy offline; kết nối/lấy dữ liệu mới cần Internet.

SQLite mặc định ở `backend/data/seo_workspace.db`, Git ignore. Migrations Alembic tự chạy khi startup. Backup nhất quán kể cả WAL: `python scripts/backup_database.py`. Không có API xóa lịch sử; bỏ property khỏi workspace chỉ ẩn nó.

- [Hướng dẫn Google Cloud và Desktop OAuth](docs/GOOGLE_GSC_SETUP.md)
- [Đồng bộ, retry, checkpoint và giới hạn dữ liệu](docs/DATA_SYNC.md)
- [Schema, migration, backup/restore](docs/DATA_MODEL.md)
- [Xử lý lỗi](docs/TROUBLESHOOTING.md)

**Nâng cấp từ v0.1:** dừng cả hai server, lấy source mới, chạy lại hai `.bat`. Bootstrap cập nhật dependencies khi lock thay đổi và migrate SQLite. Mock dataset và theme giữ nguyên. Với database v0.2 đã có, backup trước lần nâng cấp tiếp theo. Không sửa mã nguồn để kết nối Google.

**Pending Live Verification:** các kiểm thử tự động không dùng credentials thật hoặc quota Google. Bạn cần thực hiện OAuth/live sync trên cùng máy Windows với trình duyệt, không dùng loopback của cloud container. Tệp credentials được nhập qua UI, không dán token vào chat.

## Dashboard được giữ từ v0.1

- Giao diện tiếng Việt, giữ tên sản phẩm và thuật ngữ SEO phù hợp. Bảng màu theo ảnh tham chiếu mới: trắng–xám–bạc–đen, khung kính mờ trên nền đá, sidebar sáng với mục chọn màu đen, thẻ bo tròn và nút dạng pill. CSS variables dùng chung cho các module, gồm Dashboard, Settings, Technical SEO, Keyword Research và AI Workspace; nền WebP được đóng gói cục bộ, không cần CDN. Số hiển thị theo `vi-VN`, ngày `dd/mm/yyyy`; dữ liệu API và giá trị số trong CSV giữ định dạng máy đọc được.
- Hai website minh họa: `xuongmaybalogiare.com` và `congtymaybalotuixach.com`.
- Báo cáo 7/28/90 ngày; kỳ liền trước có cùng số ngày, không chồng lấn. Website/ngày lưu trong URL để refresh hoặc bookmark.
- Clicks, impressions, CTR, position, so sánh và sparkline từ cùng dataset.
- Biểu đồ chọn từng metric với đúng đơn vị, bật/tắt current/prior series, tooltip hiển thị đúng ngày của mỗi kỳ.
- 12 URL, 16 queries mỗi website: tìm kiếm, sort 4 metric, phân trang/chọn số dòng.
- Click URL mở panel KPI, biểu đồ daily clicks và queries liên quan. Click query xem chỉ số của query.
- CSV Pages chứa **tất cả dòng khớp tìm kiếm theo thứ tự sort**, không chỉ trang đang hiển thị. Tên file chứa site và kỳ báo cáo. UTF-8 BOM hỗ trợ Excel, quote theo CSV và chặn formula injection trong text.
- Country performance 5 quốc gia, tổng clicks/impressions đối chiếu được với tổng website.
- Data Sources ghi rõ trạng thái thực tế. Sidebar thu gọn lưu ở local storage.
- Loading skeleton, empty state, error/retry, keyboard navigation, tooltip và panel có focus trap/Escape.
- Responsive: bảng cuộn riêng khi cần, không làm trang tràn ngang.
- Technical SEO đã có module audit v0.3 Core. Keyword Tracking đã có v0.4 Core. Topical Map, Internal Links độc lập và SEO Reports vẫn là placeholder; link graph trong Technical SEO hoạt động riêng. Settings và Phân tích GSC giữ luồng v0.2.

## Kiểm thử

Backend, từ `backend/`:

```bash
# Windows
.venv\Scripts\python.exe -m pytest -q
# Linux/macOS
.venv/bin/python -m pytest -q
```

Frontend, từ `frontend/`:

```bash
npm run typecheck
npm run build
# Chỉ lần đầu cần tải browser cho automated tests:
npx playwright install chromium
npm run test:e2e
```

Playwright tự khởi động hai server khi chưa có server. Python cần có trên PATH, hoặc khởi động backend bằng script trước khi test. Linux có Chromium sẵn có thể đặt `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium`; trên Windows dùng browser Playwright đã cài. Dừng dev servers trước khi chạy với `CI=1`. Dữ liệu mock không bị mutate nên các browser tests chạy song song an toàn.

`npm run preview` phục vụ bản build tại port 5173, vẫn cần backend. Bản build không chứa backend và không phải file HTML có thể mở trực tiếp bằng `file://`.

### Kết quả xác minh

Xem [VALIDATION.md](VALIDATION.md) để biết các lệnh và kết quả chạy thực tế. Test bao gồm CTR/weighted position, kỳ hiện tại/trước đó, consistency của toàn bộ dimension cho cả 2 site × 3 khoảng ngày, API validation/404/CORS; browser tests kiểm tra API→UI, bảng, panel, CSV, lỗi/retry, offline resources và responsive.

## Cấu trúc

```text
backend/
  app/api/routes.py             REST endpoints và validation
  app/models.py                 Pydantic response contracts
  app/providers/                MockProvider + SQLiteAnalyticsProvider
  app/gsc/                      Desktop OAuth, OS vault, Google/fixture clients, sync queue
  app/technical/                Safe crawler, extraction, graph, rules, persistent audits/reports
  app/keywords/                 Keyword sets, rank history, import/export và GSC cache
  app/ai/                       Agent, read-only tools, evidence và provider/cost controls
  app/research/                 Research projects, keyword sources/metrics, SERP, clusters/review/transfer
  app/db/                       SQLite engine và SQLAlchemy models
  migrations/                   Alembic schema revisions
  app/services/                 Aggregation và reporting
  tests/                        API + consistency tests
frontend/
  src/app/                      Query provider, router
  src/components/layout/        Sidebar, shell
  src/components/dashboard/     KPI/chart/table/panel/country/sources
  src/components/ui/            shadcn-style owned primitives (Radix + CVA)
  src/features/dashboard/       Report orchestration + CSV utility
  src/features/settings/        OAuth, property membership và đồng bộ
  src/features/gsc/             GSC Analytics, coverage và server reports
  src/features/technical/       Audit form, explorers, history, backlog và evidence panels
  src/features/keywords/        Keyword Tracking và bảng rank theo tuần
  src/features/ai/              Chat, nguồn dữ liệu, evidence, review và AI Settings
  src/features/research/        Keyword Research và SERP Intelligence
  src/services/                 Typed REST client + TanStack Query options
  src/types/                    TypeScript response contracts
  src/styles/                   Tailwind CSS 4 + theme/component styles
  tests/                        Playwright browser acceptance tests
scripts/                        Cross-platform bootstrap/runners
run-backend.bat                  Windows launcher
run-frontend.bat                 Windows launcher
```

## Quyết định về dependency và giới hạn

React 19, React Router 7 (declarative data router), Vite 7, TypeScript 5.9, Tailwind CSS 4 qua plugin Vite, TanStack Query 5 và Recharts 3. Tailwind 4 không cần `tailwind.config.js` kiểu v3. Button, Sheet và Tooltip theo cấu trúc shadcn/ui với code được sở hữu trong repo, dùng Radix cho dialog/focus/tooltip; không thêm một UI kit runtime khác. Font dùng Inter nếu máy có, fallback system font; không tải Google Fonts để giữ offline.

`package-lock.json` khóa frontend; `backend/requirements.txt` khóa phiên bản Python runtime và test dependencies đã kiểm chứng. FastAPI 0.156.4, Pydantic 2.14.1 và Uvicorn 0.54.0 không thay đổi stack yêu cầu. Các thư viện được kiểm chứng trên Linux/Python 3.12/Node 24; batch launchers Windows được cung cấp nhưng **chưa được chạy trên máy Windows thật**.

Giao diện giữ bố cục tiếng Việt của v0.1 và dùng bảng màu trắng–xám–đen và các bề mặt kính mờ theo ảnh tham chiếu. Có crawler chỉ đọc v0.3 Core và AI Workspace Phase 6; chưa triển khai GA4 hoặc backlinks. AI cloud là tùy chọn riêng, mặc định không gọi. Position là trung bình có trọng số impressions, không phải thứ hạng cố định; CTR là tổng clicks/impressions. Không dùng Demo/SQLite fixture để kết luận về hiệu quả SEO của domain thật. OAuth/live Google và Windows keyring trên máy thật còn Pending Live Verification.

## Bước tiếp theo

Thử một bộ từ khóa nhỏ: nhập bảng lịch sử, kiểm tra một tuần thực tế và đối chiếu exact-query metrics trong hai scope với GSC cùng kỳ. Live Google/Windows cần xác minh trên máy cá nhân. Chạy Quick Audit có giới hạn trên website bạn quản lý để xem bằng chứng Technical SEO. Khi Core được xác nhận với dữ liệu thực, ưu tiên URL Inspection cho một số URL quan trọng; vẫn giữ Google index evidence riêng với local crawl. Live OAuth/sync cần xác minh trên Windows nếu chưa thực hiện.
