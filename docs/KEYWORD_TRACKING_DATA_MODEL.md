# Dữ liệu Keyword Tracking

Migration `003_keyword_tracking` thêm 10 bảng; không sửa hoặc xóa bảng GSC/Technical. Nâng cấp bằng launcher backend như trước. Sao lưu SQLite trước khi nâng cấp.

| Bảng | Vai trò |
|---|---|
| keyword_sets | Website ổn định, property FK tùy chọn, tên, lịch local, timezone, trạng thái, ngưỡng CTR |
| keyword_groups | Nhãn/màu riêng từng bộ |
| tracked_keywords | ID ổn định, display text, normalized keyword, nhóm, URL đích, mode, ưu tiên, intent, trạng thái, ghi chú |
| tracking_weeks | Số tuần và ngày bắt đầu/kết thúc; unique theo bộ + số tuần |
| search_profiles | Tên, Google, country/language/location/device/search depth/organic web |
| keyword_rank_observations | Append-only: rank state/value, tuần/profile FK, checked_at UTC hoặc null week-only, snapshot profile/query/URL/mode và ghi chú |
| keyword_gsc_metrics | Cache riêng theo keyword, scope, kỳ và hash exact query/URL |
| keyword_gsc_jobs | Hàng đợi và tiến độ, snapshot danh sách query/URL, lỗi an toàn |
| keyword_import_jobs | Tên tệp đã làm sạch, preview, dữ liệu gốc/metric lịch sử, lỗi và kết quả commit |
| keyword_tracking_activity | Tạo/sửa keyword, rank, chuyển bộ, import và đổi cấu hình |

Không có 35 cột rank trong DB. Foreign keys và composite unique constraints bảo vệ quan hệ, trùng keyword và cache. Index hỗ trợ tìm keyword, lookup tuần, chọn observation cuối và một sync active/bộ.

## Nhận dạng và lịch sử

Duplicate detection dùng NFC + casefold + gom whitespace, giữ nguyên display text và chuỗi exact query gửi Google. Một keyword/bộ; dùng bộ campaign riêng hoặc các Search Profile riêng cho phép đo khác. Không bỏ dấu tiếng Việt.

Đổi tên/URL/mode/profile không thay snapshot cũ. `series_key` hash query, URL, mode và cấu hình profile; chỉ tính biến động khi hai tuần liền nhau có cùng key. Observation không chứa token. Profile không có một mode áp đặt cho mọi keyword: mode nằm trên keyword và được snapshot ở từng observation.

Archive bảo toàn lịch sử. Delete keyword/bộ phải xác nhận vì có cascade. Chuyển giữa bộ cùng website, lịch và timezone giữ ID, snapshot, ngày và rank; ánh xạ week/profile sang bộ đích, bỏ nhóm và ghi activity hai phía. Khác lịch phải xuất/nhập lại với ánh xạ tuần rõ ràng. Lịch đã có observation bị khóa: không tự relabel.

## Thời gian

Ngày của các tuần là ngày local theo timezone bộ. checked_at lưu UTC có timezone, hiển thị theo timezone bộ; mặc định Asia/Ho_Chi_Minh. Observation nhập chỉ biết tuần có checked_at=null, timestamp_precision=week_only và created_at là giờ nhập, không phải giờ quan sát. Bản exact phải nằm trong tuần local đã chọn và không ở tương lai.

Đại diện ô là **bản ghi được lưu sau cùng trong tuần/profile**, theo ID tăng dần. Đây là chính sách sửa ô: clear và correction mới nhất có hiệu lực, ngay cả khi ngày kiểm tra được nhập lùi. UI hiển thị số observation và drawer giữ các bản cũ. Không tự chọn rank tốt nhất.

## Backup

`python scripts/backup_database.py` tạo bản sao SQLite nhất quán, gồm dữ liệu WAL đã commit và kiểm tra integrity. Token OAuth vẫn thuộc OS keyring; cần kết nối lại Google khi chuyển máy. Không copy riêng file DB trong khi đang ghi nếu bỏ qua WAL.
