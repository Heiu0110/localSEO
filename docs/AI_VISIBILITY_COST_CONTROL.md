# Chi phí, consent và recovery

Không có giá mặc định được tuyên bố là current pricing. Cần input/output model rate, tool USD/1000calls và ngày bạn kiểm tra. Search-content billing có ba trạng thái: giả định đã gồm trong reported input; tính thêm theo allowance; hoặc unverified. Token allowance là giả định có thể chỉnh, không là một mức phí cố định cho mọi model.

Preflight hiển thị model/provider, exact prompt/context, tool config/max calls, input/output token assumptions, model/tool estimates, known components, total estimate hoặc Unknown, unknown components, pricing source/date/notes và authorized reservation. Tổng token-only không được coi là total search cost. Thiếu mandatory price component thì chặn preflight. Unknown search-content billing cần checkbox riêng và reservation được người dùng chấp thuận.

Reservation cap là chính sách của app, **không là provider-side USD billing cap**. max_tool_calls/max_output_tokens giới hạn cấu hình kỹ thuật, không bảo đảm tiền OpenAI thu sẽ không vượt dự phòng. Search tokens/billing rules có thể khác giả định. Không gửi lời cam kết giá tuyệt đối.

Consent được gắn request ID + binding hash của project/website, prompt identity/revision/text, model/tool/instruction config, requested locale, pricing, cap và private credential fingerprint. Không lưu key. Public API bỏ fingerprint. Config/prompt/project/key đổi hoặc quá10 phút cần preflight mới. Adapter so fingerprint ngay trước tạo Authorization để không dùng một account/key mới dưới consent cũ.

Một active request trong DB. Double click/retry cùng request/receipt trả request đã có, không dispatch lại. Request key unique trong project. Hủy chỉ chắc chắn trước dispatch. Không retry Responses POST, kể cả429; không chuyển sang SIWC hay một provider khác.

Usage lưu trong **ai_usage_records sẵn có**, liên kết collection request; không thêm ledger thứ hai và không double count. Ngân sách API ngày (UTC+7 theo ledger hiện có) dùng chung Agent: `spent_today` gồm các estimated costs hoặc reservation khi chưa rõ. Effective limit là min(Visibility limit, AI Settings limit). Visibility có explicit enable riêng; không tự bật AI chat.

Sau trả lời: ghi response ID/model, actual token counts khi hợp lệ, số native web_search_call/actions, estimated model/tool/total theo giả định đã chọn. Provider không trả actual dollar cost: `provider_reported_dollar_cost=null`. Thiếu usage, actual model khác pricing đã cấu hình hoặc search-content billing chưa xác minh thì total Unknown và giữ reservation. Parser lỗi vẫn giữ token counts hợp lệ quan sát được, không bịa USD. Counter ngoài trần chẩn đoán 1 tỷ không được đưa vào Decimal/float/SQLite arithmetic; phần đó giữ Unknown và nằm trong raw diagnostic nếu an toàn. Các dữ liệu vẫn nằm trong raw diagnostic khi an toàn.

Raw response/usage commit trước ingestion. Nếu lưu observation thất bại, request thất bại có diagnostic và usage đã ghi; không reissue. Timeout/connection reset/oversize/invalid JSON sau dispatch là UNKNOWN_REMOTE_OUTCOME và giữ reservation, không suy ra “chưa tính phí”. HTTP rejection không tạo success/zero-cost giả. Khi restart: queued chưa gửi thành INTERRUPTED và giải phóng reservation; đã dispatch thành unknown, không tự replay. `store=false` không được coi là quyền retrieve/recover response qua API.

Nhấn lại để chạy một **preflight mới** là chấp thuận một yêu cầu mới, có thể bị tính phí thêm. Thử nghiệm bằng mocks không xác minh giá, hạn mức hoặc billing thật. [Quy trình kiểm chứng](GEO_LIVE_VERIFICATION.md).
