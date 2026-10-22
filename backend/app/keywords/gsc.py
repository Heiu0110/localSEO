"""Controlled exact-query synchronization using the existing OAuth/client boundary."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db.models import Property, Checkpoint, MetricFact
from app.gsc.dates import now, bounds
from app.gsc.errors import GSCError
from .models import *
from .core import uid, require, fail, view
from .reports import period


def identity(keyword, scope):
    return hashlib.sha256(
        json.dumps(
            [keyword.keyword_text, keyword.target_url if scope == "page" else ""],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def fetch_exact(client, site_url, query, start, end, page=None, pages=False):
    filters = [{"dimension": "query", "operator": "equals", "expression": query}]
    if page:
        filters.append({"dimension": "page", "operator": "equals", "expression": page})
    body = {
        "startDate": start,
        "endDate": end,
        "type": "web",
        "dataState": "final",
        "aggregationType": "byPage" if page or pages else "byProperty",
        "dimensions": ["page"] if pages else [],
        "dimensionFilterGroups": [{"groupType": "and", "filters": filters}],
        "rowLimit": 20 if pages else 1,
    }
    return client.exact_query(site_url, body)


def cached_daily(session, prop, keyword, start, end):
    days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days + 1
    checkpoints = session.scalars(
        select(Checkpoint).where(
            Checkpoint.property_id == prop.id,
            Checkpoint.dataset_type == "query",
            Checkpoint.search_type == "web",
            Checkpoint.date >= start,
            Checkpoint.date <= end,
        )
    ).all()
    if len(checkpoints) != days or any(
        c.status not in ("complete", "empty") for c in checkpoints
    ):
        return None
    rows = session.scalars(
        select(MetricFact).where(
            MetricFact.property_id == prop.id,
            MetricFact.dataset_type == "query",
            MetricFact.aggregation_type == "byProperty",
            MetricFact.search_type == "web",
            MetricFact.date >= start,
            MetricFact.date <= end,
            MetricFact.dimension_value == keyword,
        )
    ).all()
    # Missing detailed rows do not mean zero. Do not claim a complete period from partial daily rows.
    if len(rows) != days:
        return None
    clicks = sum(r.clicks for r in rows)
    impressions = sum(r.impressions for r in rows)
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions if impressions else None,
        "average_position": (
            sum(r.position * r.impressions for r in rows) / impressions
            if impressions
            else None
        ),
        "status": "available",
        "source": "stored_gsc_query",
        "freshness": "stored",
        "source_fetched_at": min(r.fetched_at for r in rows),
        "top_page": None,
        "observed_pages": [],
    }


class KeywordSyncManager:
    def __init__(self, db, client_factory):
        self.db, self.client_factory = db, client_factory
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="keyword-gsc"
        )
        self.lock = threading.RLock()
        self.stopping = threading.Event()

    def recover(self):
        with self.db.session.begin() as s:
            for job in s.scalars(
                select(KeywordSyncJob).where(
                    KeywordSyncJob.status.in_(["queued", "running"])
                )
            ):
                job.status = "interrupted"
                job.error = "Phiên đồng bộ đã dừng khi ứng dụng đóng. Chạy lại để tiếp tục từ cache."
                job.updated_at = now()

    def close(self):
        self.stopping.set()
        self.executor.shutdown(wait=True, cancel_futures=True)

    def start(self, data, submit=True):
        start, end = period(data.date_start, data.date_end)
        with self.lock, self.db.session.begin() as s:
            ks = require(s, KeywordSet, data.keyword_set_id)
            if not ks.property_id:
                fail(
                    "Website demo không có GSC. Chọn property đã kết nối; rank thủ công vẫn dùng được.",
                    "not_connected",
                    409,
                )
            prop = require(s, Property, ks.property_id)
            if start < bounds()[0].isoformat():
                fail(
                    "Kỳ yêu cầu vượt vùng lịch sử GSC hiện có. Cache cũ vẫn đọc được.",
                    "insufficient_history",
                )
            active = s.scalar(
                select(KeywordSyncJob).where(
                    KeywordSyncJob.keyword_set_id == ks.id,
                    KeywordSyncJob.status.in_(["queued", "running"]),
                )
            )
            if active:
                return view(active)
            keywords = s.scalars(
                select(TrackedKeyword)
                .where(
                    TrackedKeyword.keyword_set_id == ks.id,
                    TrackedKeyword.status == "active",
                )
                .order_by(TrackedKeyword.id)
                .limit(5001)
            ).all()
            if len(keywords) > 5000:
                fail(
                    "Mỗi bộ hỗ trợ tối đa 5.000 từ khóa đang hoạt động cho một lượt sync."
                )
            job = KeywordSyncJob(
                id=uid(),
                keyword_set_id=ks.id,
                status="queued",
                completed=0,
                total=len(keywords),
                data={
                    "start": start,
                    "end": end,
                    "scope": data.scope,
                    "refresh": data.refresh,
                    "property_id": prop.id,
                    "items": [
                        {
                            "id": k.id,
                            "text": k.keyword_text,
                            "target": k.target_url,
                            "identity": identity(k, data.scope),
                        }
                        for k in keywords
                    ],
                },
                error=None,
                created_at=now(),
                updated_at=now(),
            )
            s.add(job)
            s.flush()
            result = view(job)
        if submit:
            self.executor.submit(self.run, result["id"])
        return result

    def run(self, job_id):
        errors = 0
        try:
            with self.db.session.begin() as s:
                job = require(s, KeywordSyncJob, job_id)
                job.status = "running"
                data = job.data
                prop = require(s, Property, data["property_id"])
            client = None
            for item in data["items"]:
                if self.stopping.is_set():
                    break
                with self.db.session() as s:
                    if require(s, KeywordSyncJob, job_id).status == "cancelled":
                        return
                    kw = s.get(TrackedKeyword, item["id"])
                    if not kw:
                        continue
                    existing = s.scalar(
                        select(KeywordMetric).where(
                            KeywordMetric.keyword_id == kw.id,
                            KeywordMetric.scope == data["scope"],
                            KeywordMetric.date_start == data["start"],
                            KeywordMetric.date_end == data["end"],
                            KeywordMetric.identity == item["identity"],
                        )
                    )
                    valid = (
                        existing
                        and existing.data.get("status") in ("available", "no_rows")
                        and datetime.fromisoformat(existing.fetched_at)
                        > datetime.now(timezone.utc) - timedelta(hours=6)
                    )
                    if valid and not data["refresh"]:
                        metrics = None
                    elif data["scope"] == "page" and not item["target"]:
                        metrics = {
                            "status": "target_missing",
                            "clicks": None,
                            "impressions": None,
                            "ctr": None,
                            "average_position": None,
                        }
                    else:
                        metrics = (
                            cached_daily(
                                s, prop, item["text"], data["start"], data["end"]
                            )
                            if data["scope"] == "property" and not data["refresh"]
                            else None
                        )
                        if metrics:
                            metrics["source"] = (
                                "fixture_stored"
                                if prop.source_type == "fixture"
                                else metrics["source"]
                            )
                        if metrics is None:
                            metrics = {}
                if metrics == {}:
                    try:
                        if client is None:
                            client = self.client_factory(prop)
                        response = fetch_exact(
                            client,
                            prop.site_url,
                            item["text"],
                            data["start"],
                            data["end"],
                            item["target"] if data["scope"] == "page" else None,
                        )
                        expected = "byPage" if data["scope"] == "page" else "byProperty"
                        if (
                            response.get("responseAggregationType", expected)
                            != expected
                        ):
                            raise GSCError(
                                "aggregation_mismatch",
                                "Google trả về phạm vi tổng hợp khác yêu cầu.",
                                502,
                            )
                        rows = response.get("rows", [])
                        if not rows:
                            metrics = {
                                "status": "no_rows",
                                "clicks": None,
                                "impressions": None,
                                "ctr": None,
                                "average_position": None,
                            }
                        else:
                            r = rows[0]
                            imps = r["impressions"]
                            metrics = {
                                "status": "available",
                                "clicks": r["clicks"],
                                "impressions": imps,
                                "ctr": r["clicks"] / imps if imps else None,
                                "average_position": r["position"] if imps else None,
                            }
                        metrics.update(
                            source=(
                                "fixture_exact_query"
                                if prop.source_type == "fixture"
                                else "gsc_exact_query"
                            ),
                            freshness="final",
                            observed_pages=[],
                            top_page=None,
                        )
                        if rows:
                            pages = fetch_exact(
                                client,
                                prop.site_url,
                                item["text"],
                                data["start"],
                                data["end"],
                                pages=True,
                            ).get("rows", [])
                            pages = sorted(
                                pages, key=lambda r: r["impressions"], reverse=True
                            )
                            metrics.update(
                                observed_pages=[
                                    {
                                        "url": r["keys"][0],
                                        "clicks": r["clicks"],
                                        "impressions": r["impressions"],
                                    }
                                    for r in pages
                                ],
                                top_page=pages[0]["keys"][0] if pages else None,
                            )
                        # Limit API pressure independently of rendering. Existing Google client handles quota/backoff.
                        if prop.source_type != "fixture":
                            self.stopping.wait(0.25)
                    except GSCError as error:
                        errors += 1
                        with self.db.session.begin() as s:
                            job = require(s, KeywordSyncJob, job_id)
                            job.error = error.message
                            job.updated_at = now()
                        # Preserve a prior successful cache on transient failure.
                        metrics = (
                            None
                            if existing
                            else {
                                "status": "api_error",
                                "clicks": None,
                                "impressions": None,
                                "ctr": None,
                                "average_position": None,
                                "error": error.message,
                            }
                        )
                        if error.code in (
                            "reauthorization_required",
                            "permission_denied",
                            "quota_exceeded",
                            "vault_unavailable",
                        ):
                            raise
                with self.db.session.begin() as s:
                    job = require(s, KeywordSyncJob, job_id)
                    if metrics is not None and s.get(TrackedKeyword, item["id"]):
                        metrics.update(
                            keyword_text=item["text"],
                            target_url=item["target"],
                            date_start=data["start"],
                            date_end=data["end"],
                            coverage_note="GSC có thể ẩn query hoặc giới hạn rows. Không phải tổng traffic website.",
                        )
                        record = s.scalar(
                            select(KeywordMetric).where(
                                KeywordMetric.keyword_id == item["id"],
                                KeywordMetric.scope == data["scope"],
                                KeywordMetric.date_start == data["start"],
                                KeywordMetric.date_end == data["end"],
                                KeywordMetric.identity == item["identity"],
                            )
                        )
                        if record:
                            record.data = metrics
                            record.fetched_at = now()
                        else:
                            s.add(
                                KeywordMetric(
                                    id=uid(),
                                    keyword_id=item["id"],
                                    scope=data["scope"],
                                    date_start=data["start"],
                                    date_end=data["end"],
                                    identity=item["identity"],
                                    data=metrics,
                                    fetched_at=now(),
                                )
                            )
                    job.completed += 1
                    job.updated_at = now()
            with self.db.session.begin() as s:
                job = require(s, KeywordSyncJob, job_id)
                if job.status != "cancelled":
                    job.status = (
                        "interrupted"
                        if self.stopping.is_set()
                        else "partial" if errors else "completed"
                    )
                job.updated_at = now()
        except Exception as error:
            with self.db.session.begin() as s:
                job = s.get(KeywordSyncJob, job_id)
                if job and job.status != "cancelled":
                    job.status = "failed"
                    job.error = (
                        error.message
                        if isinstance(error, GSCError)
                        else "Đồng bộ chưa hoàn tất. Cache đã lưu được giữ nguyên."
                    )
                    job.updated_at = now()
