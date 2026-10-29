# Dùng Keyword Research

1. Chạy hai `.bat` như README. Vào **Theo dõi từ khóa → Keyword Research**.
2. Nhấn **Dự án mới**, chọn website, country/language, nhập mục tiêu. Có thể để không gắn website; dự án độc lập dùng seed/tệp/SERP, không đọc nguồn website hoặc chuyển Tracking.
3. Trong **Nhập / Xuất**, chọn Seed, nhập mỗi dòng một keyword, nhấn Xem trước → kiểm tra trùng/nguồn → Xác nhận. Seed không có search volume.
4. Để nhập GSC, chọn nguồn **GSC queries đã lưu**, chọn 7/28/90 ngày, ngày cuối và ngưỡng lọc. Cần sync property trước trong Cài đặt. Demo có nhãn riêng; không thay thiếu dữ liệu thật bằng demo. Impressions không phải search volume; chi tiết query không bảo đảm đầy đủ. Không gán URL bằng cách ghép hai cube query/page.
5. Nguồn **Keyword Tracking** chọn bộ và tùy chọn ID nhóm; lấy keyword/target URL đã lưu, không sửa weekly rank. Nguồn **Title từ crawl** lấy title của snapshot gần nhất; là heuristic, không chứng minh Google demand.
6. Trong **Keyword Explorer**, tìm/lọc/sort, chọn cột và keyword; sửa intent, nhãn thương hiệu, nhóm, cluster, URL và review. Mở keyword để xem từng nguồn, kỳ metric, gợi ý intent/URL và review history. Giá trị thiếu ghi Chưa có.
7. Tạo cluster từ keyword đã chọn hoặc tạo cluster trống. Trong Clusters, gợi ý lexical hoặc SERP overlap → xem yếu tố → lưu bản nháp → chỉnh thành viên/primary/intent/page type/URL → review. Có merge/split/delete; xóa cluster giữ keywords. Xem [quy tắc clustering](KEYWORD_CLUSTERING.md).
8. **SERP Explorer**: chọn keyword đã lưu, khai báo nguồn/locale/device/location/thời gian/độ sâu; nhập JSON results thực tế → preview → xác nhận. Có thể nhập CSV/XLSX/JSON từ tab Nhập / Xuất. Xem [schema SERP](SERP_INTELLIGENCE.md). Không tự chạy Google.
9. Chọn snapshots để xem kết quả/feature được khai báo, website trong mẫu và so sánh. Tab Đối thủ tổng hợp domain theo từng cohort; mẫu số chỉ là số SERP mẫu tương thích.
10. Trong **Cơ hội**, nhấn Phân tích cơ hội; mở bằng chứng, review và ghi chú. Refresh chỉ đọc nguồn đã lưu, không gọi API. Đề xuất đã review giữ bằng chứng ở thời điểm review.
11. Chuyển sang Tracking: chọn keyword đã approved → chọn bộ/nhóm đích → Xem trước → kiểm tra action create/skip và URL → Xác nhận. URL chỉ chuyển khi mapping keyword approved; URL cluster không tự ghi đè keyword. Duplicates luôn skip trong Core; không sửa rank/URL/nhóm cũ.
12. Tab Dự án & cấu hình cho đổi tên, bối cảnh, ngưỡng cơ hội, sao chép, archive/mở lại hoặc xóa có xác nhận. Sao chép keywords/clusters/sources thành draft; snapshot và reviews giữ ở bản gốc.

Xuất keyword/cluster/competitor/opportunity theo CSV/XLSX/JSON; snapshot xuất JSON từ SERP Explorer. JSON keyword giữ nguồn/metrics và có thể nhập lại trong giới hạn mỗi lượt. CSV/XLSX báo cáo có cột sources JSON để giữ provenance; không phải bảng template nhập phẳng. Tệp lớn cần chia nhỏ trước khi nhập. Topical compatibility export chỉ là dữ liệu chuẩn bị, không phải Topical Map đã hoạt động.

Có thể hỏi AI Workspace “Phân tích Research, cluster và SERP đã lưu”. Agent chỉ đọc dữ liệu của website đang chọn; không tự phân nhóm/duyệt/transfer. Với nhiều Research projects, model có thể truyền research_id; local report mặc định dự án mới cập nhật. Dự án không gắn website chưa có hội thoại Agent riêng.
