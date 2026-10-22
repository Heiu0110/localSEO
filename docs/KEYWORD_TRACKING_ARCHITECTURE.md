# Kiến trúc Keyword Tracking v0.4

Module mở rộng ứng dụng hiện có, không thay MockProvider, DashboardService, OAuth, dữ liệu GSC hay crawler. UI tiếng Việt dùng các token nâu–kem hiện tại. Route `/keyword-tracking` được tải riêng khi mở để hạn chế tăng bundle khởi động Dashboard.

## Các thành phần

- `backend/app/keywords/models.py`: metadata, lịch, quan sát, cache, job nhập và activity.
- `schemas.py`, `core.py`: validation, Unicode, URL, lịch tuần, ghi nhận và so sánh.
- `reports.py`: truy vấn SQL phân trang, filter/sort allowlist, đại diện ô, tổng quan.
- `gsc.py`: worker duy nhất, cache và exact query qua client/OAuth sẵn có.
- `spreadsheets.py`: đọc CSV/XLSX có giới hạn, preview/commit, export an toàn.
- `providers.py`: Protocol cho provider SERP sau này; chưa có collector tự động.
- `backend/app/api/keyword_routes.py`: API dùng chung Origin, CSRF và giới hạn request của app.
- `frontend/src/features/keywords`: trang chính, bảng, kiểm tra tuần, drawer, analytics và nhập/xuất.

## Luồng đọc và ghi

Mở bảng chỉ đọc SQLite. Backend lọc và sắp xếp trước khi phân trang, 25/50/100 dòng; lịch sử của grid chỉ trả đại diện cho những dòng và tuần đang hiển thị. Drawer phân trang các lần ghi nhận, kèm đại diện từng tuần. TanStack Query giữ các object không thay đổi; row/cell dùng memo, trạng thái nhập đặt ở cell. Không dùng optimistic update cho rank: chỉ đóng ô sau khi API ghi thành công; lỗi giữ nguyên giá trị đang nhập.

Mỗi lần lưu là một observation mới; clear ghi NOT_CHECKED. API bulk và import commit là transaction, có lỗi thì rollback toàn bộ batch. Xem trước import chưa thay danh sách. Khối dán được kiểm tra toàn bộ và xác nhận trước khi ghi.

## Đồng bộ GSC

Hàng đợi riêng một worker, một job active/bộ (partial unique index). Bấm Sync lấy danh sách keyword/query/URL đóng băng cho job; không gọi Google trong GET bảng. Mỗi query tối đa một yêu cầu tổng và một yêu cầu observed pages. Dùng lại cache thành công dưới 6 giờ; có nút refresh. Cache daily query hiện có chỉ dùng khi đủ toàn kỳ, aggregation byProperty đúng và exact query có mặt từng ngày. Không ghép tổng query và tổng page độc lập.

Job ghi tiến độ bền vững, hủy giữa request, khởi động lại đánh dấu interrupted; chạy lại dùng cache. Lỗi quota/quyền/OAuth giữ cache cũ. Google client hiện tại xử lý refresh token, thu hồi quyền, timeout và backoff. Shutdown chờ request đang chạy kết thúc; không thể hủy HTTP tức thì.

## Tích hợp

Dashboard thêm thẻ nhỏ khi có bộ active; dùng bộ/profile đầu tiên theo thứ tự tạo, tuần hiện tại theo múi giờ bộ. Không thay KPI traffic. Drawer tìm bằng chứng Technical SEO đã lưu theo URL, ghi thời điểm và mở URL Investigation; không tự crawl. Thiếu audit không được hiểu là URL tốt.

## Giới hạn hiện tại

Desktop ưu tiên; sáu cột cố định trên màn rộng, chỉ cột từ khóa cố định khi viewport ≤1100 px để còn chỗ xem các tuần. 35 cột sinh động, có thể lưu tới tuần 520. Tối đa 5.000 keyword/lượt sync hoặc export, 500 ô/batch rank, 200 keyword/batch metadata, 100 KiB và 1.000 dòng/tệp nhập. Không có benchmark cam kết cho dataset hàng triệu observation; chưa thêm virtualization khi chưa có bằng chứng cần thiết.

Core đã có shortcut Google, checklist, ghi chú, Enter/Escape/Tab/mũi tên. Screenshot evidence, mở Chrome riêng tư từ backend, scheduled sync và automatic SERP chưa triển khai. Không scrape Google hoặc bypass CAPTCHA.
