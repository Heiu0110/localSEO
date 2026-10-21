# Đồng bộ dữ liệu

`GoogleGSCClient / FixtureGSCClient → SyncManager → validation → SQLite → SQLiteAnalyticsProvider`. Mock Provider v0.1 không tham gia quá trình này và không bị ghi vào database.

## Mỗi ngày có 5 tập dữ liệu riêng

| Dataset | Dimensions | Aggregation |
|---|---|---|
| site | không có dimension, request một ngày | byProperty |
| page | page | byPage |
| query | query | byProperty |
| country | country | byProperty |
| device | device | byProperty |

Mọi request có cùng property identifier chính xác, `startDate=endDate`, `dataState=final` và một search type. Hiện hỗ trợ `web`, `image`, `video`, `news` (tab News trong Google Search). Discover và Google News feed (`googleNews`) chưa được hỗ trợ; không trộn với web hoặc đổi aggregation tự động.

Main KPI chỉ đọc **site + byProperty**. Pages có scope byPage khác, Queries có thể mất truy vấn ẩn danh; tổng chúng không đại diện traffic toàn property. CTR = tổng clicks / tổng impressions × 100. Position = tổng position × impressions / tổng impressions, chỉ trong cùng reporting scope. Không lấy trung bình đơn giản của CTR/Position và không suy diễn vị trí cố định của từ khóa.

## Lịch sử và tăng dần

- Lựa chọn 28, 90, 180 ngày hoặc khoảng 16 tháng; UI hiển thị ít nhất `ngày × 5` API requests cho toàn kỳ, chưa tính phân trang.
- Ngày dữ liệu theo múi giờ America/Los_Angeles. Cửa sổ đề nghị kết thúc hôm nay theo Pacific trừ 3 ngày; đây là cutoff bảo thủ, không bảo đảm mọi property có bản ghi ở ngày đó. API vẫn được gọi với `dataState=final`.
- Initial/resume bỏ qua checkpoint lịch sử đã có, nhưng làm mới 7 ngày cuối kỳ yêu cầu.
- Incremental bắt đầu từ ngày gần nhất đã đồng bộ trừ 6 ngày, giới hạn bởi ngày bắt đầu người dùng chọn, rồi lấy các ngày mới tới ngày kết thúc. Không tải lại toàn lịch sử. Kỳ phải bao gồm mốc mới nhất đã lưu hoặc thời gian sau đó.
- Refresh lấy lại toàn kỳ. Khi retry một refresh bị lỗi, ứng dụng lấy lại toàn kỳ để không coi checkpoint cũ là kết quả của lần refresh thất bại. Initial/resume tiếp tục dựa trên checkpoints đã ghi.
- Chỉ một job active cho mỗi property. Một in-process worker xử lý queue, không Redis/Celery. Không chạy nhiều Uvicorn workers cho cùng file SQLite.

## Phân trang và tính nguyên vẹn

`rowLimit=25000`, tăng `startRow` cho tới trang ngắn/rỗng hoặc 50.000 dòng/ngày/search type. Không cố vượt giới hạn để khẳng định đã có tất cả dữ liệu.

Sau khi lấy hết các trang của một dataset/ngày, kiểm tra khóa, số liệu hữu hạn, clicks/impressions nguyên không âm, clicks ≤ impressions và `responseAggregationType` đúng yêu cầu. Toàn bộ snapshot dataset/ngày cũ được thay trong **một transaction** cùng checkpoint. Khóa duy nhất chống nhân đôi. Lỗi giữa các trang không ghi nửa dataset và giữ snapshot cũ.

Checkpoint ghi completeness:

- `api_response`: kết thúc phân trang API; **không chứng minh** đầy đủ mọi query/page trên Google.
- `api_limited`: đã chạm ngưỡng 50.000, dữ liệu chi tiết có giới hạn.
- `unknown`: ở cấp report khi kỳ chưa có đủ checkpoint.

Bảng chi tiết real/fixture luôn có `coverage=partial`; các metric tổng độc lập với chúng. Dashboard hiển thị Top 100 đã lưu, tìm kiếm/sắp xếp/xuất trong Top 100 này. Phân tích GSC dùng server pagination và CSV cho tất cả dòng đã lưu khớp bộ lọc.

## Ngày rỗng, thiếu và lỗi

- Có row với clicks/impressions 0: lưu row Google thực trả về.
- Request thành công nhưng `rows=[]`: chỉ ghi checkpoint `empty`, không tạo metric 0. Không khẳng định biết nguyên nhân là không có hoạt động, thiếu dữ liệu hay chưa có dữ liệu final.
- Chưa gọi/request chưa xong: không có checkpoint; độ phủ thể hiện thiếu ngày.
- Ngày quá gần hiện tại: không thuộc cửa sổ sync final được cho phép.
- Lỗi API: job có mã lỗi; snapshot cũ không bị xóa. Timeout/offline/429/quota và server errors có retry exponential backoff + jitter; tôn trọng Retry-After. Không retry lỗi quyền/refresh token vĩnh viễn. Khoảng chờ trên 60 giây được trả về để người dùng thử lại sau thay vì vòng lặp chờ dài.

Chuỗi ngày thiếu trả `metrics=null`, không nối thành dữ liệu giả. KPI của kỳ thiếu chỉ tổng hợp các ngày có bản ghi và báo độ phủ. Thiếu kỳ trước thì `comparison_available=false`, delta/percent `null`; UI không hiển thị tăng/giảm giả. Một query/page vắng trong một kỳ không được coi là chắc chắn giảm 100%.

## Tiến độ, phục hồi và đọc đồng thời

Job lưu khoảng ngày, ngày hoàn tất, số dòng vừa nhập, task hiện tại, số retry, timestamps và lỗi đã chuẩn hóa. `completed_days` chỉ tăng khi đã xử lý cả 5 datasets của ngày đó; không tạo tiến độ theo thời gian giả.

Hủy ở ranh giới dataset an toàn; request đang chạy có thể cần hoàn tất/timeout trước khi hủy. Khởi động lại chuyển queued/running bỏ dở sang `partial` để tiếp tục. Nếu bản thân ổ đĩa không ghi được lỗi job, API hiển thị failure trong process; cần sửa quyền/dung lượng rồi khởi động lại để phục hồi trạng thái bền vững.

SQLite bật foreign keys, WAL, busy timeout và có một sync worker. Read report giữ lock ngắn để các truy vấn trong một response cùng snapshot. Dashboard lấy ngày kết thúc từ overview rồi neo các bảng/biểu đồ vào cùng ngày đó. CSV tạo snapshot nhất quán dưới lock, dùng temporary spool (tràn ra file khi lớn) rồi giải phóng lock trước khi stream tới trình duyệt. Metadata dùng transaction ngắn; SQLite tự serialize writer.

Bulk Export sang BigQuery có thể là hướng nâng cấp cho website quá lớn, không phải dependency v0.2.
