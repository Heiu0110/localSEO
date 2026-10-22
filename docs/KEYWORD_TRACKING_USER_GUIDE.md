# Hướng dẫn theo dõi từ khóa

## Nâng cấp và mở ứng dụng

1. Sao lưu: `python scripts/backup_database.py` tại thư mục dự án.
2. `git pull`, chạy `run-backend.bat`, rồi `run-frontend.bat` trong hai terminal.
3. Mở http://127.0.0.1:5173 → **Theo dõi từ khóa**. Launcher tự nâng schema và chỉ cài dependency khi lock thay đổi.

Dashboard, demo, GSC và Technical SEO vẫn hoạt động. Core không yêu cầu OAuth để quản lý từ khóa hoặc nhập rank. Demo website không có số liệu GSC giả; property thử nghiệm luôn ghi nhãn.

## Tạo bộ và thêm từ khóa

Chọn Website → Bộ từ khóa mới. Đặt tên, ngày bắt đầu Tuần 1 và múi giờ. Mặc định đề xuất thứ Hai hiện tại nhưng bạn có thể chọn ngày khác; ứng dụng không tự đổi ngày đã chọn. Mỗi tuần 7 ngày.

Trong Cấu hình, thêm nhóm với tên/màu tùy ý. Tại Bảng theo dõi → Thêm từ khóa, nhập keyword tiếng Việt, nhóm, URL đích, ưu tiên, intent, trạng thái và ghi chú. URL hợp lệ mặc định dùng Exact Target URL; không có URL dùng Domain. Bạn có thể đổi mode rõ ràng.

- **Exact Target URL:** chỉ ghi FOUND khi đúng landing page xuất hiện. Homepage lên hạng không thay thế URL đích.
- **Domain / Property:** ghi vị trí organic đầu tiên phù hợp website.

Tìm kiếm theo keyword hoặc URL; lọc nhóm/trạng thái/rank/GSC; sắp xếp keyword, click, impression, GSC Position, rank tuần hoặc biến động. Các bộ lọc giữ khi chuyển tab hoặc mở drawer. Chọn nhiều dòng để đổi nhóm, trạng thái, ưu tiên hoặc URL. Archive giữ lịch sử; xóa yêu cầu xác nhận.

Drawer cho sửa keyword, xem mọi observation theo trang, biểu đồ rank và bằng chứng Technical SEO đã lưu. Chuyển từ khóa kèm lịch sử sang bộ cùng lịch/múi giờ trong drawer; bộ khác lịch cần quy trình export/import rõ ràng.

## Kiểm tra tuần

1. Chọn Search Profile và tuần. Xem khoảng ngày tuần trong header/tooltip.
2. Lọc Chưa kiểm tra hoặc mở tab Kiểm tra tuần.
3. Mở Google Search, dùng cửa sổ riêng tư nếu cần. Shortcut chỉ mở tab thường; country/language không bảo đảm vị trí chính xác.
4. Đếm kết quả organic web, loại quảng cáo, Local Pack, Shopping và bản thân AI Overview. Thay đổi vị trí/thiết bị có thể thay đổi kết quả.
5. Nhập số nguyên 1–độ sâu profile (mặc định 100), hoặc NA khi đã kiểm tra hết phạm vi mà không thấy.
6. Lưu và tiếp tục. Không nhấn lưu chỉ vì vừa mở trang Google: ứng dụng không tự quan sát SERP.

**—** là chưa kiểm tra; **NA** là đã kiểm tra nhưng không tìm thấy. Không điền 0 cho hai trạng thái này.

Trong grid, click ô → nhập → Enter lưu; Escape hủy; Tab/Shift+Tab lưu và sang ô kế/trước; phím mũi tên di chuyển khi không nhập. Nút NA/Xóa đặt giá trị nhưng vẫn cần Lưu. Mọi lần lưu giữ các bản cũ; số nhỏ bên rank cho biết nhiều quan sát.

Ngày kiểm tra mặc định là hiện tại. Nhập timestamp lịch sử bằng ô “Thời điểm kiểm tra” (giờ máy, sau đó lưu UTC). Nếu chỉ biết tuần, chọn **Nhập lịch sử: chỉ biết tuần**; không tự bịa giờ kiểm tra. Với paste nhiều tuần lịch sử, chọn chế độ này trước. Dán khối tab/newline vào ô → xem trước → xác nhận. Batch lỗi không ghi một phần.

## Đọc kết quả

Tổng quan tính trên keyword active của bộ/profile/tuần. Top 3 nằm trong Top 10 và Top 20. Tăng/giảm chỉ so tuần liền trước và cùng chuỗi đo. NA không cộng vào trung bình rank. “Vào phạm vi”, “Rời phạm vi”, “Quan sát mới” và “Khác chuỗi” là trạng thái riêng, không phải delta số.

Biểu đồ drawer đảo trục: vị trí 1 ở trên. NA/chưa kiểm tra làm đứt đường; các tuần NA có nhãn riêng. Khi URL/query/profile thay đổi, đường được tách chuỗi.

## GSC

Chọn property đã thêm trong Settings, rồi chọn kỳ 7/28/90 ngày hoặc ngày tùy chỉnh, chọn phạm vi và Sync. Kỳ GSC độc lập với tuần rank. Query toàn property và Query theo URL đích không đồng nghĩa. Cache hiển thị ngoại tuyến; xem nguồn/thời điểm trong drawer. Không có row có thể do privacy hoặc giới hạn API, không phải bằng chứng không có nhu cầu tìm kiếm.

Chỉ báo CTR thấp có ngưỡng impression/CTR chỉnh trong cấu hình bộ; đó là tín hiệu để xem xét, không phải yêu cầu tự động viết lại title. URL GSC khác URL đích không tự thay mapping, không được kết luận cannibalization.

## Giới hạn và bước tiếp theo

Chưa có automatic SERP, lịch chạy nền định kỳ, screenshot evidence hoặc mở Chrome ẩn danh từ backend. Live Google và native Windows cần kiểm chứng trên máy đã cấu hình; mọi test tự động dùng fixtures/mock thay credentials thật. Không cần cấu hình Google để thử các luồng rank và import/export.
