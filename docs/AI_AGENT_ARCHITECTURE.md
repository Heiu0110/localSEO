# AI Agent Foundation — Phase 6

AI Workspace mở rộng app localhost hiện có. Chỉ triển khai Phase 6; không nghiên cứu SERP/web, không publishing/CMS/social/GBP và không chạy AI nền.

## Hiện trạng đã kiểm tra

Dashboard/MockProvider, SQLite GSC, OAuth, Technical SEO và Keyword Tracking có code và tests hoạt động. Topical Map chỉ là route placeholder; chưa có topic–keyword–URL store hoặc service. Agent báo thiếu nguồn, không đăng ký tool Topical Map giả. Không viết lại các module đã ổn định.

## Ranh giới

`AIWorkspacePage → /api/ai → AIManager → ToolRegistry → dịch vụ SEO hiện có`

`AIManager → OpenAIProvider → https://api.openai.com/v1/responses` chỉ khi người dùng gửi với consent.

Ba chế độ (bổ sung SIWC sau Phase7 Core):

- `local_report`: bộ quy tắc dựng báo cáo từ tool outputs. Chạy ngoại tuyến, không có mô hình AI, không tiêu token.
- `chatgpt`: OAuth SIWC open-source/locally hosted, PKCE/dynamic registration/OS vault, model tài khoản và Responses SSE; [live eligibility và login còn pending](CHATGPT_CONNECTION_SETUP.md).
- `openai`: provider API key, có model/giá ước tính/ngân sách cấu hình được, key trong OS keyring. Không sử dụng tài khoản/model Codex của phiên phát triển.

Route AI tải riêng; không thêm dependency JS/Python. Mở Dashboard hoặc AI Workspace không tạo request sinh nội dung. Worker AI chỉ được gọi từ POST message, độc lập với worker GSC/audit/keyword.

## Tool execution và ngữ cảnh

Mỗi hội thoại giữ project_id bất biến. Project catalog tái sử dụng demo sites, GSC properties và dự án crawl độc lập; các nguồn không liên kết không được tự gộp theo suy đoán. Audit-only project có ID `audit:<project-id>`. Tool arguments không có project_id; backend lấy scope từ hội thoại. Keyword/set/profile/audit đều được kiểm tra ownership.

Registry có Pydantic input/output, version, read_only, timeout 5 giây, kết quả tối đa 8.000 UTF-8 byte. Hai worker đọc có semaphore để không xếp hàng không giới hạn. Timeout trả lỗi sớm; không thể giết một câu SQL/read thread đang chạy, nhưng thao tác chỉ đọc, query được giới hạn và slot chỉ được trả sau khi tác vụ thực kết thúc.

Mặc định tối đa 6 tool/lượt, trong đó có context ban đầu; tối đa 8. Tool GSC kế thừa kỳ đã chọn; yêu cầu kỳ khác bị chặn để tránh trộn báo cáo. Kỳ manual rank là tuần/profile riêng. Khi UI nhận câu hỏi có 7/28/90 ngày rõ ràng, gửi kỳ đó; hỏi tiếp giữ kỳ trước. URL được nhắc trong hội thoại giữ cho bước điều tra tiếp theo, không tự truy cập URL.

API Key Provider dùng Responses API không stream, store=false, parallel_tool_calls=false, JSON schema. Context/history ngắn và tổng payload có giới hạn byte. Tool loops bị giới hạn; kiểm tra ngân sách/thời gian trước request tiếp theo. HTTP đang chạy có timeout riêng, nên mốc 90 giây của orchestration không phải deadline cứng cho request đang truyền.

## Grounding

Số liệu và bảng chính thức được backend lấy/tính; không nhờ LLM cộng raw rows. AI chỉ tạo diễn giải/giả thuyết/đề xuất theo schema và phải dẫn evidence IDs đã phát hành trong lượt hiện tại. Citation không có thật bị chặn. Citation có thật không tự chứng minh diễn giải đúng; UI luôn nhắc kiểm tra. Không thể bảo đảm LLM không viết một nhận định sai ngữ nghĩa dù citation hợp lệ; human review vẫn cần thiết.

Bằng chứng chỉ lưu tóm tắt hữu hạn và ref, không sao chép toàn bộ GSC/crawl dataset. Review chỉ ghi ai_recommendations, không gọi Technical backlog hoặc external writes.

## Tệp chính

- Backend: `app/ai/{context,tools,provider,agent,schemas,models,common}.py`, `app/api/ai_routes.py`.
- Migration: `004_ai_agent` thêm 6 bảng; không sửa/xóa SEO tables.
- Frontend: `features/ai`, `services/aiApi.ts`, `types/ai.ts`, `styles/ai.css`.
- Cấu hình key tại terminal: `scripts/configure_ai_provider.py`.
