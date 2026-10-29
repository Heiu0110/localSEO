# Nguồn và provider v0.7 Core

| Nguồn | Trạng thái | Phạm vi |
|---|---|---|
| Seed thủ công | Đã triển khai | Không demand metrics |
| GSC SQLite / demo có nhãn | Đã triển khai | Query rows đã lưu, cùng kỳ; không search volume |
| Keyword Tracking | Đã triển khai | Bộ/nhóm/keyword/URL và rank MANUAL có profile riêng |
| Technical SEO | Đã triển khai | Title/URL snapshot đã lưu; không crawl mới |
| CSV/XLSX/JSON | Đã triển khai | User-supplied provenance, chưa xác minh live |
| Manual/imported SERP | Đã triển khai | Snapshot có metadata, bất biến |
| Google Ads API | Chưa triển khai/kết nối | v0.7.1 tùy chọn, cần developer token, OAuth và quyền customer riêng |
| SERP API | Chưa triển khai/kết nối | v0.7.1 tùy chọn; cần chọn một provider và xác minh docs/terms/schema/cost |
| Google Trends API | Chưa triển khai/kết nối | Không giả định alpha access; relative interest có thể nhập qua Candidate JSON |

Core không cần API key và không phát sinh chi phí provider. `/api/research/providers` công bố trạng thái/giới hạn; `/serp/check` trả unavailable, không thực hiện request trả phí. Chưa có adapter provider live, cost accounting provider hoặc luồng nhập credentials cho Research. Không trình bày chúng như đã cấu hình xong.

Không dùng token `webmasters.readonly` cho Google Ads, không mở rộng scope GSC. Bản Core không scrape Google Suggest/Search, không CAPTCHA bypass/proxy rotation. Khi phát triển v0.7.1 cần review tài liệu chính thức trước khi chọn đúng một provider, bổ sung vault, estimate/consent/budget/idempotency/cache và mocked tests, sau đó mới live verification được người dùng cho phép. Không cần gửi credentials để dùng Core hiện tại.

OpenAI vẫn cấu hình riêng theo Phase 6, dùng đúng consent/model/cost controls cũ; Research không tự gọi generation hoặc gửi bulk AI jobs.
