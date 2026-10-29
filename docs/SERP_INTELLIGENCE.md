# SERP Intelligence — bằng chứng nhập, không phải rank live

GSC Average Position, MANUAL rank Tracking và organic position trong snapshot là ba loại dữ liệu độc lập. Research không ghi vị trí SERP vào weekly rank.

Snapshot có keyword, provider/source, search_engine, search_type web, country/language, location, device, requested_depth, collected_at có timezone, completeness, request_id/notes và result rows. `returned_depth` là vị trí organic lớn nhất đã khai báo, không phải số dòng. Metadata ghi origin user_imported và cost null, không bịa provider usage.

JSON nhập một snapshot, với keyword_id lấy từ Research và dữ liệu quan sát thật:

```text
{
 "keyword_id": "<ID keyword đã lưu>",
 "provider": "<nguồn quan sát>",
 "search_engine": "Google", "country": "VN", "language": "vi",
 "location": "<địa điểm>", "device": "desktop",
 "requested_depth": <Top N đã quan sát>,
 "collected_at": "<ISO datetime có timezone>",
 "completeness": "partial",
 "results": [{"organic_position": <vị trí thực tế>, "provider_position": "<nhãn gốc>",
              "result_type": "organic", "url": "<HTTP(S) URL>",
              "title": "<title>", "snippet": "<snippet>", "features": []}]
}
```

CSV/XLSX dùng mỗi dòng một result với các metadata snapshot lặp giống nhau; header keyword_id, provider, search_engine, country, language, location, device, requested_depth, collected_at, completeness, organic_position, provider_position, result_type, url, title, snippet. Feature arrays nhập qua JSON/UI. Một tệp tương ứng một snapshot.

`complete_observed` yêu cầu đủ organic positions 1..N trong độ sâu được khai báo; chỉ xác nhận mẫu nhập, không khẳng định có toàn bộ kết quả Google. Paid/feature rows không có organic_position. Không suy ra feature vắng mặt nếu không được khai báo. AI Overview là feature, không chứng minh website được AI trích dẫn.

Import preview → xác nhận lưu nguyên bản. Cùng content identity trả snapshot cũ; không có API sửa snapshot. URL normalization chỉ chuẩn hóa HTTP(S)/IDNA host và bỏ fragment; giữ path/query, không suy đoán canonical hay bỏ trailing slash. Không tải URL. Organic vị trí theo số người nhập cung cấp, provider_position giữ nguyên nhãn gốc.

Compare chỉ cho cùng provider/engine/type/country/language/location/device/requested depth/rank definition và đủ Top N. Profile khác/partial → comparable=false, overlap=null, lý do rõ ràng. So sánh keyword khác là overlap intent-support, không phải biến động rank của cùng query. Jaccard là số URL chuẩn hóa chung / tổng URL khác nhau quan sát; không gộp theo domain. Snapshot trên 7 ngày đánh dấu cũ; thời gian cũ không bị thay bằng imported_at.

Website presence chỉ nói observed hoặc not_found_within_observed_top_n. Không thấy trong Top N không đồng nghĩa không xếp hạng ở Google. Competitor cohorts dùng snapshot mới nhất mỗi keyword trong cùng profile; đếm mỗi domain một lần/SERP dù có nhiều URL. Mẫu số sampled_serps luôn kèm theo; không phải thị phần/traffic toàn thị trường. Không crawl đối thủ tự động.
