# Nghiệm thu OpenAI Web Search / GEO trên máy cá nhân

**Trạng thái bàn giao: Pending Live Verification.** Code/mock/UI đã kiểm thử; chưa chạy OpenAI thật hoặc tiêu ngân sách API. Không đưa secrets vào chat. Cấu hình API key trong AI Settings/OS Vault và giá/model theo [setup](OPENAI_WEB_SEARCH_SETUP.md).

## Ba lượt đầu, xác nhận riêng từng lượt

1. Neutral informational: “Những tiêu chí nào cần xem xét khi lựa chọn xưởng may balo học sinh?”
2. Neutral commercial discovery: “Có những xưởng may balo theo yêu cầu nào tại Việt Nam?”
3. Một câu hỏi phù hợp website/đối thủ của bạn, giữ nguyên wording, không ép model giới thiệu brand hoặc cite domain của bạn.

Đây là prompt candidates, không phải observed user demand. Không chạy cả ba tự động; tạo preflight, xem giá/context và xác nhận từng lượt. Nếu permission/quota/model không phù hợp, dừng và kiểm tra OpenAI account. Không dùng browser scraping/consumer ChatGPT/SIWC fallback.

Với mỗi request, ghi: request ID, consent, response ID và status; model thật; search action/status có qualifying search; exact answer; native citation count và original metadata; retrieved sources riêng; requested country/language/city/region và actual applied location unknown nếu provider không xác nhận; token usage, estimate/unknown components/reservation; stored observation/extraction revision và QA quyết định.

Mở Observation Detail. Đọc toàn bộ answer, citation links/title/domain, raw annotations và Search Sources. Kiểm tra mention/alias, competitor, owned-domain attribution và ambiguous matches. Offsets chưa được verify thì chỉ dùng reference riêng. App không fetch citation content. Chọn confirmed/rejected/needs_review có lý do; đây là Human Reviewed, không là Source Content Verified. Rejected revision bị loại khỏi metric/GEO; re-extract tạo revision mới cần review lại.

Sau QA, mở GEO Finder, tùy chọn chỉ extraction đã xác nhận, chạy detect thủ công. Kiểm tra evidence gốc: retrieved-but-not-cited không được tạo Brand/Competitor Citation; missing metadata không thành zero; single competitor citation không chứng minh thị phần hoặc website tốt hơn. Agent giữ observed fact/hypothesis/counterevidence/missing info/action/verification riêng. Approval không publish/sửa website.

## Evaluation tiếp theo: 20–30 prompts

Chọn cho **một website**, gồm neutral discovery, commercial, informational, competitor-comparison, một ít brand-specific và các câu có thể không có brand. Đưa từng prompt vào Prompt Library với cohort/source/priority/locale, không coi generated candidate là nhu cầu đã quan sát. Người dùng tự duyệt từng paid request; v0.8.1 không có bulk run/scheduler.

Báo cáo số planned/collected, complete eligible, zero-citation, missing/partial/refusal/no-search/failed/unknown; provider/model/locale/grounding/measurement profile và review status. Không lấy planned sample làm mẫu số. Đánh giá citation parsing, mention matching, ownership, search execution/completeness, rule correctness và recommendation quality bằng rubric Phase 8. Ghi cả false positives/false negatives/abstentions; không extrapolate small fixture/live samples thành production-wide accuracy.

Chỉ gọi **Live Provider Verified** khi một request thật được chấp thuận đã thành công, search/citations/usage đã đối chiếu và observation lưu đúng. “Web Search Supported” trong app là capability đã quan sát ở response; human/content verification là mức riêng. Nếu chưa làm được, giữ Pending Live Verification, không dùng mock results để thay thế.
