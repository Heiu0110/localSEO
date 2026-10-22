# GSC và Keyword Tracking

Dùng lại connection, OS keyring, OAuth và scope `webmasters.readonly` hiện có. Không có OAuth thứ hai và không lưu token trong bảng keyword/frontend. Settings vẫn là nơi kết nối Google/chọn property.

## Phạm vi

- `property`: exact query, dimensions=[], aggregationType=byProperty.
- `page`: exact query + exact target page filters, dimensions=[], aggregationType=byPage.
- Observed pages: exact query filter, dimensions=[page], aggregationType=byPage, tối đa 20 row, sắp theo impression ở client của job.

Mọi query filter dùng `operator=equals`; không dùng contains, không lower-case hoặc bỏ dấu biểu thức gửi Google. Query-page được gọi trực tiếp, không ghép query totals và page totals độc lập. Search type Core là web, dataState=final. Observed top page là top trong các row API trả về; có thể thiếu, không phải danh sách landing page đầy đủ.

Không thay Target URL bằng top page. Khi cache có observed page khác URL đích sẽ hiển thị chỉ báo; người dùng tự đánh giá và sửa mapping trong drawer. Không coi nhiều URL cùng query là cannibalization đã xác nhận.

## Thời gian và cache

Mặc định 28 ngày kết thúc tại ngày final an toàn hiện tại theo giờ Pacific, tách biệt với 35 tuần manual. Có 7/28/90 ngày hoặc custom tối đa 501 ngày. Google có giới hạn lịch sử khoảng 16 tháng; sync từ chối ngày quá cũ, nhưng cache cũ vẫn đọc được. Không dùng tuần rank làm kỳ GSC.

Cache unique theo keyword/scope/start/end/hash exact query và target (chỉ page scope). Property liên kết qua bộ. Sửa query/URL không hiển thị cache của danh tính khác. Lượt sync dùng lại cache thành công dưới 6 giờ, nút Làm mới bỏ cache. Daily query cache hiện tại chỉ dùng khi đủ checkpoint và exact row cho từng ngày với aggregation đúng; tính CTR bằng tổngclick/tổngimpression, Position có trọng số impression. Không cộng TopQueries thành KPI website.

Một worker nền, một job active/bộ, tối đa 5.000 keyword/lượt; không gọi API khi render mỗi cell. Có tiến độ, hủy giữa request, đánh dấu interrupted khi khởi động lại, chạy lại dùng cache. Google client hiện tại retry/backoff/quota/refresh token như v0.2. Lỗi sync giữ cache đã thành công và thông báo lỗi; không thay bằng 0.

## Trạng thái

`available`, `no_rows`, `not_synced`, `not_connected`, `target_missing`, `api_error`. Kỳ quá cũ/không hoàn tất và quyền bị thu hồi có thông báo job/validation riêng. Missing row có thể do privacy/row limits; click/impression/position chưa biết là null. GSC Average Position luôn khác phép đếm rank organic thủ công và không được tự ghi vào tuần.

## Kiểm chứng

Tests mock external calls và dùng FixtureGSCClient có ghi nhãn. Đã test equals filters, hai aggregation scopes, weighted cache, no rows, cache identity, quota/quyền qua client chung và bảo toàn cache khi lỗi. Chưa xác minh live Google trong môi trường cloud không có keyring/credentials của người dùng. Sau cấu hình thật, kiểm tra một query nhỏ trong cả hai scope và đối chiếu GSC UI cùng kỳ trước khi sync bộ lớn.
