# Xử lý lỗi v0.3

## Technical SEO

| Triệu chứng | Hành động |
|---|---|
| unsafe_host / unsafe_network / out_of_scope | Dùng website HTTP/HTTPS công khai, cổng chuẩn và hostname được phép. Private IP/localhost/metadata hoặc DNS có IP riêng bị chặn có chủ ý; không tắt SSRF hoặc TLS để vượt chặn. Dùng bộ thử nghiệm ngoại tuyến nếu chỉ cần kiểm tra UI. |
| audit_already_active | Một project chỉ có một queued/running run. Chờ hoặc hủy run đó; website khác có thể xếp hàng riêng. |
| robots unknown hoặc 401/403 | Xem bằng chứng robots; crawler fail closed. Kiểm tra site/robots thực tế, không giả Googlebot hoặc bỏ robots. |
| Audit lâu | Xem phase, processed và HTTP requests. Giảm max URLs/depth/scope. Redirects/sitemap/retries làm tăng requests; không có thời gian hoàn tất cam kết. OS DNS resolver có thời gian chờ riêng. |
| partial / interrupted | Kết quả đã lưu còn nguyên. Xem coverage/caps/error; Chạy lại tạo snapshot mới. Core chưa resume frontier trong cùng snapshot. |
| Check chưa đánh giá | URL có thể bị robots, HTTP lỗi, body giới hạn hoặc không phải HTML. Not Checked không phải Passed; mở URL detail và đọc evidence. |
| Không xác nhận resolved | Cần hai snapshot cùng project/scope/version, đủ coverage và check được đánh giá lại. Đổi URL intent hoặc config cũng thay scope hash. |
| Export bị từ chối khi active | Chờ audit dừng hoặc hủy rồi xuất snapshot nhất quán. |
| CSV import bị từ chối | Chỉ important-URL CSV UTF-8 ≤100 KiB/1.000 URL, đúng header/enum, trong scope và không trùng sau normalization. |

Xem [hướng dẫn Technical SEO](TECHNICAL_AUDIT_USER_GUIDE.md) và [giới hạn Core](TECHNICAL_LIMITATIONS.md). Chưa có rendering, CWV, GSC URL Inspection hoặc log parser để bật bằng cài đặt.

## Frontend khởi động lâu

Backend in `Application startup complete` và địa chỉ `127.0.0.1:8000` nghĩa là đã chạy xong; cửa sổ đó tiếp tục mở để phục vụ API.

Ảnh log có `added … packages in 9m` nhưng `VITE ready in 263ms` nghĩa là chậm ở npm tải/cài dependency, không phải Dashboard hoặc Vite. Thời gian mạng/ổ đĩa trên máy thật chưa thể suy ra chỉ từ ảnh.

Launcher hiện đối chiếu dependency thực tế với lockfile và phiên bản đã cài. Đổi version app, định dạng JSON hoặc thiếu stamp từ launcher cũ không tự buộc cài lại toàn bộ. Bản cài hợp lệ từ `npm ci` cũng được dùng lại sau một kiểm tra Vite/esbuild/plugin ngoại tuyến. Giữ nguyên `frontend/node_modules`; đừng giải nén vào thư mục mới mỗi lần cập nhật nếu muốn giữ bản cài.

Khi thật sự cần npm, launcher dùng cache chung của máy/cấu hình npm; nếu dự án đã có `.cache/npm` từ bản cũ thì giữ cache ấm đó. Log `npm http` cho biết đang tải gói nào hoặc cache hit. Cấu hình npm `fetch-timeout` mặc định 120 giây, retry một lần; toàn lượt cài được phép tối đa **600 giây (10 phút)**. Giới hạn này chỉ dành cho bước cài, không làm chậm những lần chạy khi thư viện đã hợp lệ. Quá hạn thực sự sẽ dừng tiến trình con; chỉ ghi nhận thành công sau mã thoát npm bằng 0, đối chiếu dependency và kiểm tra Vite/esbuild/plugin.

Trường hợp `added … packages in 3m` rồi launcher cũ báo quá 180 giây xảy ra khi tải gói gần chạm giới hạn, sau đó npm còn chạy postinstall/hoàn tất lượt cài. Launcher mới tăng thời gian cho cài lần đầu và nhận sự kiện kết thúc tiến trình npm ngay, không chờ đóng các handle sau khi tiến trình đã thoát. Nếu npm kết thúc bình thường đúng lúc bộ hẹn giờ hết hạn, mã thoát 0 vẫn được kiểm tra bằng bản cài và native probe; không chỉ dựa vào dòng `added … packages` để coi là thành công.

Sau khi bản cài vừa hoàn tất như ảnh, cập nhật code rồi mở lại cùng thư mục:

```powershell
git pull
.\run-frontend.bat
```

Bạn sẽ thấy `Dependency không đổi… bỏ qua npm ci` hoặc `Tìm thấy bản cài khớp lockfile… không tải lại npm`. Lần chuyển sang launcher mới chỉ thêm kiểm tra native một lần. Cài mới từ đầu vẫn cần Internet hoặc cache đầy đủ và phụ thuộc tốc độ mạng/ổ đĩa.

