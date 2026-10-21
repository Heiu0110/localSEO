# Validation evidence · v0.2

Chạy trong workspace Linux ngày **21/10/2026**, trên repository hiện có. Trước khi thay đổi, baseline v0.1 tại `f7a0a25` đạt **28 backend tests, 18 browser tests và production build**. Mock Provider và DashboardService v0.1 được giữ nguyên mã nguồn. Dashboard tiếp tục dùng giao diện tiếng Việt và bảng màu đã thống nhất.

## Kết quả v0.2

### Bảng màu theo ảnh tham chiếu (21/10/2026)

Chỉ thay CSS tokens, favicon và browser theme-color: kem/be/nâu đồng/espresso trên Dashboard, Settings và GSC Analytics. Không sửa layout, frontend logic hoặc backend. Đã chạy `npm run build` thành công và toàn bộ **26 Playwright tests passed** trên dev server; đã xem browser screenshots desktop/mobile và focus state. Những cặp chữ chính đã kiểm tra đạt tương phản tối thiểu 4,5:1. Chi tiết phạm vi và ảnh nội bộ trong [design-qa.md](design-qa.md). Backend tests không chạy lại trong lần đổi màu này.

### Cập nhật tốc độ và log khởi động frontend (21/10/2026)

Đã thay npm wrapper ở bước chạy dev bằng gọi Vite trực tiếp qua Node; giữ điều kiện bỏ qua cài đặt khi fingerprint lockfile khớp. Khi cần cài, npm ưu tiên cache, bỏ network audit ở startup và in trạng thái mỗi 15 giây; không thay đổi TLS/integrity. npm CLI được gọi trực tiếp qua Node để hỗ trợ đường dẫn có khoảng trắng, không qua shell Windows.

Xác minh thực tế trên Linux: `node --check scripts/frontend.mjs` đạt; bootstrap với dependencies có sẵn báo chuẩn bị 0,0 giây và Vite Ready sau 172 ms. Cài sạch 174 packages trong thư mục tạm có khoảng trắng, dùng cache và bật npm offline, đạt sau 3,7 giây; chạy lại bỏ qua install. Cố ý tạo dependency không có trong offline cache: script trả exit 1 và không ghi stamp thành công. Gửi SIGINT tới launcher đã dừng cả launcher và Vite child. Hai browser regression tests cho navigation/chart và offline runtime đạt **2/2**. Không chạy lại toàn bộ backend/browser suite vì thay đổi chỉ ở launcher và tài liệu; kết quả đầy đủ v0.2 bên dưới là lượt xác minh trước đó. Chưa đo thời gian hoặc chạy launcher trên Windows thật; số đo Linux không phải cam kết tốc độ máy người dùng.

| Kiểm tra | Kết quả thực tế |
|---|---|
| Backend: `.venv/bin/python -m pytest -q` | **45 passed**, không failed/skipped/xfail |
| Backend: `.venv/bin/python -m pip check` | No broken requirements found |
| Frontend: `npm run build` | **Passed**, bao gồm TypeScript và Vite production build |
| Frontend: `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e` | **26 passed** trên production preview, không failed/skipped; suite cũng đã đạt 26/26 trên dev server |
| Bootstrap `python scripts/backend.py`, migration CLI, `node scripts/frontend.mjs` | Thành công; chạy lại dùng dependencies đã cài khi fingerprint không đổi |
| SQLite backup script | Backup cả dữ liệu trong WAL, integrity check thành công, từ chối ghi đè file đích |
| Live OAuth / Google API với tài khoản thật | **Not executed — Pending Live Verification** |
| Windows `.bat` và Windows Credential Manager trên máy thật | **Not executed — Pending Live Verification** |

Backend tests dùng SQLite tạm riêng và test-only MemoryVault, không đọc credentials thật. Bao phủ migrations/WAL/foreign keys/persistence; property identifiers và chống trùng; sync idempotent/initial/incremental/resume/refresh/cancel/recovery; rollback giữa trang; phân trang 25.000 và giới hạn 50.000; retry/quota/timeout; Google SDK request shape; PKCE/state một lần; token refresh/revoke giả lập; chống ghi token vào SQLite; từ chối plaintext keyring; CSRF/origin; upload cấu hình Desktop JSON; server search/sort/pagination; CSV và backup. KPI được đối chiếu với site facts độc lập, không bằng tổng queries; kiểm tra CTR/weighted position, search type, khoảng thiếu và không dựng mức giảm 100% từ detail row vắng mặt.

