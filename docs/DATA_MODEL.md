# SQLite data model

Mặc định: `backend/data/seo_workspace.db`. Có thể đặt `SEO_WORKSPACE_DATA_DIR` trong process backend trước khi khởi chạy. Thư mục dữ liệu/cache/credentials được Git ignore. Không phục vụ file database qua HTTP.

Schema được quản lý bằng Alembic, revision đầu `001_gsc_storage`. `python scripts/backend.py --run` tự chạy migrations, FastAPI lifespan cũng kiểm tra migrations khi chạy trực tiếp Uvicorn. Chạy riêng từ `backend/`: `.venv/bin/python -m app.db.database` (Windows dùng `.venv\Scripts\python.exe`). Không dùng create_all thay thế migration; không sửa revision đã áp dụng. Khi đổi schema, thêm revision mới và kiểm tra upgrade/persistence.

| Bảng | Vai trò |
|---|---|
| google_connections | ID, provider google/fixture, trạng thái, display name cục bộ, scope, timestamps; không có token |
| gsc_properties | UUID ổn định, connection_id, exact site_url, Domain/URL-prefix, permission, source_type, is_active, last_synced_at |
| gsc_daily_metrics | Các reporting facts, tách bằng dataset_type site/page/query/country/device và aggregation_type |
| gsc_sync_checkpoints | Một dataset/ngày/property/search_type, complete hoặc empty, fetched_rows, completeness và fetched timestamp |
| gsc_sync_jobs | Queue/lịch sử sync, phạm vi, trạng thái, progress, retries, cancellation và lỗi an toàn |
| app_settings | Metadata không bí mật, hiện có active_google_connection; không phải kho lưu tùy ý credential |
| alembic_version | Revision đã áp dụng |

Để tránh lặp schema, 5 dataset dùng chung một bảng fact, **không phải** một cross-product cube. `dimension_value=''` cho site; URL/query/country/device giữ giá trị API trả về. Khóa duy nhất fact:

`property_id + date + search_type + dataset_type + dimension_value + aggregation_type`

Property unique theo `connection_id + exact site_url`; checkpoint unique theo `property_id + search_type + dataset_type + date`; partial unique index không cho hai job queued/running cùng property. Có index cho property/search type/dataset/date, dimension value và trạng thái job. Foreign keys bật ở mọi connection.

Clicks/impressions là integer, position/CTR là float. CTR ở database là fraction 0–1 (được tính lại từ clicks/impressions), còn REST API/UI là phần trăm 0–100. `data_state=final`. Reporting position tổng hợp theo impression-weighted sum cùng scope, không theo trung bình các row. ISO date là ngày GSC theo Pacific; timestamps UTC có timezone.

Mọi overview đọc riêng site/byProperty. Grouping SQL của page/query/country/device có scope riêng; sort allowlist, parameterized SQL, server pagination và tìm kiếm literal (`%`/`_` không trở thành wildcard ngoài ý muốn). Country mapping dùng ISO 3166 qua pycountry, rồi Intl.DisplayNames tiếng Việt; mã không biết được giữ và ghi là không xác định.

Không lưu quan hệ query–page trong v0.2. Page Detail dùng daily page facts, có đủ 4 chart metrics, và thông báo rõ chưa có query breakdown theo URL. Không ghép hai bảng aggregate độc lập để tạo quan hệ giả.

Mock Provider v0.1 giữ fixture 200 ngày độc lập trong bộ nhớ. FixtureGSCClient là nguồn thứ ba rõ ràng, ghi vào SQLite theo cùng pipeline nhưng source_type=fixture, domain `.example`. Không bao giờ fallback từ property GSC/fixture sang Mock Provider.

## Backup và restore

Từ thư mục gốc:

```text
python scripts/backup_database.py
python scripts/backup_database.py --destination D:\SEO-backups\workspace.db
```

Script dùng SQLite backup API nên bao gồm dữ liệu WAL đã commit, kiểm tra integrity và từ chối ghi đè file đã có. Có thể backup khi backend đang chạy. Không copy riêng file `.db` khi có WAL mà bỏ qua `.db-wal`/`.db-shm`.

Restore: dừng cả hai server; giữ bản dự phòng hiện tại bằng script; đặt bản `.db` đã kiểm chứng vào vị trí dữ liệu, không giữ các sidecar WAL/SHM cũ của database khác; khởi chạy lại backend để migrate. Không chạy downgrade/xóa database để sửa lỗi migration mà chưa có backup. Tokens ở kho khóa hệ điều hành, không nằm trong backup; trên máy khác hãy nhập Desktop client JSON và kết nối Google lại.
