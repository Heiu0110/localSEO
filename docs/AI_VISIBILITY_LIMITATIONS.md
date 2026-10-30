# Cập nhật v0.8.1

OpenAI Web Search adapter đã có, chỉ dispatch sau preflight/consent mỗi request. **Pending Live Verification**; giá/eligibility/Unicode conventions chưa được xác minh live, SDK schema đã đối chiếu. Gemini chưa triển khai. Search sources khác answer citations; source content chưa được app fetch/verify. Không scheduler/publishing. Xem [hướng dẫn live](OPENAI_WEB_SEARCH_SETUP.md), [chi phí](AI_VISIBILITY_COST_CONTROL.md), [parser limits](OPENAI_CITATION_PARSING.md).

Các phần v0.8 Core bên dưới là nền tảng manual/import và giới hạn lịch sử; availability mới của OpenAI được mô tả tại [báo cáo v0.8.1](PHASE8_1_COMPLETION_REPORT.md).

# Giới hạn v0.8 Core

- Nguồn khả dụng: manual observations, JSON/CSV response imports, CSV/JSON/XLSX prompts; Research/Tracking/Technical/GSC đọc dữ liệu đã lưu theo website. Có thể nhập prompt draft do AI đề xuất và gắn provenance; chưa có riêng batch prompt generator.
- OpenAI web search và Gemini grounding **not connected**. Phân tích payload đã nhập không đồng nghĩa có quyền gọi live provider. ChatGPT SIWC tiếp tục **Pending Live Verification**; login/inference entitlement không chứng minh web-search eligibility.
- Core không gọi consumer ChatGPT/Gemini, không scraping/ẩn danh bằng browser, không fetch URL citation, không hosted-MCP/tool workaround, không scheduler/automation/publishing.
- Citation metadata do nguồn cung cấp có thể thiếu/sai. “Confirmed attribution” chỉ là annotation/URL/domain/span hợp lệ trong nguồn; HTTP availability, content support và factual accuracy chưa được xác minh độc lập. User-supplied citation có nhãn riêng, không biến thành provider-confirmed citation.
- Rate là tỷ lệ trong tập quan sát, không traffic, AI market share hoặc AI ranking. Unknown context không chứng minh cùng context thực tế; quan sát cùng prompt không độc lập. Branded/neutral được tách. Bộ fixture nhỏ không suy rộng thành accuracy production.
- Rule là explainable candidate, không là causal diagnosis. Pattern guards không chứng minh mọi câu free text. Correct evidence ID vẫn cần human review; không hứa AI sẽ cite sau khi chỉnh nội dung.
- Chỉ liên kết SEO theo references/URL tường minh. Topical Map và dữ liệu nội dung website/đối thủ chưa nhập thì unavailable; không bịa bản đồ topic hoặc page content. Technical stale không xác nhận tình trạng hiện tại; GSC không đo AI visibility.
- Giữ local raw response để truy vết, không có auto-retention scheduler ở Core. Import tối đa 100 KiB/100 dòng; có trần 2.000 observations và 2.000 prompts/project. Backup/export trước quản lý dữ liệu; tuân thủ giấy phép/retention của bên cung cấp. Không nhập secrets/nội dung chưa được phép gửi cloud.
- Artifact reference không được dùng làm filesystem path; không đọc tùy ý. Imported HTML chỉ hiển thị text. Các request mở URL thủ công là quyết định của người dùng, app không tự fetch để xác minh.

v0.8.1 chỉ nên thêm OpenAI live adapter sau khi Core acceptance pass và xác minh docs, quyền provider/web search, provenance/citation completeness, consent/cost, retention, retries/cancellation. Gemini grounding đi sau với cùng capability contract. Không triển khai Phase 9/10/11 trong lượt Core này.
