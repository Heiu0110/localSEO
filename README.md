# SEO Local Workspace · v0.2

Ứng dụng phân tích SEO chạy local cho một người dùng: React Dashboard + FastAPI + SQLite. Giữ nguyên hai website demo qua Mock Provider; properties Google dùng SQLite Analytics Provider riêng sau khi được cấp quyền. Có bộ thử nghiệm SQLite để kiểm tra toàn luồng mà không cần Google. Không có login ứng dụng, Docker hoặc cloud deployment. Dữ liệu Google thật chỉ xuất hiện sau khi chính bạn kết nối và đồng bộ; không tự truy cập các domain demo.


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

## Chạy trên Windows 10/11

Yêu cầu **Python 3.11+** (bật “Add Python to PATH”) và **Node.js 24 LTS** kèm npm (tối thiểu Node 22.12). Mở terminal mới sau khi cài. Cần Internet cho lần cài dependencies đầu tiên; sau đó ứng dụng chạy offline nếu lockfile không thay đổi.

1. Mở thư mục project trong VS Code.
2. Chạy `run-backend.bat` bằng double-click hoặc terminal.
3. Chạy `run-frontend.bat` trong cửa sổ khác.
4. Mở frontend: `http://127.0.0.1:5173`.

Backend: `http://127.0.0.1:8000` (không có trang ở `/`; xem `/api/health`). Swagger API docs: `http://127.0.0.1:8000/docs`. Swagger UI được lưu sẵn trong project để tài liệu cũng hoạt động offline, không cần CDN.

Hai script tự kiểm tra runtime, tạo `backend/.venv`, cài dependencies đã khóa và chạy server. Cài lại khi checksum của lockfile/requirements thay đổi; lần chạy tiếp theo không gọi package registry. Cache cài đặt nằm trong `.cache/`, không cần quyền administrator. Hai server mặc định chỉ bind **127.0.0.1**. Không cần tạo `.env`; Vite proxy `/api` sang backend. `.env.example` chỉ dành cho tùy chọn override API base URL.

**Dừng ứng dụng:** nhấn `Ctrl+C` ở cả hai cửa sổ, xác nhận `Y` nếu Windows hỏi dừng batch job. Không copy `node_modules` hoặc `.venv` giữa Windows và Linux; để script cài lại trên hệ điều hành tương ứng.

### Linux/macOS hoặc chạy thủ công

Từ thư mục gốc, mở hai terminal:

```bash
python scripts/backend.py --run
node scripts/frontend.mjs --run
```

Dùng `python3` nếu máy chỉ có lệnh này. Có thể chỉ chuẩn bị dependencies bằng cách bỏ `--run`. Các lệnh bên dưới dùng Python của virtual environment:

```bash
# Backend, từ backend/
python -m venv .venv
# Windows:
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# Linux/macOS thay .venv\Scripts\python.exe bằng .venv/bin/python

# Frontend, từ frontend/
npm ci
npm run dev
```

### Những lỗi thường gặp

| Vấn đề | Cách xử lý |
|---|---|
| Không tìm thấy Python/Node/npm | Cài runtime ở trên, mở terminal mới; kiểm tra `python --version`/`py -3 --version` và `node --version`. |
| Dashboard báo không gọi được API hoặc lỗi 500 proxy | Khởi chạy backend trước; kiểm tra `/api/health` và log terminal backend. Bấm **Thử lại**. |
| Port 8000 hoặc 5173 đã được dùng | Dừng bản ứng dụng cũ. Vite dùng strict port để không tự đổi sang cổng ngoài cấu hình CORS. |
| Cài dependency thất bại | Kiểm tra Internet, quyền ghi vào thư mục project và log package manager. Không bỏ TLS hoặc integrity verification. |
| Đã đổi `.env` nhưng chưa có tác dụng | Khởi động lại Vite. Chỉ `frontend/.env.local` được Vite đọc cho cấu hình frontend. |
| Môi trường ảo bị xóa một phần | Dừng backend, xóa `backend/.venv` rồi chạy lại script. Không xóa mã nguồn. |
| `node_modules` bị xóa một phần | Dừng frontend, xóa `frontend/node_modules` rồi chạy lại script. |
| Ngày dữ liệu không chạy theo ngày hôm nay | Đây là fixture 200 ngày cố định, kết thúc **20/10/2026**. “Last N days” tính từ ngày cuối fixture, được ghi trên Dashboard. |

## Dashboard được giữ từ v0.1

- Giao diện tiếng Việt, giữ tên sản phẩm và thuật ngữ SEO phù hợp. Màu chủ đạo: trắng, xám, bạc, vàng đậm, nâu đất và nâu sẫm; bảng màu dùng chung qua CSS variables. Số hiển thị theo `vi-VN`, ngày `dd/mm/yyyy`; dữ liệu API và giá trị số trong CSV giữ định dạng máy đọc được.
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
- Technical SEO, Keyword Tracking, Topical Map, Internal Links và SEO Reports vẫn là placeholder. Settings và Phân tích GSC đã được triển khai ở v0.2.

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

Giao diện giữ thiết kế tiếng Việt và bảng màu trắng–xám–bạc–vàng đậm–nâu của v0.1. Không triển khai GA4, crawling, backlinks hoặc AI. Position là trung bình có trọng số impressions, không phải thứ hạng cố định; CTR là tổng clicks/impressions. Không dùng Demo/SQLite fixture để kết luận về hiệu quả SEO của domain thật. OAuth/live Google và Windows keyring trên máy thật còn Pending Live Verification.

## Bước tiếp theo

Thực hiện live OAuth và một lần sync thật trên Windows theo hướng dẫn Google Cloud, đối chiếu số liệu site-level trong cùng kỳ/search type với GSC và kiểm tra reconnect/revoke. Chỉ mở rộng phân tích sau khi luồng này được xác minh.
