# AI Visibility live provider · v0.8.1

Luồng mới nằm trong **AI Visibility → AI Search**, không thay Phase 8 Core: chọn đúng một prompt → kiểm tra model access → preflight cục bộ → consent gắn request → một POST Responses/Web Search → parser → `core.ingest` → extraction/metrics/GEO/human review hiện có. Không tự chạy khi mở trang, không lịch/batch monitoring hoặc publishing.

## Hợp đồng được đối chiếu

Ngày 30/10/2026, các trang guide Web Search, bản Markdown, API reference và pricing OpenAI đều bị CONNECT Tunnel403 trong môi trường phát triển. Không tuyên bố đã xác minh nội dung live của các trang đó. Đã lấy và đọc nguồn SDK OpenAI chính thức tại commit [`05992039b9f7b78a48cf1e5a35727ba27d96db6e`](https://github.com/openai/openai-python/tree/05992039b9f7b78a48cf1e5a35727ba27d96db6e/src/openai/types/responses), cụ thể:

- `web_search_tool_param.py`: type `web_search`, external_web_access, search_context_size và approximate user_location. Chỉ gửi `{type: approximate}` khi không chọn địa điểm để tránh fallback US nêu trong SDK.
- `response_create_params.py`: input, tools, tool_choice, max_tool_calls, max_output_tokens, store và include `web_search_call.action.sources`.
- `tool_choice_options.py`: `required` được hỗ trợ. Chỉ khai báo một tool Web Search; không dựa vào auto.
- `response_function_web_search.py`: native call/status, search/open_page/find_in_page và source list.
- `response_output_text.py`: output_text + annotation URL/title/start/end.

Model access, tool/account eligibility, current prices và quy ước Unicode/end-index **chưa được xác minh live**. Không hardcode runtime model là Sol/Astra hoặc suy ra Web Search từ tên model. GET model chỉ là metadata/access check; một lượt search được người dùng chấp thuận mới xác minh search thực sự chạy.

## Kiến trúc và dữ liệu

Mở rộng `ProviderCapabilities`/`LiveVisibilityAdapter` hiện có. Adapter trả envelope gồm raw response và candidate đã chuẩn hóa, actions/sources/usage; manager lưu qua `core.ingest`. Không có Agent/provider credential stack mới. API key lấy từ `ai.openai.api_key` trong OS Vault có sẵn; không đọc ChatGPT tokens.

Migration007 thêm **3 bảng** `visibility_collection_requests`, `visibility_collection_consents`, `visibility_search_sources`. Usage dùng **ai_usage_records hiện có**, với `operation_type=visibility_web_search`, message_id=null và request link; không ghi trùng vào một bảng usage khác. Tổng API spend/reservation dùng chung ledger và lock với Agent; SIWC quota không đổi sang USD.

Request lưu prompt/context/config/pricing snapshot, private credential fingerprint, binding hash, expiration, status, consent, dispatch timestamp, observation/usage links và raw diagnostics an toàn. Public API không trả credential fingerprint hoặc key. Một active_slot unique toàn DB và executor một worker ngăn hai collection trả phí cùng lúc theo mặc định.

State: PREFLIGHT_READY → QUEUED → RUNNING → COMPLETED/PARTIAL/FAILED/UNKNOWN_REMOTE_OUTCOME. Consent receipt là sự kiện xác nhận, lưu nguyên vẹn. Có cancel trước dispatch và INTERRUPTED khi restart trước gửi. Sau dispatch không khẳng định có thể hủy từ xa. Restart không reissue; unknown outcome giữ reservation. Preflight hết hạn sau10 phút hoặc prompt/project/config/key thay đổi phải tạo lượt mới. Adapter kiểm tra lại credential fingerprint ngay trước tạo Authorization để không dùng nhầm key/account sau consent. Prompt queued/running không được sửa; patch/confirm dùng chung lock để metadata không đổi giữa lúc đã duyệt và lưu kết quả. Có thể hủy trước dispatch hoặc chờ hoàn tất rồi sửa.

## Network/security

POST duy nhất tới `https://api.openai.com/v1/responses`, HTTPS cố định, trust_env=false, follow_redirects=false, không retry. HTTP timeout45s (connect8s), deadline kiểm tra streaming body60s, response≤256KiB. JSON phải là object, không duplicate keys/NaN/lone surrogate. Error detail từ provider không được echo. Native payload chứa secrets bị quarantine và không lưu plaintext. Giới hạn Core: response text30.000 ký tự, observation metadata30KB; quá giới hạn không bịa dữ liệu thay thế.

Citation/source URL chỉ là dữ liệu: HTTP(S), không credentials, chặn localhost/private IP kể cả legacy numeric IPv4; không DNS/crawl/fetch nguồn. HTML hiển thị escaped text, external links có noopener/noreferrer. Không có tool thực thi từ web content. Artifact không là đường dẫn file.

Provider response live được giữ nguyên; không sửa qua correction endpoint. Sửa nhận diện bằng registry/review/re-extract hoặc nhập một observation thủ công riêng. Review từ chối loại revision khỏi metric/GEO; chọn “Chỉ dùng extraction được xác nhận” để lọc evidence đã review. Approval không chứng minh nội dung nguồn hoặc thực thi website changes.

Xem [setup](OPENAI_WEB_SEARCH_SETUP.md), [parser](OPENAI_CITATION_PARSING.md), [chi phí](AI_VISIBILITY_COST_CONTROL.md), [live QA](GEO_LIVE_VERIFICATION.md).
