# Xử lý lỗi v0.2

| Triệu chứng | Hành động |
|---|---|
| Không có kho khóa/secure_storage_unavailable | Windows: chạy bằng tài khoản cá nhân có Credential Manager; kiểm tra keyring/pywin32-ctypes đã được script cài. Linux headless cần Secret Service/KWallet được hỗ trợ; không dùng plaintext keyring. Demo và SQLite vẫn hoạt động. |
| OAuth JSON không hợp lệ | Tải file **Desktop app** từ Google Cloud, tối đa 64 KB. Web client/service-account JSON bị từ chối. Không chỉnh auth_uri/token_uri sang server khác. |
| access_denied / ứng dụng chưa cho tài khoản truy cập | Kiểm tra Audience, thêm Test user, quyền GSC và trạng thái Google Auth Platform. Không thêm scope không liên quan. |
| redirect_uri_mismatch / callback không tới backend | Dùng Desktop client, chạy cùng máy với trình duyệt; backend cổng 8000, callback 127.0.0.1. Cloud container không phải loopback của máy cá nhân. Không dùng OOB. |
| State hết hạn hoặc callback được mở lại | Bắt đầu lại từ Settings; state dùng một lần và hết hạn sau 10 phút. Không copy/reuse URL callback cũ. |
| Cần xác thực lại / invalid_grant | Refresh token hết hạn/bị thu hồi, thường gặp External Testing khoảng 7 ngày. Dùng Kết nối lại Google; SQLite không bị xóa. |
| 403 permission_denied | Bật Search Console API đúng Google Cloud project; kiểm tra tài khoản có quyền đúng exact Domain/URL-prefix property. Làm mới properties. |
| 429/quota_exceeded | Chờ theo Google và retry; không chạy nhiều bản backend trên cùng database. Mỗi ngày có 5 datasets và có thể phân trang. |
| Offline/timeout/server error | Đọc dữ liệu SQLite bình thường. Đồng bộ lỗi không xóa snapshot cũ; retry sau khi mạng hoạt động. Không tắt TLS/checksum verification. |
| Dashboard property không có số liệu | Kiểm tra đã thêm vào workspace, sync site dataset và chọn đúng search type/kỳ. Không có row không đồng nghĩa 0; không dùng demo thay thế. |
| Tổng Queries/Pages không khớp KPI | Đây là điều có thể xảy ra: privacy/API limits và aggregation byPage/byProperty khác nhau. KPI dùng site dataset độc lập. |
| Chưa đủ lịch sử so sánh | Đồng bộ dài hơn: muốn so sánh 90 ngày cần khoảng 180 ngày có bản ghi. Không tạo delta giả. |
| Thiếu related queries trong Page Detail | Chưa lưu query–page relationship trong v0.2; không suy ra từ hai bảng độc lập. 4 metric trends dùng daily page data đã có. |
| SQLite locked/read-only/full | Chỉ chạy một backend; kiểm tra quyền ghi và dung lượng thư mục data (cả WAL/SHM). Sửa nguyên nhân, khởi động lại, tiếp tục job. Không xóa database để bỏ qua lỗi. |
| Job partial/interrupted sau restart | Checkpoint đã lưu còn nguyên. Dùng Tiếp tục từ checkpoint; refresh job sẽ retry lại toàn kỳ được yêu cầu. |
| Phiên ứng dụng thay đổi / csrf_required | Backend vừa khởi động lại; tải lại frontend rồi thử. Không tắt CSRF/Origin checks. |
| 403 untrusted_origin / CORS / 411 | Dùng frontend 127.0.0.1 hoặc localhost cổng 5173. Native API client cần Content-Length và header X-CSRF-Token từ GET /api/session. Không dùng mutation GET. |
| CSV chỉ có Top 100 | CSV Dashboard chỉ xuất tập summary đang hiển thị. Dùng Phân tích GSC để export mọi dòng SQLite khớp bộ lọc; vẫn không phải toàn bộ Google export. |

Log không chứa token, credentials JSON hoặc auth code; callback query được che trong access log. Khi báo lỗi, chỉ cung cấp mã lỗi/job ID và mô tả; không gửi credentials, refresh token hoặc toàn bộ database chứa dữ liệu riêng tư.

Chưa triển khai GA4, crawler, backlink provider, AI hoặc auth đa người dùng. OAuth/live Google trên Windows thật còn **Pending Live Verification** cho đến khi người dùng cấu hình và kiểm tra tài khoản của mình.
