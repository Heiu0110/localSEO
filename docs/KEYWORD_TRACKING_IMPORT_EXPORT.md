# Nhập/xuất bảng từ khóa

## Định dạng

CSV UTF-8 hoặc XLSX (sheet đầu), tối đa 100 KiB,1.000 dòng dữ liệu,100 cột. Header cần có tên duy nhất. Giữ tiếng Việt có dấu. Tệp có macro, external links, mã hóa, công thức XLSX hoặc vượt giới hạn giải nén bị từ chối. Chỉ đọc bytes upload; không nhận đường dẫn tệp trên máy.

Header mặc định: `Từ khóa, Nhóm, URL, Click, Impression, Vị trí trung bình, Tuần 1, …, Tuần 35`.

Nhận diện cả các technical keys `keyword_text`, `target_url`, `week_1`… Có thể thay ánh xạ từng cột tại bản xem trước rồi nhấn xem trước lại. Header lạ chưa ánh xạ sẽ báo lỗi, vẫn cho chọn mapping.

## Ba chế độ

- Chỉ keyword: keyword, nhóm, URL; bỏ metric/rank.
- Keyword + lịch sử: thêm rank tuần, không có metric live.
- Toàn bộ bảng: như trên, giữ metric từ tệp trong import record với nguồn `historical_spreadsheet_unverified`. Drawer có thể xem lại, không dùng thay GSC API hiện tại.

Rank nhận số nguyên trong search depth, `NA` không phân biệt hoa/thường hoặc blank. Blank không tạo quan sát nhập, tương đương chưa có bản ghi; không xóa observation đang có. Muốn clear lịch sử hãy dùng ô rank và lưu giá trị rỗng.

## Trùng và lỗi

Duplicate detection giữ dấu, chuẩn NFC/casefold/whitespace. Trong cùng tệp, dòng trùng bị đánh dấu lỗi, không lặng lẽ gộp. Với keyword đã tồn tại:

- Bỏ qua toàn bộ dòng.
- Cập nhật nhóm/URL, thêm các rank không trống vào lịch sử (không xóa các bản cũ).
- Tạo bộ campaign riêng cùng lịch/profile, giữ chuỗi độc lập.

Preview hiển thị header/mapping,20 dòng mẫu, lỗi và cảnh báo. Xác nhận mới commit. Nếu có lỗi, phải chấp nhận bỏ qua toàn bộ dòng lỗi; không có sự chấp nhận thì không ghi. Mọi dòng được chấp nhận lưu trong một transaction. Batch DB lỗi rollback tất cả. Không thể commit một preview hai lần. Nếu lịch/profile đổi sau preview, cần xem trước lại.

Không biết timestamp của rank lịch sử: lưu week_only và checked_at=null, không suy ra từ kỳ GSC hoặc created_at. Lịch Tuần 1 do bộ quyết định; kiểm tra ngày trước khi nhập.

## Xuất

Bộ lọc, sort, profile và kỳ GSC hiện tại áp dụng cho toàn bộ kết quả, không chỉ trang đang xem. Tối đa 5.000 keyword/lần. CSV UTF-8 BOM phù hợp Excel tiếng Việt. XLSX có sheet Theo dõi từ khóa và Metadata (website, bộ, kỳ GSC, scope, profile, lịch, timezone, giờ xuất).

41 cột mặc định gồm 6 cột chính+35 tuần. Rank số là số, NA là chuỗi NA, chưa kiểm tra là ô trống. Unknown GSC là trống; không phải 0. Metric tệp chưa xác minh không xuất thành live GSC. CSV dùng endpoint/query làm ngữ cảnh; để mang metadata đầy đủ hãy chọn XLSX.

Chuỗi có thể kích hoạt formula được thêm dấu nháy để bảo vệ Excel. Không xuất OAuth token hoặc secrets. Các lần quan sát cũ có trong SQLite/drawer; bản export grid chỉ chứa đại diện tuần, không phải full audit log. Backup SQLite để giữ đầy đủ lịch sử/import gốc.
