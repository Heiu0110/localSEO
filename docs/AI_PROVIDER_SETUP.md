# OpenAI provider và ngân sách

Có hai phương thức kết nối riêng tới OpenAI: API Key Provider ở phần dưới và [Sign in with ChatGPT / ChatGPT Plan Usage](CHATGPT_CONNECTION_SETUP.md). SIWC dùng OAuth theo handoff ngày29/10/2026, model tài khoản và streaming riêng; eligibility/login thật còn Pending Live Verification, không tự fallback sang API key. Không phải quyền truy cập OpenAI của Codex, không tích hợp Sol/Astra giả vào API runtime.

## Model và giá

Model mặc định `gpt-4.1-mini`. ID được xác nhận có trong SDK chính thức ngày 29/10/2026:

- https://github.com/openai/openai-python/blob/main/src/openai/types/shared/chat_model.py
- https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_create_params.py
- https://github.com/openai/openai-python/blob/main/src/openai/types/responses/function_tool_param.py

Trang model/pricing OpenAI bị tunnel403 trong môi trường triển khai, nên **chưa xác minh được bảng giá hiện hành**. App không gán giá cố định. Mở https://openai.com/api/pricing/ để kiểm tra đúng model và loại request; nhập input/output USD mỗi1 triệu token và ngày kiểm tra. Giá đó luôn ghi “user estimate”. Account/model/capability vẫn phải xác minh với key thật; SDK listing không thay thế quyền của tài khoản.

## Lưu key trên Windows

Chạy backend launcher trước để có venv, rồi tại thư mục gốc:

```powershell
backend\.venv\Scripts\python.exe scripts\configure_ai_provider.py
```

Nhập key tại prompt getpass (ẩn). Không dùng key làm command argument hoặc biến môi trường, không dán vào chat. Script dùng OS-backed CredentialVault, namespace AI riêng với Google, không lưu key trong SQLite/file. Linux/macOS dùng `backend/.venv/bin/python scripts/configure_ai_provider.py`; cần keyring được mở khóa. Headless cloud không có keyring hợp lệ sẽ báo chưa hỗ trợ, vẫn dùng báo cáo ngoại tuyến.

Trong AI Settings: làm mới trạng thái key, nhập/lưu model và giá ước tính, nhấn Kiểm tra key/model, rồi bật OpenAI và lưu. Kiểm tra dùng GET `/models/<model>` không yêu cầu sinh nội dung trả phí; chỉ xác minh model/key có quyền, chưa chứng minh mọi schema/tool capability.

Trong composer: chọn OpenAI → nhập câu hỏi → Xem ước tính → xác nhận dữ liệu gửi ra ngoài/chi phí → Gửi. Lượt chat thật đầu tiên mới kiểm chứng Responses/tool/schema và có thể tính phí. Không có request AI nền hoặc API credit dùng trong tests.

Xác nhận gắn với model và trần chi phí đã xem. Đổi model hoặc tăng giá/giới hạn làm vượt trần sẽ yêu cầu xem ước tính mới. Nếu cấu hình thay đổi khi lượt đang chạy, app dừng trước request trả phí tiếp theo.

## Usage và giới hạn

Tokens input/output lưu đúng usage provider nếu trả về; thiếu usage giữ unknown. Dollar cost chỉ tính từ giá đã cấu hình, không phải số tiền provider báo. Không tự giả định cached-input discount hoặc billing price chính xác.

Trước từng call, dự phòng theo giới hạn input UTF-8 bytes + protocol margin và output token cap. Mỗi lượt giới hạn tool/call/context; ngân sách ngày theo Asia/Ho_Chi_Minh. Request completed thay dự phòng bằng ước tính theo token thực; timeout/usage thiếu giữ dự phòng. Không tự retry timeout/5xx để tránh tính phí trùng.429 chỉ thử lại một lần với Retry-After≤2 giây.

Giới hạn ứng dụng là ngân sách **ước tính theo giá nhập**, không phải hard billing cap phía OpenAI. Cấu hình thêm giới hạn tại tài khoản provider nếu cần. Unknown usage không được coi là miễn phí. Xóa hội thoại không xóa usage để làm mới ngân sách.

Tắt provider bằng checkbox trong AI Settings, chặn request mới kể cả lượt đang chờ. Request đã gửi có thể vẫn hoàn tất/tính phí. Đổi model làm mất dấu kiểm tra model, cần test lại. Xóa key:

```powershell
backend\.venv\Scripts\python.exe scripts\configure_ai_provider.py --remove-key
```

Live OpenAI, model permissions, pricing hiện hành và Windows keyring của người dùng là **Pending Credentials / Pending Live Verification**. Không yêu cầu gửi key trong cuộc trò chuyện Codex này.
