# Metrics và mẫu số

Đơn vị cơ bản là một observation hợp lệ, đầy đủ, không bị supersede và thuộc scope đã chọn. Invalid/partial/missing-time khi lọc ngày được loại kèm reason. Brand không xuất hiện trong một mẫu chỉ là “không quan sát thấy trong tập mẫu này”. Không có AI ranking score, market share hoặc correlation→causation.

Mỗi cohort được khóa bởi provider, model, country, language, location, grounding, prompt cohort và collection method. Model/locale thiếu là Unknown; việc cùng Unknown không chứng minh cùng context thực tế. Báo cáo giữ riêng các group, không tạo tỷ lệ tổng gộp provider/model. Phạm vi ngày dùng ngày UTC sau chuẩn hóa timestamp timezone; thời gian import không thay thế thời gian quan sát.

| Metric | Tử số | Mẫu số |
|---|---|---|
| Brand Mention Rate | observations có ≥1 CONFIRMED_MATCH của brand | eligible observations trong cohort |
| Brand Citation Rate | observations có ≥1 citation xác nhận ownership brand | eligible observations có citation-capable, metadata complete và extraction không cảnh báo |
| Competitor rates | cùng phép đo theo đối thủ | cùng cohort + điều kiện mẫu số tương ứng |
| Prompt coverage | active prompt khác nhau có observation phù hợp | active prompts thuộc intent/category/effective cohort được chọn |

Một response có nhiều alias không tăng mention numerator nhiều lần. Branded prompt được phát hiện theo registry tại ingest và snapshot riêng; không tự nhập vào neutral discovery. Prompt coverage dùng registry hiện tại để nhận diện cohort và cần đọc cùng lịch sử cấu hình.

Unknown/not-supported/missing/partial citation metadata không được biến thành zero. Complete capable zero citations có denominator=1, numerator=0. Annotation sai domain/span/structure hoặc parsing bị giới hạn thì không đủ điều kiện làm citation denominator. Rate denominator=0 hiển thị Unknown, không 0%.

Citation occurrences, unique normalized URLs và observations containing domain là ba số riêng. URL normalization giữ query parameters và reserved encoding; chỉ loại fragment/default port và chuẩn hóa host/unreserved encoding. URL thường trong prose nằm ở URL mentions, không ở citation count. Citation trong nguồn provider không chứng minh HTTP availability, factual accuracy hoặc source content hỗ trợ claim.

Các báo cáo nêu số quan sát/prompt, citation denominator, missing metadata, unknown capability, context và sample caveat. Quan sát cùng prompt nhiều lần không được coi là các nguồn độc lập. GSC site/byProperty totals, query/page rows, manual rank và SERP snapshots là context SEO riêng; không đổi chúng thành AI visibility hoặc AI traffic.
