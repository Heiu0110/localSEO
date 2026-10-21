# Validation evidence · v0.1

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
