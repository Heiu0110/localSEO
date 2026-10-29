# Tool Registry v1.0

Tool catalog và schema máy đọc: `GET /api/ai/tools`. Tất cả read_only, scope do backend giữ theo hội thoại, timeout 5 giây, kết quả tối đa 8.000 byte. Mặc định tối đa 6 tool/lượt kể cả context đầu; không có SQL/shell/file/network/write tool.

| Tool | Nguồn thực và giới hạn |
|---|---|
| get_project_context | Catalog website, ngày GSC, audit và bộ rank; không có dữ liệu Topical Map giả |
| get_data_source_status | Cùng context service, nêu rõ nguồn thiếu/inactive |
| get_gsc_overview | DashboardService cho demo có nhãn; SQLiteAnalyticsProvider cho property active; tổng site/byProperty |
| compare_gsc_periods | Dịch vụ so kỳ liền trước hiện có; thiếu coverage không có delta xác nhận |
| get_gsc_top_pages | Page dataset/byPage, tối đa 10 dòng, có availability và giới hạn privacy/rows |
| get_gsc_top_queries | Query dataset/byProperty, tối đa 10 dòng; không dùng làm tổng traffic |
| get_gsc_query_page_data | KeywordMetric page-scope cache đã gọi exact query+page riêng; không ghép query/page totals, không gọi Google |
| get_technical_audit_summary | AuditProject/AuditRun đúng website, snapshot lưu sẵn |
| get_technical_findings | Technical report service, tối đa 6 findings cùng snapshot |
| get_url_diagnostics | URL đã có trong audit; không crawl, không URL Inspection |
| get_internal_link_summary | Aggregate AuditLink.internal trong snapshot, tối đa 10 targets |
| get_keyword_tracking_summary | Keyword report service theo set/profile/week, có NA/unchecked và delta hợp lệ |
| get_keyword_rank_history | Đại diện tối đa 10 tuần gần nhất trong 35 tuần truy vấn; giữ profile/URL/mode snapshot |

Không đăng ký get_topical_map_summary/get_topic_mappings vì nguồn chưa tồn tại. Server Logs, URL Inspection và External Research chưa có adapter. Yêu cầu những tool này trả lỗi allowlist, không tạo mock measurement.

Tool arguments được Pydantic kiểm tra extra=forbid, giới hạn days/limit/độ dài và enum sort. IDs khác website bị từ chối. GSC args lấy kỳ từ hội thoại; muốn kỳ khác hãy chọn lại ở composer. Native manual ranking week không bị suy ra từ GSC date range.

HTTP của tool chỉ là API localhost phục vụ UI; model không được tự gọi API localhost tùy ý. Registry gọi service methods allowlist, không dùng model text để tạo SQL hoặc lệnh thực thi. SQL do các service kiểm soát và bind parameters.

## Bổ sung Phase 7 — tổng 20 tools

7 tools Research: `get_keyword_research_summary`, `get_research_keyword_candidates`, `get_keyword_clusters`, `get_serp_snapshot`, `compare_serp_snapshots`, `get_competitor_serp_summary`, `get_keyword_opportunities`. Tất cả chỉ đọc dữ liệu đã lưu thuộc website của hội thoại, cùng timeout/result/budget controls. Xem [phạm vi và evidence](KEYWORD_RESEARCH_AI_INTEGRATION.md). Không có discovery/fetch/review/transfer tool.
