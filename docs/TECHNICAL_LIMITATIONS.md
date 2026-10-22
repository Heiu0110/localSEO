# Phạm vi và giới hạn v0.3 Core

## Đã có

Crawler HTTP/HTML có scope/robots/rate/size/depth/URL caps và IP pinning; sitemap index; redirects/status; metadata/canonical/noindex; observed link graph/depth; deterministic evidence-backed issues; manual URL intent; explainable queue priority; persistent jobs/audits/backlog; historical comparison; important-URL CSV preview/commit; CSV/JSON/printable HTML; Dashboard summary khi có audit live phù hợp.

Catalog chứa **138** checks của toàn master, **63** capability tự động trong Core (gồm 39 loại rule sinh finding, các tín hiệu thu thập và workflow). 49 checks chưa triển khai, 19 cần tích hợp, 7 cần xem thủ công. Không tuyên bố 138 checks đã được đánh giá. Trạng thái mỗi run phụ thuộc data/coverage, không chỉ capability.

## Chưa triển khai / cần nguồn khác

- **v0.3.1:** GSC URL Inspection, Page Indexing CSV analysis, raw/rendered comparison, query×page analysis, content similarity nâng cao. Google index status/canonical trong URL panel hiện null, không giả lập từ local crawl.
- **v0.3.2:** CWV/CrUX/PageSpeed, mobile viewport parity, structured-data eligibility, security diagnostics nâng cao. JSON-LD chỉ đếm tín hiệu trong extraction; không có rich-results validation. Không thể bật rendering bằng cách nhập field lạ vào config, chưa có browser crawler production hoặc hướng dẫn “bật” một engine chưa xây.
- **v0.3.3:** server logs, WordPress diagnostics, recurring monitoring/alerts, LocalBusiness consistency và GEO analysis. Không biết CPU/PHP/plugin settings từ public HTTP, không có Google Crawl Stats/Manual Actions/Security Issues API giả.
- Chưa có redirect mapping/log/Page Indexing import, lịch tự động hoặc PDF renderer riêng. HTML có thể in/lưu PDF bằng browser.

## Diễn giải

- Coverage complete chỉ là hết frontier trong scope/caps đã chọn; không chứng minh đã có mọi URL trên website/Google. Robots/exclusions giới hạn quan sát. Orphan là candidate trong graph đã thấy.
- Word count/fingerprint dùng main/article nếu có, nếu không dùng visible text của raw document; có ghi scope. Không phải đánh giá chất lượng nội dung hoặc near-duplicate semantic analysis.
- Không crawl CSS/JS/images như browser, không xử lý nội dung sau tương tác, không dùng cookies đăng nhập hoặc vượt WAF. Resource blocking chỉ là mô phỏng robots từ href đã trích xuất. HTML parse không phải W3C validator.
- Không gộp URL có/không trailing slash. Query preserved mặc định; user chọn bỏ query có thể làm mất phân biệt URL có ý nghĩa.
- Chỉ hostname allowlist/cổng chuẩn; không tự kiểm tra tất cả www/non-www/HTTP variants. Muốn audit host khác cần thêm cụ thể hoặc tạo project, vẫn phải công khai và an toàn. DNS resolver của hệ điều hành có thể chờ lâu hơn TCP/HTTP timeout.
- Delay/concurrency/caps không phải lời hứa hoàn tất trong thời gian cố định. Core một request tại một thời điểm, không có tùy chọn bỏ SSRF/robots guards.
- GSC exposure là page/byPage/web đã lưu, không xác nhận index hoặc quan hệ nhân quả traffic. Top 5.000 seeds và crawl cap có thể hạn chế coverage; không dùng query aggregates để tạo query-page pairs.
- Khi đổi config/URL intent hoặc rule version, comparison có thể không xác nhận resolved. Khi snapshot bị xóa, verification source được gắn nhãn rõ; backlog vẫn còn.
- UI so sánh tối đa 500 issue differences và 200 URL changes; inventory/issues/links/backlog được phân trang server. Export snapshot có giới hạn gián tiếp qua crawl caps, vẫn có thể lớn; không lưu HTML không giới hạn.

## Xác minh triển khai

Tests dùng fixtures/MockTransport và SQLite tạm. Có fixture Technical SEO cố định để thử UI mà không request domain thật; không có production fallback sang fixture khi network lỗi. Chưa crawl website production của người dùng, chưa chạy Windows native hoặc Google credentials thật trong lần triển khai này. Các kiểm tra đó cần thực hiện trên máy cá nhân theo cấu hình thực tế; không cần cấp OAuth để xác minh crawler cơ bản.
