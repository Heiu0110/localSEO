# SQLite Technical SEO

Migration **002_technical_audits**, nối sau 001_gsc_storage; thêm bảng, không thay hoặc xóa fact/checkpoint/token của GSC. OS keyring vẫn là nơi lưu OAuth, không liên quan crawler.

| Table | Mục đích / khóa |
|---|---|
| technical_projects | Website root, property FK tùy chọn, source_type live/fixture, cấu hình mặc định |
| technical_audits | Run/job, status, progress, config+intent snapshot, scope_hash, rule_version, coverage, summary, timestamps |
| technical_urls | Original/normalized/final URL, state/status, depth, title/indexability, counts/duration, source list, extracted JSON; unique(audit_id,url) |
| technical_links | Source URL FK, target URL, anchor/rel/context/internal flag; index(audit_id,target_url) |
| technical_sitemaps | HTTP/parse status, kind/count/error; unique(audit_id,url) |
| technical_issues | Finding snapshot, rule/version via audit, evidence/confidence, priority reasons, first/last seen; unique(audit_id,fingerprint) |
| technical_tasks | Trạng thái công việc hiện tại, owner/notes/verification, first/last seen; unique(project_id,fingerprint) |
| technical_url_intents | Phân loại/mục đích cho audit sau, provenance; unique(project_id,url) |
| technical_imports | Tên file đã sanitize, hash, preview/imported status, validated rows, project FK và timestamp |

Có partial unique index chặn hai queued/running runs cùng project; indexes cho runs, URL reports, issues và tasks. Foreign keys bật, SQLite WAL và busy timeout dùng chung Database v0.2. Một worker Technical SEO và một worker GSC trong process; không dùng nhiều Uvicorn workers cho cùng DB.

Mỗi run mới đóng băng config/intent, không ghi đè URL hoặc issue của run trước. Original URL đầu tiên được giữ; normalized key được dùng để dedup. Query policy được ghi cùng snapshot, trailing slash vẫn phân biệt. URL sources có thể nhiều giá trị. Không lưu HTML đầy đủ, access token, cookies/auth headers, file paths hoặc server secrets. Chỉ giữ metadata/headers allowlist/evidence có giới hạn.

Checkpoint là URL đã xử lý và metadata/links đã commit. Run bị dừng chuyển interrupted ở startup. Chạy lại tạo snapshot mới và fetch lại; Core không resume trong cùng snapshot. Transaction cuối tính graph/findings/backlog, không ghi nửa tập findings.

Fingerprint dựa rule ID + normalized URL, độc lập audit ID. Task giữ ghi chú khi finding tái xuất hiện. Evidence của một snapshot không đổi khi người dùng đổi backlog hoặc URL intent. Verification không được xem là thành công chỉ vì task được đóng thủ công.

CSV preview lưu validated rows riêng với trạng thái preview. Chỉ commit rõ ràng mới upsert intent; source chứa import ID. Không nhập chéo website âm thầm. Upload không đọc arbitrary paths, không nhận archives; global request cap 128 KiB và file cap 100 KiB.

Export chỉ cho audit đã dừng, đọc trong explicit SQLite read transaction để tránh trộn snapshot khi retention xóa đồng thời. Xóa audit dùng FK cascade cho URLs/links/sitemaps/issues; không xóa Google facts hoặc project tasks. Verification reference được đánh dấu source_deleted. Không chạy VACUUM tự động.

Backup nhất quán kể cả WAL: `python scripts/backup_database.py`. Dừng backend trước restore, theo [DATA_MODEL.md](DATA_MODEL.md). Không xóa database để xử lý lỗi migration hoặc test. Tests sử dụng DB tạm; runtime migrations idempotent và có test nâng 001→002 vẫn giữ dữ liệu cũ.
