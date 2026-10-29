# Dữ liệu Research và import

Migration `005_keyword_serp_research` nối tiếp `004_ai_agent`. Có foreign keys, index project/keyword/cluster/snapshot và unique keyword (project, normalized, country, language). Cascade chỉ trong Research; không xóa SEO nguồn. `primary_keyword_id` được service kiểm tra membership, không dùng FK vòng.

10 bảng: research_projects, research_keywords, research_keyword_sources, research_keyword_metrics, research_clusters, research_serp_snapshots, research_serp_results, research_opportunities, research_review_events, research_import_jobs.

Source giữ provider, method, reference, original text, seed, collected_at, imported_at, metadata và content identity. Metric là số hữu hạn ≥0, có type/unit/scope/period/provider source. Không cộng hoặc tự so sánh metrics khác provider/thang đo/kỳ. Close variants có thể lưu trong source metadata, không tự merge identities.

Đơn vị GSC Research: clicks, impressions, CTR ratio 0–1, average_position. Adapter chuyển CTR phần trăm của API Dashboard sang ratio. GSC metrics trong cùng observation phải cùng kỳ/scope. Import từ GSC Core là all_countries/all_devices của property; country/language của Research là locale nghiên cứu, không phải bộ lọc GSC đã được áp dụng. Search volume dùng searches/month; CPC currency/USD hoặc currency/VND; competition/difficulty cần metadata.scale. Google Ads competition là paid competition, không phải organic difficulty. Relative interest index_0_100 là chỉ số tương đối, không phải volume.

JSON keyword import là một danh sách Candidate, ví dụ chỉ seed không có demand:

```json
[{"keyword_text":"may balo học sinh","country":"VN","language":"vi","provider":"user_supplied","method":"seed","metrics":[]}]
```

Candidate có thể thêm group_name, intent, target_url, notes, reference, seed, collected_at (ISO có timezone), metadata (tối đa 10 chuỗi) và metrics. Ví dụ hình dạng metric (chỉ dùng số thực từ nguồn của bạn):

```text
metric_type: search_volume
value: <số hữu hạn thực tế>
unit: searches/month
scope: <locale/network của nguồn>
reporting_start / reporting_end: YYYY-MM-DD hoặc null
metadata: {"close_variants": "mô tả nguồn nếu có"}
```

CSV/XLSX có header keyword_text (hoặc Keyword/Từ khóa), provider (Source/Nguồn), country, language, group_name, intent, target_url, notes, search_volume, cpc, cpc_currency, paid_competition, organic_difficulty, metric_scale, metric_scope, reporting_start, reporting_end. Giữ trống dữ liệu thiếu; metrics cần source rõ ràng. Mapping JSON là tên field → tên cột, ví dụ `{"keyword_text":"Từ khóa","provider":"Nguồn"}`. XLSX công thức/macro/external links bị từ chối; CSV export bảo vệ formula injection.

Giới hạn: 100 KiB/tệp, 1.000 dòng/import, 100 projects, 5.000 keywords/project, 100 source observations/keyword, 500 clusters/project, 500 SERP snapshots/project, 100 result rows/snapshot, 200 keyword/bulk hoặc transfer. Table phân trang 25 mặc định, tối đa 100. Preview hiển thị 25 dòng đầu; confirmation xử lý toàn bộ số dòng đã nêu. Export có thể lớn hơn giới hạn import; cần chia tệp nếu muốn nhập lại.

Backup bằng `backend\.venv\Scripts\python.exe scripts\backup_database.py`, giữ đường dẫn backup và dừng server khi cập nhật code. Backup chứa Research và AI history; credentials vẫn trong OS vault. Không ghi đè DB đang chạy bằng bản cũ vì sẽ mất các thay đổi sau thời điểm backup.
