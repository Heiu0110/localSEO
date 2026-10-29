# Keyword & SERP Intelligence — v0.7 Core

Research là phần mở rộng của ứng dụng hiện có, mở từ link trong Theo dõi từ khóa hoặc `/keyword-research`. Route React tải riêng, giữ token kem–be–nâu đồng, không thêm dependency.

Luồng: React → `/api/research` → `research/{core,analysis,serp,files}` → SQLite. Discovery chỉ đọc dịch vụ GSC, Tracking và Technical SEO hiện có. Migration 005 thêm 10 bảng Research; OAuth, providers Dashboard, crawler và rank history giữ nguyên.

`core.py` quản lý phạm vi, provenance, preview/commit, cluster/review và transfer. `analysis.py` tạo draft lexical/SERP-overlap, gợi ý intent/URL và cơ hội có quy tắc. `serp.py` lưu snapshot bất biến, so sánh profile tương thích và tổng hợp domain theo cohort. `files.py` tái sử dụng bộ đọc spreadsheet có giới hạn từ Phase 4. `responses.py` định nghĩa output contracts chính. `agent_tools.py` bổ sung 7 adapter vào Agent Phase 6.

Mỗi dự án có website cố định hoặc không gắn website. Keyword identity là NFC + casefold + gom whitespace, trong phạm vi dự án/country/language. Không bỏ dấu hoặc tự bỏ punctuation. Một keyword có nhiều source observations/metrics độc lập. Việc nhập trùng không sửa intent/URL/review do người dùng đã chọn.

Mọi import có preview lưu trên server và confirmation. Commit trong transaction, cùng job ID trả lại kết quả đã commit khi retry. Transfer chỉ thêm keyword đã duyệt vào bộ của cùng website; skip duplicate; kiểm tra lại bản xem trước nếu Research/Tracking đã thay đổi. Không gọi hàm ghi rank.

Không có scheduler, web browser agent, arbitrary URL fetch, auto-publishing hoặc một AI Agent thứ hai. External provider chưa triển khai trong Core, không có request trả phí phát sinh từ Research.
