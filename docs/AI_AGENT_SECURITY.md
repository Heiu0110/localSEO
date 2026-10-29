# Ranh giới an toàn Phase 6

Agent không có công cụ sửa website, SQL tự do, shell, filesystem, publishing hoặc gọi endpoint tùy ý. Tools là service methods chỉ đọc, project scope do server lấy từ hội thoại; các argument project_id/sql/file_path không hợp lệ bị chặn.

Tiêu đề HTML, URL, dữ liệu import, câu trả lời cũ và tool output là dữ liệu không tin cậy. System policy nói rõ đây không phải chỉ dẫn. Bảo vệ thực thi nằm ở registry/ownership/budget/schema, không phụ thuộc việc LLM luôn nghe lời. Tests đưa chỉ dẫn độc hại vào title crawl rồi mô phỏng model đòi SQL: tool bị chặn, SEO data không thay đổi. Chưa có External Research tool; yêu cầu loại này bị từ chối.

API dùng chung TrustedHost/Origin/CORS/CSRF, Content-Length và giới hạn128 KiB của app. AI routes trả lỗi validation an toàn, không echo input chứa secret. Key không có field trong API/UI. API key nhập bằng getpass ở terminal, chỉ lưu OS-backed CredentialVault hiện có, namespace riêng AI. Không có file/SQLite/environment fallback. Không đọc Google tokens vào context.

Redaction nhận diện key/token phổ biến và các field bí mật trước lưu message/evidence/tool summaries. Đây không phải bộ phát hiện mọi loại secret được mã hóa tùy ý; người dùng không nên dán credential vào câu hỏi hoặc dữ liệu website.

OpenAI HTTPS host cố định, không cho base_url tùy ý, không follow redirect, trust_env=false; key chỉ ở Authorization header backend. HTTP response/timeout bị giới hạn. Provider errors không echo raw provider payload/headers. Generated content là JSON schema render bằng React text/components, không dangerouslySetInnerHTML.

Mỗi lượt có idempotency key. Gửi lại cùng lượt không tạo generation mới; dùng key cho câu hỏi khác bị từ chối. Một lượt active/hội thoại, tool/call/context budgets, daily cost reservation. Không auto retry request timeout/5xx có thể đã tính phí;429 chỉ retry một lần với Retry-After ngắn. Usage không xác định giữ dự phòng. Không replay job bị ngắt khi khởi động lại.

Xác nhận gửi OpenAI gắn với model và trần ước tính người dùng vừa xem. Nếu model hoặc giá/giới hạn thay đổi làm vượt trần, server yêu cầu xem lại ước tính trước khi tạo lượt. Thay đổi cấu hình giữa lượt chặn các request trả phí tiếp theo; request đã gửi có thể vẫn được tính phí.

Review statuses chỉ ghi ai_recommendations. Approved không tạo backlog Technical SEO hoặc bất cứ external write nào. Không có execution hook cho automation sau này.

Giới hạn: semantic hallucination/prompt injection vẫn có thể ảnh hưởng diễn giải; citation validation không phải proof of correctness. Human review và mở nguồn gốc vẫn cần thiết. Tool timeout không giết thread SQL đang chạy, chỉ trả lỗi và giữ slot đến khi tác vụ thực kết thúc. Windows keyring/API thật chưa được chạy trong tests cloud.

SIWC bổ sung authentication tách biệt, state/nonce/PKCE, JWKS/RS256 validation và refresh rotation trong OS vault. Không đọc Codex credentials, không dùng API key dự phòng; models lấy theo quyền tài khoản. Xem [thiết kế callback, token và SSE](CHATGPT_CONNECTION_ARCHITECTURE.md). Eligibility/license không được suy ra từ repository public hoặc checkbox; chủ sở hữu cần review trước live OAuth.
