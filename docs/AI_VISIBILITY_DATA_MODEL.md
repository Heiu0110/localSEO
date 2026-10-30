# Dữ liệu AI Visibility

Migration additive `006_ai_visibility`, parent `005_keyword_serp_research`, thêm 15 bảng; không ALTER/drop bảng SEO/Agent cũ trong upgrade. Migration đóng băng DDL, không phụ thuộc model động. Không reset SQLite.

| Bảng | Nội dung / bất biến |
|---|---|
| visibility_projects | liên kết website polymorphic ID, market/language/goal/status |
| visibility_entities | brand/competitor, aliases/domains/profile và config hiện tại |
| visibility_prompts | prompt/intent/category/priority/cohort + source/Research/Tracking references |
| visibility_observations | response nguyên văn, prompt snapshot, collection context, raw annotations/citations, identity, import provenance, supersedes |
| visibility_extractions | revision, registry snapshot/hash, parser version, warnings/completeness |
| visibility_mentions | spans codepoint của nguyên bản, detected/effective status, entity/reason |
| visibility_citations | raw/normalized URL, ownership, reported attribution, offsets/quote, source verification |
| visibility_documents | nguồn page content/business identity/requirement được nhập, provenance và approval |
| visibility_coverage_reviews | đánh giá missing/covered/uncertain có lý do, append-only |
| visibility_evidence | immutable source pointer + snapshot/signature, scoped project |
| visibility_opportunities | rule version/facts/hypotheses/evidence/confidence/priority + review status |
| visibility_reviews | lịch sử thay registry/prompt, mention, nguồn và human review |
| visibility_import_jobs | preview, lỗi, registry/project hash, file hash, commit/count/record IDs |
| visibility_detection_runs | scope, included/excluded IDs, rules, abstentions và availability snapshot |
| visibility_agent_analyses | verified GEO output gắn opportunity và ai_messages hiện có |

Sửa response tạo observation mới với `supersedes_id`; bản cũ không đổi và bị loại khỏi mẫu số hiện tại. Unique supersedes ngăn hai nhánh sửa. Re-extract tạo revision mới, không ghi đè registry snapshot hoặc review cũ. Registry thay đổi phải được re-extract chủ động; Agent từ chối evidence cũ cho đến khi detect lại.

Idempotence theo content/context fingerprint từng project. Cùng prompt nhưng khác provider/model/date là observation khác. Import provenance do server thêm sau fingerprint, nên nhập cùng response qua tệp khác không nhân đôi observation. Các lượt import vẫn có job audit riêng. Chưa có metadata thực thì giữ null; import timestamp không thay observation timestamp.

Backup môi trường trước migration: `backend/data/pre-phase8-baseline.sqlite`, `pre-phase8-migration.sqlite`. SQLite backup API được dùng thay copy file WAL. Kiểm tra thời điểm migration: 41/41 bảng hiện có giữ nguyên count + SHA256 logical rows; integrity_check=ok, foreign_key_check=0. Các file runtime/backup không được commit. Browser tests sau migration tạo thêm fixture có chủ đích; không nhầm fixture đó với thay đổi do migration.

Full response/raw payload lưu local cho đến khi chủ workspace quản lý/xóa dữ liệu/backup; Core chưa có retention scheduler. Archive project/prompt không xóa evidence. Cân nhắc thời hạn lưu/giấy phép của dữ liệu bên thứ ba trước khi nhập. Không ghi credentials vào các bảng này.
