# Bằng chứng của Agent

Mỗi kết quả tool có evidence_id, project_id, source_type/name/record_id, metric_scope, date_start/end, collected_at, retrieved_at, data_freshness, completeness, value_summary, source_reference và limitations.

- collected_at lấy từ nguồn; thiếu thì null, không gán giờ hiện tại như giờ thu thập.
- retrieved_at là giờ Agent đọc dữ liệu.
- age_days mô tả tuổi thu thập; reporting_lag_days mô tả ngày kết thúc báo cáo cách hiện tại.
- Snapshot quá 14 ngày hoặc reporting window trễ quá 7 ngày được đánh dấu stale; đây là ngưỡng cảnh báo ứng dụng, không phải quy tắc Google.
- Query/page details là tập có thể bị lọc/giới hạn. KPI chỉ lấy site/byProperty. Position/CTR khi không có mẫu số phù hợp là unknown, không phải rank0.
- Demo/fixture có source_type riêng, không được kết luận như dữ liệu website thật.
- Rank MANUAL giữ tuần, mode, URL và Search Profile. NA không phải unchecked hoặc position101.

UI render metric cards từ dữ liệu backend và mở bảng/chi tiết trong drawer bằng chứng. Diễn giải AI được ghi nhãn riêng. Mỗi finding/recommendation phải dẫn IDs của lượt hiện tại; không cho model tự tạo link hoặc citation. Source links do backend dựng, frontend chỉ mở các route báo cáo allowlist, không render HTML tùy ý.

Summary evidence có giới hạn dòng/byte, không phải bản sao đầy đủ dataset. Dữ liệu gốc có thể thay đổi/bị xóa sau phân tích; evidence là tóm tắt tại lúc đọc, không phải bằng chứng nguồn còn tồn tại vĩnh viễn. Mở báo cáo gốc để kiểm tra lại.

Một citation hợp lệ chỉ xác minh ID đã được đọc, không chứng minh mọi câu AI viết là đúng hoặc chứng minh quan hệ nhân quả. Khi thiếu dữ liệu, analyst phải nêu giới hạn và đề xuất thu thập thêm; không suy diễn số liệu.
