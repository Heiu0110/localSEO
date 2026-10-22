# Sử dụng Technical SEO

## Nâng cấp và chạy

1. Dừng hai server. Backup bằng `python scripts/backup_database.py`, rồi lấy source mới bằng `git pull origin main`.
2. Chạy `run-backend.bat` và `run-frontend.bat`. Backend cài thêm defusedxml và chạy migration tự động. Giữ `.cache` và `frontend/node_modules` để không tải lại thư viện không cần thiết.
3. Mở ứng dụng → **Technical SEO**. Không cần cấu hình Google để audit HTTP.

## Thử nghiệm trước

Chọn **Dự án mới → Tạo bộ thử nghiệm Technical SEO** rồi **Chạy audit mới**. Bộ này dùng `audit.fixture.example`, không gửi request ra mạng; vẫn chạy crawler, robots, XML/HTML parser, graph, rules, SQLite và báo cáo. Nhãn **Thử nghiệm ngoại tuyến** luôn hiển thị. Không dùng kết quả này để đánh giá domain thật.

## Audit website

1. Chọn **Dự án mới**, nhập Website URL hoặc điền từ website đã lưu. Chọn site demo chỉ điền URL, không biến mock thành dữ liệu crawl.
2. Đặt tên hoặc để ứng dụng gợi ý. Chọn Quick/Standard/Advanced và max URLs. Advanced chỉ tăng giới hạn, không tự bật rendering/Google APIs.
3. Chọn tốc độ thận trọng mặc định 1 request/giây; cấu hình sitemap, URL quan trọng, Allowed hosts, query policy, include/exclude glob, depth/timeout ở phần nâng cao nếu cần. Robots luôn bật.
4. Nhấn **Tạo dự án và bắt đầu audit**. Trong lần sau, **Cấu hình audit → Lưu cấu hình → Chạy audit mới**. Mỗi lần tạo snapshot riêng.
5. Xem phase, số URL xử lý và HTTP requests. Dùng **Hủy audit** nếu cần; kết quả đã lưu vẫn đọc được. Không đóng backend để thay cho hủy tác vụ.

Chỉ chọn GSC property bao phủ website đó. Crawl dùng riêng scope host và không tự truy cập mọi host trong Domain property. Property fixture GSC không được liên kết như dữ liệu Google thật.

## Đọc báo cáo

- **Tổng quan:** số lượng đo được, phân bố HTTP/mức độ/local indexability, ưu tiên xử lý, coverage và nguồn dữ liệu. Không có overall SEO score.
- **Crawl Explorer / Indexability:** server search/sort/pagination. Click URL xem status ban đầu/final URL, redirects, title/H1/canonical/robots, links, word count scope và GSC exposure nếu có. `—` là chưa có dữ liệu, không phải 0.
- **Vấn đề:** lọc severity/category/search, click finding để đọc evidence, confidence, recommendation và cách xác minh. Affected URL count thuộc cùng rule, không phải tổng traffic.
- **Sitemaps:** các tài liệu thực đã thử đọc; lỗi URL trong sitemap và lastmod nằm ở Issue Explorer.
- **Liên kết nội bộ:** source→target, anchor, context/rel và HTTP target đã biết. External links được ghi nhận nhưng không tự crawl.
- **Hiệu suất:** giải thích nguồn thời gian HTTP và GSC; không giả CWV/PageSpeed khi chưa tích hợp.
- **Danh mục kiểm tra:** capability và kết quả từng check. Not Checked/Not Available không phải Passed.

Local indexability chỉ là đánh giá HTTP/HTML: Indexable Candidate không xác nhận Google đã index. Noindex có thể là chủ ý. Orphan/soft 404/thin content/duplicate là candidate, cần đối chiếu mục đích và coverage; không phải kết luận ranking.

## Backlog và xác minh

Click công việc tại **Action Backlog**, đặt người xử lý (nhãn văn bản), ghi chú và trạng thái. Đây là ứng dụng một người dùng, không có hệ thống giao việc/gửi thông báo cho người khác.

“Đã sửa, chờ kiểm tra” không đánh dấu đã xác minh. Chạy audit mới cùng scope; nếu rule vẫn phát hiện, task mở lại và giữ ghi chú. Nếu audit đủ coverage, scope/version phù hợp và URL/check được đánh giá lại không còn lỗi, verification chuyển verified_absent. “Đã đóng” thủ công vẫn được gắn nhãn manual_status.

Trong URL panel có thể phân loại Critical Money Page/Important/Supporting/Low và Should Index/Should Not Index/Undecided. Phân loại mới chỉ áp dụng cho audit sau, không thay lịch sử. Khác mục đích index không tự cho phép so sánh như cùng scope.

## CSV quan trọng

Trong **Cấu hình audit**, nhập CSV UTF-8 tối đa 100 KiB/1.000 URL. Chỉ hỗ trợ loại này trong Core, không nhận log/Google credentials/Page Indexing CSV. Ví dụ:

```csv
url,priority,should_index,page_type,notes
https://example.com/product/,critical_money,yes,product,Trang kinh doanh
https://example.com/privacy/,low,no,legal,Xác nhận chính sách trước khi đổi
```

priority: `critical_money`, `important`, `supporting`, `low`; should_index: `yes`, `no`, `undecided`. Mọi URL phải trong scope dự án; URL trùng sau normalize bị từ chối. Xem preview rồi nhấn **Xác nhận nhập URL**; file import có provenance riêng.

## Lịch sử, xuất và retention

**Lịch sử audit** cho phép chọn snapshot cũ, chọn hai lần trước/sau và so sánh. Nếu scope/version hoặc coverage không phù hợp, chỉ báo newly observed/not observed; không suy luận đã sửa. Có giới hạn hiển thị 500 issue differences/200 URL changes mỗi comparison để giữ UI nhẹ, kèm tổng số.

Xuất CSV issues hoặc URL Inventory, JSON đầy đủ và HTML để mở/in bằng Ctrl+P. Dữ liệu là snapshot SQLite, có source/coverage/limitations; không phải toàn bộ Google index. JSON có backlog hiện tại được ghi rõ riêng với issue snapshots. Báo cáo HTML không chạy script, CSV bảo vệ formula injection.

Xóa từng snapshot đã dừng tại Lịch sử audit sau khi xác nhận. Backup/export trước; backlog và ghi chú được giữ, liên kết verification tới snapshot đã xóa được đánh dấu source_deleted. Không có tự xóa lịch sử hay monitoring khi ứng dụng đóng.
