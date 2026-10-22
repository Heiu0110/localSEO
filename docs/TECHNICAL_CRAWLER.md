# Crawler chỉ đọc

Chỉ crawl website bạn có quyền kiểm tra. Nút chạy audit mới gửi GET công khai; không có chức năng sửa website, đăng nhập, submit form, vượt CAPTCHA/WAF hoặc gửi sitemap lên Google.

## Scope và mạng

- Mặc định chỉ hostname của Website URL, HTTP/HTTPS cổng chuẩn. Subdomain/host khác chỉ được xét nếu nhập tên cụ thể trong Allowed hosts; không có wildcard crawl toàn domain.
- Chặn URL có credentials, schemes khác HTTP/HTTPS, cổng tùy ý, localhost và tên miền dành riêng. Không cho phép truy cập private/loopback/link-local/metadata IP.
- Mỗi kết nối kiểm tra toàn bộ IP mà DNS trả về; nếu có IP không công khai thì từ chối. Socket kết nối vào IP đã kiểm tra, không DNS lookup lần thứ hai. Redirect kiểm tra lại scope và robots; TLS giữ SNI/hostname gốc, không tắt verification. Không dùng HTTP_PROXY/Google ADC của môi trường.
- Bỏ URL có dấu hiệu hành động: logout, delete, remove, checkout, purchase, wp-admin/wp-login và các query action liên quan. Có thể bỏ nhầm URL lành tính; không có nút tắt bảo vệ này trong Core.
- IP/hostname không an toàn không được đưa vào allowlist để vượt bảo vệ. Fixture offline là transport cố định, không phải tùy chọn cho phép localhost/private network.

## Giới hạn

| Giới hạn | Core |
|---|---|
| Quick / Standard / Advanced | 100 / 500 / 2.000 URL mặc định; tùy chỉnh 1–5.000 |
| Concurrency | 1 request tại một thời điểm, một worker Technical SEO |
| Delay mỗi host | Mặc định 1 giây, có thể chọn 0,5–10 giây |
| Crawl depth | Mặc định 8, tối đa 30 HTML hops |
| TCP/HTTP timeout | Mặc định 15 giây, 2–60 giây; OS DNS resolver có thể có thời gian chờ riêng |
| Redirect | Tối đa 9 responses/chuỗi, phát hiện loop; không tự ra ngoài scope |
| Retry | Tối đa 1 retry cho 429/500/502/503/504; tôn trọng Retry-After tới 30 giây, dài hơn thì ngừng host |
| Lỗi tạm thời liên tiếp | Sau 3 responses lỗi tạm thời, không tiếp tục request vào host |
| HTML | Tối đa 2 MiB; compressed input và expanded output đều bị giới hạn |
| XML sitemap | Tối đa 4 MiB trước/sau giải nén, 10.000 entries/file; 10 files, 3 cấp index |
| URL discovery | Tối đa min(5 × max_urls, 20.000) |
| Links | Tối đa 3.000 links/trang, 100.000 links/audit |
| Headings / resources | Tối đa 200 headings và 200 resources phân tích/trang |

HTTP requests có thể nhiều hơn số URL do robots, sitemap, redirects và retry. Không cam kết thời gian hoàn tất cố định. `processed` tính cả URL robots-blocked; `crawled` chỉ đếm URL đã thử fetch. Progress không được dựng từ đồng hồ. Hủy được kiểm tra trong các khoảng chờ ngắn, nhưng request/DNS đang chạy có thể cần kết thúc hoặc timeout.

## robots.txt

404/410: không có robots, cho phép crawl trong scope. 401/403: không crawl nội dung. 5xx, timeout, HTML giả robots hoặc không xác định: fail closed. Robots bị lỗi không đồng nghĩa URL noindex. Crawl-delay được tôn trọng; giá trị trên 60 giây khiến trạng thái chưa xác định thay vì tạo tác vụ chờ không giới hạn.

Rule Googlebot được đánh giá riêng như **mô phỏng**. CSS/JS chỉ được phân tích href và quy tắc robots đã có; Core không khẳng định đã tải/kiểm tra sự khả dụng mọi resource hoặc tái tạo Google Web Rendering Service.

## URL và discovery

Giữ original URL/href và comparison key riêng; lưu tối đa 10 dạng URL/href đã thấy trên mỗi comparison key. Bỏ fragment, chuẩn hóa scheme/host/default port/percent-encoding/dot segments; giữ khác biệt trailing slash. Mặc định giữ query có ý nghĩa. Chỉ bỏ tracking/all query khi người dùng chọn rõ. Patterns là glob cho path, không phải regex. Discovery từ start URL, href HTML, sitemap, important/import và GSC pages đã lưu.

Link counts/depth trước khi graph được finalize trả unknown, không điền số 0 giả. Minimum observed HTML depth được tính bằng link graph từ start URL; redirect không tăng HTML depth. Sitemap/import/GSC-only URL không có đường liên kết từ start giữ depth unknown, không gán 0. Orphan chỉ là candidate không có inbound được quan sát trong coverage.

## Coverage, restart và giữ dữ liệu

`complete` chỉ nghĩa frontier đã xử lý trong cấu hình hiện tại, không bảo đảm có toàn website hoặc toàn bộ URL Google biết. Cap, lỗi truy cập/fetch, body/extraction bị giới hạn hoặc robots unknown tạo partial/warnings. 404 đã đo vẫn có thể nằm trong audit hoàn tất; URL-specific check chưa đủ dữ liệu không được đánh dấu đạt.

Queued/running sau restart chuyển interrupted. Kết quả từng URL còn nguyên, không tự request lại. Chạy lại tạo audit mới với cấu hình cũ; Core chưa resume frontier trong cùng snapshot. Không mở nhiều Uvicorn workers/bản backend trên cùng file SQLite.