Browser suite giữ toàn bộ 18 regression tests cũ và thêm 8 tests: tạo property thử nghiệm SQLite, đồng bộ 14 ngày với tiến độ thực, đổi Mock/SQLite mà không lẫn KPI, 5 tab analytics, server pagination/search/sort, page detail, bốn CSV exports, cached reports khi chặn mạng ngoài loopback, thiếu kỳ so sánh, lỗi OAuth/reauthorization qua API giả lập và responsive. Kiểm tra overflow ở 1366/1024/768/390 px; đã xem screenshot nội bộ Dashboard, Settings, Analytics để kiểm tra sự nhất quán. Không tạo tài liệu review giao diện riêng.

Trong lượt kiểm tra cuối, một selector test khớp cả link sidebar và link trong nội dung; đã giới hạn vào navigation. Một lượt điều hướng bị gián đoạn vì build lại thư mục production đồng thời với tests; đã chạy lại suite sau khi build kết thúc. Kết quả cuối **26/26 passed**, không còn test failed hoặc skipped. Không vô hiệu hóa assertions, TLS hoặc package integrity để đạt kết quả.

Môi trường giữ Python 3.12.14 / Node 24.19.0 / npm 11.9.0 / Chromium 154 / Playwright 1.64.1 và stack v0.1. Dependencies bổ sung đã khóa trong `backend/requirements.txt`. Có một cảnh báo deprecation Starlette TestClient về httpx và cảnh báo màu terminal NO_COLOR/FORCE_COLOR; không có assertion thất bại.

## Phạm vi chưa xác minh

- Cloud headless hiện không có OS keyring phù hợp. Status API trả trạng thái rõ ràng; Demo, SQLite fixture, cached data và các tests vẫn hoạt động. Không thêm fallback token plaintext.
- Chưa dùng Google account/property thật, chưa kiểm tra consent/refresh/revoke/quota thật. Cần chạy luồng trong [Google setup](docs/GOOGLE_GSC_SETUP.md) trên máy cá nhân; không sử dụng ADC của môi trường cloud.
- Chưa chạy native Windows hoặc kiểm tra restore snapshot môi trường trong task mới. Bootstrap Python/Node dùng chung đã chạy trên Linux.
- Giới hạn có chủ ý: một kết nối Google active, một sync worker, bốn search types `web/image/video/news`, chưa có dataset quan hệ query–page. Google có thể giới hạn/ẩn detail rows dù đã phân trang; CSV chỉ xuất dữ liệu đã lưu.
- Đã cập nhật và lưu draft `install_script` / `start_skill` cho v0.2. **Chưa publish** snapshot. Để tái sử dụng cấu hình này, mở Environment settings, review/save rồi Publish; đây không phải triển khai ứng dụng lên cloud.

## Lịch sử xác minh v0.1

Các kết quả bên dưới ghi nhận phiên bản trước khi bổ sung GSC/SQLite, không mô tả phạm vi hiện tại của v0.2.

## Cập nhật giao diện tiếng Việt và bảng màu

Đã chạy lại `npm run build` (bao gồm TypeScript) và toàn bộ **18 Playwright tests: 18 passed**, không skipped/failed. Test tương tác dùng nhãn tiếng Việt và đối chiếu KPI với API theo định dạng `vi-VN`; CSV tiếp tục xuất đủ dữ liệu khớp bộ lọc với tiêu đề tiếng Việt. Đã kiểm tra bố cục ở 1366/1024/768/390 px và xem giao diện desktop/màn hình hẹp. Phát hiện và sửa việc Radix Tooltip chuyển callback `className` của NavLink thành chuỗi khi sidebar thu gọn; test kiểm tra nhãn ẩn và active class sau khi thu gọn.

Màu được quản lý tập trung bằng CSS variables: nền trắng/xám, đường nét bạc, nhấn vàng đậm, nâu đất và sidebar nâu sẫm. Backend/API contracts và mock dataset không thay đổi trong lần cập nhật này.

Chạy thực tế trong workspace Linux ngày 21/10/2026. Không suy diễn rằng đã chạy trên Windows hoặc đã publish/restore môi trường mới.

## Môi trường

