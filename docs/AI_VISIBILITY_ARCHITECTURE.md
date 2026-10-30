# AI Visibility · v0.8 Core

Luồng: website hiện có → Visibility project → registry/prompt → manual/import preview → immutable observation → extraction revision → cohort metrics → deterministic candidates → existing AI Workspace → verifier → human review.

`backend/app/visibility` giữ nghiệp vụ; `api/visibility_routes.py` dùng Runtime/SQLite, CSRF và localhost boundary hiện có. Frontend `/ai-visibility` lazy-load, dùng React Query, Sheet, Button và palette trắng/xám/đen hiện có. Dashboard, Analytics Providers, crawler, rank và Research không bị thay bằng dữ liệu Visibility.

Không có queue thu thập live, crawler citation hoặc AI provider mới. Native annotations OpenAI và Gemini grounding support→chunk được phân tích từ payload người dùng nhập. `PROVIDER_API` chỉ là provenance khai báo của dữ liệu nhập, không chứng minh LocalSEO đã gọi API.

AI integration đăng ký 9 read-only tools vào ToolRegistry sẵn có. Lượt GEO khóa website + visibility project + opportunity, seed bounded evidence packet, giữ consent/model/cost/history/review và credential vault cũ. Agent ngoại tuyến vẫn hoạt động. Không gắn kết quyền web-search/grounding với việc đã login ChatGPT.

Giới hạn Core: 100 project, 2.000 prompt và 2.000 quan sát/project; import 100 dòng/100 KiB, preview 30 phút; tối đa 500 candidate/lượt, list phân trang. Kết quả tool ≤8.000 byte; vượt giới hạn thì trả lỗi rõ ràng, không tự gửi toàn bộ dataset ra ngoài. Không thêm dependency frontend/backend.

Nguồn đã lưu được liên kết bằng reference/URL đích tường minh. GSC là dữ liệu Google Search, không là AI traffic. Technical evidence giữ ngày/tuổi, >30 ngày hoặc không biết ngày là stale. Nguồn document/identity/coverage là context hiện tại có provenance riêng, không được coi tự động đồng thời hoặc nhân quả với observation cohort.

Xem [hướng dẫn](AI_VISIBILITY_USER_GUIDE.md), [data model](AI_VISIBILITY_DATA_MODEL.md), [metrics](AI_VISIBILITY_METRICS.md), [engine](GEO_OPPORTUNITY_ENGINE.md), [verification](GEO_EVIDENCE_VERIFICATION.md), [Agent](GEO_AGENT_INTEGRATION.md), [limits](AI_VISIBILITY_LIMITATIONS.md).

## v0.8.1 provider extension

`provider_contracts.py` mở rộng envelope normalized candidate + raw response/actions/sources/usage; `OpenAIWebSearchVisibilityAdapter` là implementation đầu tiên. Ba bảng migration007, dùng chung AI usage ledger và OS Vault. Model/eligibility live không suy ra từ credential presence/GET model hoặc SIWC. Xem [contract/security](AI_VISIBILITY_LIVE_PROVIDER.md), [state/financial safety](AI_VISIBILITY_COST_CONTROL.md), [acceptance](GEO_LIVE_VERIFICATION.md).
