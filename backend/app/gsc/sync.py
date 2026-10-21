"""One in-process writer; each paginated dataset/day replaces its snapshot atomically."""
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.models import Checkpoint, MetricFact, Property, SyncJob
from app.gsc.client import DIMENSIONS
from app.gsc.dates import bounds, days_between, now
from app.gsc.errors import GSCError
from app.gsc.repository import require_property
from app.gsc.schemas import JobView, SyncRequest

logger = logging.getLogger(__name__)
ACTIVE = ("queued", "running")
ROW_LIMIT = 25_000
DAY_LIMIT = 50_000


def fetch_dataset(client, prop, day, dataset, search_type):
    expected = "byPage" if dataset == "page" else "byProperty"
    rows, seen, start = [], set(), 0
    while True:
        response = client.query(prop.site_url, day, dataset, search_type, start, ROW_LIMIT)
        if response.get("responseAggregationType") != expected:
            raise GSCError("aggregation_mismatch", "Google trả phạm vi tổng hợp khác yêu cầu; dữ liệu cũ được giữ nguyên.", 502)
        page = response.get("rows", [])
        if not isinstance(page, list) or len(page) > ROW_LIMIT:
            raise GSCError("invalid_google_data", "Phản hồi Google không hợp lệ; không ghi đè dữ liệu.", 502)
        for row in page:
            keys = row.get("keys", [])
            key = "" if dataset == "site" else keys[0] if len(keys) == 1 and isinstance(keys[0], str) else None
            clicks, impressions, position = row.get("clicks"), row.get("impressions"), row.get("position")
            if (key is None or key in seen or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (clicks, impressions, position))
                    or clicks > impressions or clicks != int(clicks) or impressions != int(impressions)):
                raise GSCError("invalid_google_data", "Bản ghi Google không hợp lệ hoặc trùng khóa. Lần nhập bị hủy an toàn.", 502)
            seen.add(key)
            rows.append({"dimension_value": key, "clicks": int(clicks), "impressions": int(impressions),
                         "position": position, "ctr": clicks / impressions if impressions else 0})
        if len(rows) >= DAY_LIMIT:
            return rows, "api_limited", expected
        if len(page) < ROW_LIMIT:
            # A complete API response does not prove every query/page is exposed.
            return rows, "api_response", expected
        start += ROW_LIMIT


