# Quy tắc rank thủ công

| Nhập | DB state | DB value | Hiển thị |
|---|---|---|---|
|1…search depth|FOUND|Số nguyên dương|Số|
|NA|NOT_FOUND|null|NA|
|Rỗng/clear|NOT_CHECKED|null|—|

Không có rank 0, số âm, số thập phân hoặc NA=101. Search depth mặc định 100, profile cho 1–1000. Domain và Exact URL là hai phép đo khác nhau. Snapshot gồm keyword text, URL, mode, country, language, device, location và depth.

Tuần 1 bắt đầu ngày bộ đã chọn, Tuần n = start+7(n−1) đến start+7(n−1)+6. Địa phương theo timezone bộ, không lấy tuần ISO hiện tại làm Tuần 1. API hỗ trợ tới 520 tuần mà không đổi schema. GSC date range không quyết định ngày kiểm tra rank.

Timestamp exact lưu UTC; local date phải thuộc tuần được gán và không ở tương lai. Nếu chỉ biết tuần, người dùng phải chọn week_only hoặc nhập tệp; checked_at=null. Created_at là ngày nhập, không được trình bày như giờ kiểm tra.

Đại diện ô: bản ghi **lưu sau cùng** theo tuần/profile. Bản mới có thể correction hoặc clear; không xóa bản cũ. Cho phép nhiều observation cùng tuần. Đây là chính sách nhập/sửa, không phải lựa chọn rank tốt nhất hoặc timestamp quan sát lớn nhất.

## So sánh tuần liền trước

|Trước → Sau|Kết quả|
|---|---|
|20 → 8|Tăng 12|
|8 → 20|Giảm 12|
|10 → 10|Không đổi 0|
|10 → NA|Rời phạm vi; không có delta số|
|NA → 10|Vào phạm vi; không có delta số|
|NA → NA|Vẫn NA|
|Chưa kiểm tra → 10|Quan sát mới|
|10 → Chưa kiểm tra|Chờ kiểm tra|
|Khác snapshot query/URL/mode/profile|Khác chuỗi theo dõi; không tính delta|

Chỉ hai rank FOUND của tuần liền nhau cùng `series_key` mới tính `previous_rank-current_rank`. Không nhảy qua tuần trống để tạo tăng/giảm. Không cộng NA vào trung bình hoặc coi một lịch sử không kiểm tra là tăng hạng. Top 3 ⊂ Top 10 ⊂ Top 20. Tổng quan dùng keyword active; grid có thể lọc paused/archive riêng.

Biểu đồ đảo trục rank 1 ở trên, không nối qua NA/chưa kiểm tra. Các chuỗi khác nhau vẽ riêng, các tuần NA có nhãn. Không dùng GSC Average Position hoặc API search khác làm rank thủ công. Phương pháp Core là MANUAL; shortcut Google không tự xác nhận observation. Provider SERP sau này phải lưu method/provider/cost/confidence riêng, không ghi đè manual.