Nếu mạng chậm hơn 10 phút nhưng log HTTP vẫn tiến triển, cho phép tối đa 20 phút **chỉ cho lần cài đó** (cấu hình fetch-timeout vẫn 120 giây):

```powershell
.\run-frontend.bat --install-timeout=1200
```

Dừng cửa sổ frontend đang chạy trước. Chỉ khi bản cài bị hỏng hoặc kiểm tra native báo thiếu file, dùng cài lại có chủ ý (npm ci sẽ thay node_modules, giữ cache):

```powershell
.\run-frontend.bat --repair --install-timeout=600
```

Không mở hai cửa sổ cùng cài dependency: launcher chặn lượt thứ hai và tự thu hồi khóa của tiến trình đã dừng. Lỗi mạng cần xem dòng `npm http`/`npm ERR` và kiểm tra VPN/proxy/firewall, không tắt TLS. Có thể chẩn đoán riêng với `npm ping --fetch-retries=0 --fetch-timeout=10000` trong `frontend/`. Nếu npm cảnh báo install script của esbuild nhưng Vite chạy được thì không cần tự động approve; launcher mới kiểm tra công cụ native trước khi ghi nhận bản cài dùng được.

Kiểm thử launcher: `node --test scripts/tests/frontend.test.mjs`. Tests sử dụng thư mục tạm, không xóa bản cài hoặc dữ liệu thật. Native Windows vẫn cần kiểm chứng trên máy cá nhân; tests hiện xác minh command/arguments Windows và đường dẫn chứa khoảng trắng, còn đo thời gian thực tế được thực hiện trên Linux.

Sau khi thấy `Local: http://127.0.0.1:5173/`, mở địa chỉ đó bằng trình duyệt. Terminal không tự đóng khi server chạy bình thường. Muốn dừng, nhấn Ctrl+C.

## Các lỗi khác

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

Chưa triển khai GA4, backlink provider, AI hoặc auth đa người dùng. Crawler Technical SEO Core đã có, advanced integrations còn chưa thực hiện. OAuth/live Google trên Windows thật còn **Pending Live Verification** cho đến khi người dùng cấu hình và kiểm tra tài khoản của mình.


## Keyword Tracking v0.4

- Ô rank từ chối timestamp: ngày local phải thuộc tuần đã chọn. Nếu chỉ biết tuần lịch sử, chọn “Nhập lịch sử: chỉ biết tuần”; không suy ngày từ kỳ GSC.
- Không sửa được lịch bộ: đã có observation. Tạo bộ mới và nhập lịch sử có ánh xạ tuần; không xóa database.
- GSC là —: xem tooltip và nguồn/thời điểm trong drawer; chọn đúng property/kỳ/scope rồi Sync. Demo website không có GSC. No Rows có thể do privacy, không phải 0.
- Kỳ custom quá cũ hoặc chưa final: chọn vùng dữ liệu final trong khoảng lịch sử GSC hỗ trợ. Cache cũ vẫn đọc được.
- Import báo lỗi cột: mở Ánh xạ cột, chọn keyword/week tương ứng, xem trước lại; xác nhận bỏ dòng lỗi chỉ khi chấp nhận. Tệp lớn cần chia nhỏ dưới100KiB/1.000dòng.
- Sáu cột chiếm hết màn hình nhỏ: tại ≤1100px chỉ cột keyword cố định; cuộn ngang để xem phần còn lại. Desktop là trải nghiệm ưu tiên.
- Sync bị dừng: job interrupted/cancelled có thể chạy lại dùng cache; giữ nguyên dữ liệu đã lưu. Không chạy scraping để thay OAuth.


## AI Workspace Phase 6

- Báo cáo ngoại tuyến không phải AI/LLM; vẫn đọc nguồn dữ liệu đã lưu và không tiêu token.
- Thiếu Topical Map/URL Inspection/Server Logs: module/adapter chưa tồn tại, không thể bật bằng model hoặc API key.
- Không có keyring trong cloud: giữ báo cáo ngoại tuyến; cấu hình bằng terminal/Windows Credential Manager trên máy cá nhân, không plaintext fallback.
- Model chưa kiểm tra: AI Settings → làm mới trạng thái key → Kiểm tra key/model. GET model không phải generation trả phí.
- Giá chưa xác minh: kiểm tra bảng giá đúng model và nhập ước tính. Không có mức giá giả mặc định; USD không phải hóa đơn provider.
- Consent/estimate biến mất khi sửa câu hỏi: cần kiểm tra lại ước tính/xác nhận vì đây là lượt gửi mới. Không bật xác nhận mặc định.
- Tool/context vượt giới hạn hoặc kỳ không khớp: thu hẹp câu hỏi/chọn lại kỳ GSC; keyword week độc lập. Không dùng SQL hoặc scrape để thay dữ liệu thiếu.
- Unknown usage sau timeout: giữ dự phòng, không tự replay. Xóa hội thoại vẫn giữ usage để tính ngân sách.

Xem [AI user guide](AI_AGENT_USER_GUIDE.md) và [AI provider setup](AI_PROVIDER_SETUP.md).