class SyncManager:
    def __init__(self, db, client_factory):
        self.db, self.client_factory = db, client_factory
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gsc-sync")
        self.lock = threading.RLock()
        self.closed = False
        self.failures: dict[str, dict] = {}

    def recover(self):
        with self.db.session.begin() as session:
            session.execute(update(SyncJob).where(SyncJob.status.in_(ACTIVE)).values(
                status="partial", error_code="interrupted", error_message="Tiến trình trước đã dừng. Có thể tiếp tục từ checkpoint.", updated_at=now(), finished_at=now()))

    def start(self, request: SyncRequest, submit=True) -> JobView:
        first, latest = bounds()
        if request.start_date < first or request.end_date > latest:
            raise GSCError("invalid_sync_range", f"Chọn kỳ trong {first.isoformat()} – {latest.isoformat()} (ngày GSC theo giờ Pacific, chỉ dữ liệu final).", 422)
        stamp = now()
        with self.lock:
            try:
                with self.db.session.begin() as session:
                    prop = require_property(session, request.property_id, active=True)
                    if prop.permission_level in ("unavailable", "siteUnverifiedUser"):
                        raise GSCError("permission_denied", "Property không còn quyền truy cập. Làm mới danh sách hoặc kết nối lại Google.", 403)
                    active = session.scalar(select(SyncJob).where(SyncJob.property_id == prop.id, SyncJob.status.in_(ACTIVE)))
                    if active:
                        raise GSCError("sync_already_active", "Property này đang có tác vụ đồng bộ.", 409)
                    start = request.start_date
                    if request.sync_mode == "incremental":
                        last = session.scalar(select(Checkpoint.date).where(Checkpoint.property_id == prop.id, Checkpoint.search_type == request.search_type,
                            Checkpoint.dataset_type == "site").order_by(Checkpoint.date.desc()).limit(1))
                        if last:
                            start = max(start, date.fromisoformat(last) - timedelta(days=6))
                    if start > request.end_date:
                        raise GSCError("invalid_incremental_range", "Kỳ tăng dần phải chứa ngày mới nhất đã lưu hoặc những ngày sau đó.", 422)
                    job = SyncJob(id=str(uuid4()), property_id=prop.id, search_type=request.search_type, sync_mode=request.sync_mode,
                                  status="queued", requested_date_start=start.isoformat(), requested_date_end=request.end_date.isoformat(),
                                  completed_days=0, total_days=(request.end_date - start).days + 1, rows_fetched=0, current_task="Chờ xử lý",
                                  retry_count=0, cancel_requested=False, started_at=stamp, updated_at=stamp)
                    session.add(job)
                    session.flush()
                    result = JobView.model_validate(job)
            except IntegrityError:
                raise GSCError("sync_already_active", "Property này đang có tác vụ đồng bộ.", 409) from None
            if submit:
                self.executor.submit(self.run, result.id)
            return result

    def job(self, job_id) -> JobView:
        with self.db.session() as session:
            job = session.get(SyncJob, job_id)
            if not job:
                raise GSCError("job_not_found", "Không tìm thấy tác vụ.", 404)
            result = JobView.model_validate(job)
            return result.model_copy(update=self.failures[job_id]) if job_id in self.failures else result

    def jobs(self, property_id=None):
        with self.db.session() as session:
            query = select(SyncJob)
            if property_id:
                query = query.where(SyncJob.property_id == property_id)
            return [JobView.model_validate(job).model_copy(update=self.failures.get(job.id, {})) for job in session.scalars(query.order_by(SyncJob.started_at.desc()).limit(100))]

    def cancel(self, job_id):
        with self.db.session.begin() as session:
            job = session.get(SyncJob, job_id)
            if not job:
                raise GSCError("job_not_found", "Không tìm thấy tác vụ.", 404)
            if job.status in ACTIVE:
                job.cancel_requested, job.updated_at = True, now()
        return self.job(job_id)

    def retry(self, job_id):
        job = self.job(job_id)
        if job.status in ACTIVE:
            raise GSCError("sync_already_active", "Tác vụ vẫn đang chạy.", 409)
        return self.start(SyncRequest(property_id=job.property_id, start_date=job.requested_date_start,
            end_date=job.requested_date_end, search_type=job.search_type, sync_mode="refresh" if job.sync_mode == "refresh" else "resume"))

    def _update(self, job_id, **values):
        with self.db.session.begin() as session:
            session.execute(update(SyncJob).where(SyncJob.id == job_id).values(updated_at=now(), **values))

    def _retry_count(self, job_id):
        with self.db.session.begin() as session:
            session.execute(update(SyncJob).where(SyncJob.id == job_id).values(retry_count=SyncJob.retry_count + 1, updated_at=now()))

    def _fail(self, job_id, **values):
        try:
            self._update(job_id, **values)
        except SQLAlchemyError:
            self.failures[job_id] = {**values, "updated_at": now()}
            logger.warning("Cannot persist sync failure: job=%s", job_id)

    def replace_dataset(self, property_id, day, search_type, dataset, rows, completeness, aggregation):
        stamp = now()
        with self.db.metrics_lock, self.db.session.begin() as session:
            where = (MetricFact.property_id == property_id, MetricFact.date == day, MetricFact.search_type == search_type, MetricFact.dataset_type == dataset)
            session.execute(delete(MetricFact).where(*where))
            # SQLAlchemy inserts are parameterized; the transaction also covers checkpoints.
            for offset in range(0, len(rows), 1000):
                session.add_all([MetricFact(property_id=property_id, date=day, search_type=search_type, dataset_type=dataset,
                                           aggregation_type=aggregation, data_state="final", fetched_at=stamp, **row) for row in rows[offset:offset + 1000]])
                session.flush()
            checkpoint = session.scalar(select(Checkpoint).where(Checkpoint.property_id == property_id, Checkpoint.date == day,
                Checkpoint.search_type == search_type, Checkpoint.dataset_type == dataset))
            if not checkpoint:
                checkpoint = Checkpoint(property_id=property_id, date=day, search_type=search_type, dataset_type=dataset)
                session.add(checkpoint)
            checkpoint.status = "complete" if rows else "empty"
            checkpoint.completeness, checkpoint.fetched_rows = completeness, len(rows)
            checkpoint.aggregation_type, checkpoint.last_successful_sync_at = aggregation, stamp

    def run(self, job_id):
        job = self.job(job_id)
        imported = 0
        try:
            self._update(job_id, status="running")
            with self.db.session() as session:
                prop = require_property(session, job.property_id)
            client = self.client_factory(prop, lambda: self._retry_count(job_id))
            for i, day in enumerate(days_between(date.fromisoformat(job.requested_date_start), date.fromisoformat(job.requested_date_end))):
                for dataset in DIMENSIONS:
                    if self.closed or self.job(job_id).cancel_requested:
                        self._update(job_id, status="cancelled", current_task="Đã hủy tại ranh giới an toàn", finished_at=now())
                        return
                    self._update(job_id, current_task=f"{dataset} · {day.isoformat()} · ngày {i + 1}/{job.total_days}")
                    with self.db.session() as session:
                        checkpoint = session.scalar(select(Checkpoint).where(Checkpoint.property_id == prop.id, Checkpoint.date == day.isoformat(),
                            Checkpoint.search_type == job.search_type, Checkpoint.dataset_type == dataset))
                    recent = day >= date.fromisoformat(job.requested_date_end) - timedelta(days=6)
                    if checkpoint and job.sync_mode != "refresh" and not recent:
                        continue
                    rows, completeness, aggregation = fetch_dataset(client, prop, day.isoformat(), dataset, job.search_type)
                    self.replace_dataset(prop.id, day.isoformat(), job.search_type, dataset, rows, completeness, aggregation)
                    imported += len(rows)
                    self._update(job_id, rows_fetched=imported)
                self._update(job_id, completed_days=i + 1)
            stamp = now()
            with self.db.session.begin() as session:
                prop = session.get(Property, job.property_id)
                prop.last_synced_at = stamp
            self._update(job_id, status="completed", current_task="Đã hoàn tất truy xuất API; bảng chi tiết vẫn có thể bị giới hạn", finished_at=stamp)
        except GSCError as error:
            self._fail(job_id, status="reauthorization_required" if error.code == "reauthorization_required" else "partial" if self.job(job_id).completed_days else "failed",
                         error_code=error.code, error_message=error.message, finished_at=now())
            logger.warning("GSC sync failed: job=%s code=%s", job_id, error.code)
        except Exception as error:
            # Never serialize provider exception text, which may contain credential material.
            code = "sqlite_write_error" if isinstance(error, SQLAlchemyError) else "sync_error"
            self._fail(job_id, status="partial" if self.job(job_id).completed_days else "failed", error_code=code,
                         error_message="Đồng bộ bị gián đoạn. Dữ liệu đã ghi an toàn được giữ lại; kiểm tra quyền ghi, dung lượng và thử tiếp tục.", finished_at=now())
            logger.warning("GSC sync failed: job=%s code=%s", job_id, code)

    def close(self):
        self.closed = True
        self.executor.shutdown(wait=True, cancel_futures=True)
