# Phạm vi và giới hạn v0.7 Core

Đã triển khai Core: project/seed/GSC stored/Tracking/crawl title/imports, Explorer và editing, manual/lexical/SERP-overlap clustering, intent heuristic/manual, immutable imported SERP, cohort competitor observations, rule opportunities/URL suggestions, human review, confirmed add-only Tracking transfer và 7 tools Agent.

Chưa triển khai: provider live Google Ads/SERP/Trends, polling/scheduler, semantic/LLM clustering chuyên dụng, tự crawl competitor, keyword expansion từ Google Suggest, auto update duplicates trong Tracking, tự suy luận cannibalization/market-wide content gaps, billing provider Research, Topical Map, AI visibility Phase 8, content generation/publishing.

Provider live là v0.7.1 tùy chọn, không phải credential đang chờ để Core chạy. Adapter/permission/schema/terms/price của provider Research cụ thể chưa được xác minh hoặc triển khai; không tuyên bố API thật thành công. Google Ads phải có quyền riêng với GSC. OpenAI Phase 6 và native Windows keyring vẫn cần xác minh thực trên máy người dùng nếu chưa làm.

Nhập số liệu bên ngoài là user-supplied, app không xác minh tuyên bố source/volume/difficulty. Dữ liệu quá khứ là quá khứ. Các metric có kỳ, unit/scope/provider riêng; không có độ phủ tuyệt đối của Google. Manual ranks NA/Not Checked không được đổi thành số rank; chỉ so hai tuần liền kề FOUND cùng chuỗi/profile/target.

Cơ hội dùng quy tắc minh bạch: impressions≥ngưỡng và CTR ratio thấp, GSC Average Position trong khoảng, có visibility nhưng mapping chưa duyệt, keyword chưa target (ứng viên gap trong project), rank MANUAL giảm cùng profile/chuỗi. Không có proprietary score. Reviewed opportunities giữ evidence, refresh chỉ cập nhật drafts. CTR thấp chưa chứng minh nguyên nhân hoặc cần sửa title. URL suggestions chỉ từ Tracking và token/title trong crawl đã lưu, không phải GSC observed query-page hoặc AI-generated URL.

Project duplicate giữ nguồn/metrics/keywords/clusters ở trạng thái draft, không sao chép snapshots/review history. Locale/website project bất biến; keyword khác locale giữ identity riêng. Transfer chỉ mới/skip, giữ locale trong notes; Search Profile do Tracking quản lý riêng. Cluster detail không có tổng unique search volume hoặc graph Topical Map.

Tệp giới hạn 100KiB/1.000rows; JSON có thể đạt body cap trước số dòng đó. Bảng phân trang, export đọc tối đa 5.000 keywords; cột sources có provenance JSON. Chưa benchmark hàng triệu observations. SQLite index/transaction không thay thế hệ thống đa người dùng; ứng dụng chỉ cho một người trên localhost.
