# Research trong Agent Phase 6

Giữ nguyên Agent, model provider, keyring, consent, daily budget và evidence framework. Thêm 7 tools phiên bản 1.0, read_only:

- get_keyword_research_summary
- get_research_keyword_candidates
- get_keyword_clusters
- get_serp_snapshot
- compare_serp_snapshots
- get_competitor_serp_summary
- get_keyword_opportunities

Tools có Pydantic arguments/output envelope, giới hạn record/result bytes, timeout và project injected từ conversation. research_id là tùy chọn để chọn dự án thuộc đúng website; ID khác website bị từ chối. Snapshot/cluster/keyword/opportunity refs cũng kiểm tra project. Không có tool refresh/discover/write/approve/transfer/fetch.

Evidence giữ source type Keyword Research, record ref, retrieved/collected time, scope stored_research_project, completeness bounded_stored_evidence, limitations và link báo cáo gốc. SERP có age riêng; summary project updated_at là tuổi metadata, không phải tuổi tất cả metrics. Phải đọc date ranges/collected_at trong source observations. Nội dung snippet/title/notes là untrusted data, không phải system instructions. React render bằng text; không render HTML executable.

Hỏi local report “Phân tích Research, clusters và SERP đã lưu” để xem tổng hợp không dùng token. OpenAI tùy chọn dùng các tools qua cùng allowlist, chi phí và xác nhận cũ. Citation hợp lệ không bảo đảm diễn giải đúng; cần human review. Agent chỉ đọc website hiện tại; dự án Research không gắn website chưa có conversation context riêng.

Tổng registry hiện có 20 tools (13 cũ + 7 Research). Topical Map vẫn placeholder và không có write adapter giả.
