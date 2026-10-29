# Dùng AI Workspace

## Cập nhật

Backup SQLite bằng `python scripts/backup_database.py`, rồi cập nhật code trong thư mục đang dùng. Chạy run-backend.bat và run-frontend.bat như trước. Migration 004 thêm dữ liệu Agent, không xóa dữ liệu SEO. Dependency không đổi; launcher mới vẫn dùng lại node_modules khi chỉ đổi version app.

## Phân tích ngay khi chưa có API key

1. Mở AI Workspace, chọn website/property hoặc dự án crawl.
2. Mở Ngữ cảnh & nguồn để xem ngày dữ liệu, bộ Keyword Tracking và nguồn còn thiếu.
3. Tạo hội thoại hoặc gõ câu hỏi rồi Gửi phân tích.
4. Mặc định “Báo cáo ngoại tuyến · không gọi AI”: dùng các quy tắc đọc dữ liệu lưu, không có LLM, không dùng token.
5. Mở các nút bằng chứng, xem metric scope, kỳ, tuổi và giới hạn; vào báo cáo gốc nếu cần.

Demo là mô phỏng, fixture là thử nghiệm. Với nguồn thật chưa sync/audit, hệ thống nói thiếu dữ liệu, không tự thay bằng demo. Topical Map hiện là placeholder, chưa thể phân tích topic mapping.

Ví dụ: “Phân tích hiệu suất SEO 28 ngày gần nhất”, “Tìm URL mất traffic”, “Keyword nào tụt hạng theo tracking tuần2”, “Điều tra URL https://website-cua-ban/trang/”. Chỉ đọc dữ liệu đã có, không tự tải website hoặc tìm web.

Kỳ GSC chọn 7/28/90 ngày, ngày kết thúc để trống dùng ngày lưu gần nhất. Câu hỏi nêu rõ 7/28/90 ngày sẽ chọn kỳ đó khi gửi; hỏi tiếp giữ kỳ trước. Khoảng dữ liệu cũ phải đọc kèm freshness, không tự coi là hiện tại. Tuần rank thủ công độc lập với kỳ GSC. URL đã nêu giữ trong hội thoại để hỏi tiếp “trang đó”.

## Dùng OpenAI

Xem [AI_PROVIDER_SETUP.md](AI_PROVIDER_SETUP.md). Key nhập tại terminal, không dán vào chat. Lưu model/giá/ngân sách, kiểm tra key/model và bật provider. Chọn OpenAI ở composer, xem ước tính, xác nhận gửi dữ liệu/chi phí, rồi Gửi. Mở trang hoặc đổi tab không tự gọi generation.

Model ứng dụng không phải tài khoản/model Codex. Cloud AI cần Internet. Giá hiện hành cần bạn xác minh; giá trong app là ước tính nhập thủ công, không phải hóa đơn. Không có thành công live được ngầm bảo đảm bởi tests mock.

## Đọc và review

Metric cards/bảng lấy từ backend; các đoạn AI là diễn giải hoặc giả thuyết. Citation hợp lệ không tự chứng minh kết luận đúng. Không coi giảm clicks là bằng chứng kỹ thuật gây giảm traffic nếu chưa điều tra.

Đề xuất có trạng thái Mới/Đang rà soát/Đã duyệt/Từ chối/Cần thêm bằng chứng, kèm ghi chú. Lưu review chỉ thay trạng thái, không thực hiện hành động SEO hoặc xuất bản. Không có automation trong Phase 6.

## Quản lý phiên

Danh sách chỉ thuộc website đang chọn. Đổi website mở ngữ cảnh riêng, không đổi project của hội thoại cũ. Lưu dấu sao, đổi tên, xem các trang tin cũ/mới. Xóa phiên cần xác nhận và phải chờ lượt active kết thúc. Hội thoại/evidence refs/recommendations của phiên bị xóa; SEO data không bị xóa, usage vẫn giữ để không reset ngân sách. Sao lưu SQLite nếu muốn giữ lịch sử đầy đủ.

## Lỗi thường gặp

- OpenAI đang tắt/thiếu key: dùng báo cáo ngoại tuyến hoặc cấu hình trong AI Settings.
- Không có OS keyring: không có plaintext fallback; dùng Windows Credential Manager trên máy cá nhân.
- Model chưa kiểm tra: nhấn Kiểm tra key/model; đây là GET model, chưa phải test generation trả phí.
- Context/tool/cost vượt giới hạn: thu hẹp câu hỏi hoặc điều chỉnh giới hạn có chủ ý. Không có vòng lặp không giới hạn.
- Provider timeout/quota: không tự gửi lại vô hạn. Xem usage unknown/dự phòng; không đoán rằng request chắc chắn miễn phí.
- Dữ liệu GSC/Technical/Rank thiếu: bổ sung qua module hiện có, rồi tạo lượt phân tích mới.