- Python 3.12.14, Node.js 24.19.0, npm 11.9.0.
- Chromium 154.0.8037.57, Playwright 1.64.1, headless.
- React 19.3.1, React Router 7.18.4, Vite 7.3.7, TypeScript 5.9.3.
- Tailwind CSS 4.3.3, TanStack Query 5.104.5, Recharts 3.10.1.
- FastAPI 0.156.4, Pydantic 2.14.1, Uvicorn 0.54.0.
- Phiên bản đầy đủ được khóa trong package-lock.json và backend/requirements.txt.

## Kết quả

| Kiểm tra | Kết quả thực tế |
|---|---|
| `.venv/bin/python -m pytest -q` (cwd backend) | **28 passed**, không failed/skipped/xfail |
| `.venv/bin/python -m pip check` (cwd backend) | No broken requirements found |
| `npm run typecheck` (cwd frontend) | Passed |
| `npm run build` (cwd frontend; bao gồm typecheck) | Passed, Vite build production thành công |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e` (cwd frontend) | **18 passed** trên bản production qua `npm run preview`, không failed/skipped |
| Browser suite trên dev server trước khi thêm offline docs test | **17 passed** |
| `npm audit --omit=dev` | 0 vulnerabilities ở dependency production tại thời điểm kiểm tra |
| `python scripts/backend.py`, `node scripts/frontend.mjs` | Cài dependencies thành công, chạy lại bỏ qua cài đặt; fingerprint khớp requirements/lockfile |
| Backend qua `python scripts/backend.py --run --no-reload` | Khởi động và phục vụ health/sites/overview/docs thành công |
| Frontend qua `node scripts/frontend.mjs --run` | Khởi động Vite tại port 5173, proxy API hoạt động |

Backend tests kiểm tra CTR và weighted position bằng ví dụ tính tay; zero baseline; fixture tái lập 200 ngày; 2 websites × 7/28/90 ngày; partition sums theo daily/pages/queries/countries; equal-length, contiguous previous period; page detail/related-query reconciliation; 404, 422, CORS; local API documentation assets.

Browser tests thực hiện thao tác chọn website/ngày và đối chiếu cả 4 KPI với API cho cả 6 context; đổi chart metric; bật/tắt compare/series; table sort/search/pagination/empty state; chọn query; page details; CSV download chứa mọi dòng khớp bộ lọc; URL navigation/reload và sidebar preference; loading/error/retry/invalid-site recovery. Có kiểm tra CSV escaping/formula injection và số âm.

Responsive assertions tại **1366, 1024, 768, 390 px**: không có horizontal page overflow; bảng rộng cuộn trong container. Đã xem screenshot desktop để kiểm tra bố cục. Không tạo tài liệu ảnh review riêng.

Runtime test chặn mọi destination ngoài loopback: Dashboard vẫn hiển thị và không phát sinh request external. Một test riêng mở `/docs`, tải Swagger UI từ project, thực thi GET health trong Swagger và nhận provider=mock mà không dùng CDN.

Các test đối chiếu UI/API kiểm tra `pageerror` và console error: không phát hiện lỗi. Python test runner có **1 cảnh báo deprecation từ Starlette TestClient về httpx**; chưa phải lỗi runtime, toàn bộ assertions vẫn chạy. Node runner có cảnh báo NO_COLOR/FORCE_COLOR từ cấu hình màu terminal của môi trường. Không tắt kiểm tra TLS, package integrity, assertions hoặc test để đạt kết quả.

## Giới hạn xác minh

- Chưa chạy `.bat` trên Windows thật. Các script dùng launcher mỏng và gọi bootstrap Python/Node dùng chung đã chạy trên Linux; vẫn cần Windows smoke test trước khi phân phối rộng.
- Không có ảnh tham chiếu ngoài mô tả văn bản; không tuyên bố clone pixel-perfect.
- Chỉ mock fixture, không có kết nối GSC/GA4 thật; các module tương lai vẫn placeholder có ghi nhãn.
- Kiểm tra offline dùng browser request interception. Không mô phỏng máy mới chưa có dependencies; cài lần đầu vẫn cần Internet.
- Đã lưu draft `install_script` và `start_skill` cho môi trường hiện tại. Chưa publish snapshot hoặc kiểm tra restore trong task mới; publication là thao tác riêng trong Environment settings.
