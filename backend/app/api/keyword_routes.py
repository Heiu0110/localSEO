"""Keyword APIs share the application's Origin, CSRF and upload limits."""

import json
from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Body
from fastapi.responses import Response
from sqlalchemy import select, func, delete
from app.gsc.runtime import get_runtime
from app.db.models import Property
from app.services.dashboard_service import get_service
from app.gsc.dates import now
from app.keywords.models import *
from app.keywords.schemas import *
from app.keywords.core import *
from app.keywords.reports import (
    period,
    query_rows,
    grid,
    row_view,
    overview,
    trends,
    latest_query,
)
from app.keywords import spreadsheets

router = APIRouter(prefix="/api/keyword-tracking", tags=["Keyword Tracking"])
Runtime = Annotated[object, Depends(get_runtime)]


def set_detail(s, ks):
    return {
        **view(ks),
        "profiles": [
            view(x)
            for x in s.scalars(
                select(SearchProfile)
                .where(SearchProfile.keyword_set_id == ks.id)
                .order_by(SearchProfile.created_at, SearchProfile.id)
            )
        ],
        "groups": [
            view(x)
            for x in s.scalars(
                select(KeywordGroup)
                .where(KeywordGroup.keyword_set_id == ks.id)
                .order_by(KeywordGroup.sort_order, KeywordGroup.name)
            )
        ],
        "weeks": [
            view(x)
            for x in s.scalars(
                select(TrackingWeek)
                .where(TrackingWeek.keyword_set_id == ks.id)
                .order_by(TrackingWeek.week_number)
            )
        ],
    }


@router.get("/sets")
def sets(runtime: Runtime, site_id: str = Query(max_length=100)):
    with runtime.db.session() as s:
        return [
            view(x)
            for x in s.scalars(
                select(KeywordSet)
                .where(KeywordSet.site_id == site_id)
                .order_by(KeywordSet.created_at, KeywordSet.id)
            )
        ]


@router.post("/sets", status_code=201)
def create_set(data: SetCreate, runtime: Runtime):
    demos = {x.id: x for x in get_service().provider.sites}
    with runtime.db.session.begin() as s:
        prop = s.get(Property, data.site_id)
        if data.site_id not in demos and not prop:
            fail("Website chưa có trong workspace.")
        if (
            s.scalar(
                select(func.count())
                .select_from(KeywordSet)
                .where(KeywordSet.site_id == data.site_id)
            )
            >= 100
        ):
            fail("Website hỗ trợ tối đa 100 bộ từ khóa.")
        values = data.model_dump(exclude={"start_date"})
        ks = KeywordSet(
            id=uid(),
            **values,
            property_id=prop.id if prop else None,
            start_date=data.start_date.isoformat(),
            week_start_day=data.start_date.weekday(),
            status="active",
            settings={
                "site_url": prop.site_url if prop else demos[data.site_id].domain,
                "min_impressions": 100,
                "low_ctr": 0.02,
            },
            created_at=now(),
            updated_at=now(),
        )
        s.add(ks)
        s.flush()
        ensure_weeks(s, ks)
        profile = ProfileInput(keyword_set_id=ks.id)
        s.add(
            SearchProfile(
                id=uid(),
                keyword_set_id=ks.id,
                name=profile.name,
                config=profile.model_dump(exclude={"keyword_set_id", "name"}),
                created_at=now(),
                updated_at=now(),
            )
        )
        s.flush()
        return set_detail(s, ks)


@router.get("/sets/{set_id}")
def get_set(set_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        return set_detail(s, require(s, KeywordSet, set_id))


@router.patch("/sets/{set_id}")
def update_set(set_id: str, data: SetPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        ks = require(s, KeywordSet, set_id)
        values = data.model_dump(exclude_unset=True)
        if any(v is None for v in values.values()):
            fail("Không chấp nhận giá trị null.")
        calendar_change = (
            "start_date" in values and values["start_date"].isoformat() != ks.start_date
        ) or ("timezone" in values and values["timezone"] != ks.timezone)
        has_history = s.scalar(
            select(RankObservation.id)
            .join(
                TrackedKeyword, TrackedKeyword.id == RankObservation.tracked_keyword_id
            )
            .where(TrackedKeyword.keyword_set_id == ks.id)
            .limit(1)
        )
        if calendar_change and has_history:
            fail(
                "Bộ đã có lịch sử: lịch được khóa để không đổi nhãn tuần. Tạo bộ mới rồi nhập lịch sử với ánh xạ tuần rõ ràng.",
                "calendar_locked",
                409,
            )
        settings = ks.settings.copy()
        for k, v in values.items():
            if k in ("min_impressions", "low_ctr"):
                settings[k] = v
            elif k == "start_date":
                ks.start_date = v.isoformat()
                ks.week_start_day = v.weekday()
            else:
                setattr(ks, k, v)
        if calendar_change:
            for week in s.scalars(
                select(TrackingWeek).where(TrackingWeek.keyword_set_id == ks.id)
            ):
                week.start_date, week.end_date = week_dates(
                    ks.start_date, week.week_number
                )
        ks.settings = settings
        ks.updated_at = now()
        activity(s, ks.id, "set_updated", {k: str(v) for k, v in values.items()})
        return set_detail(s, ks)


@router.post("/sets/{set_id}/delete")
def delete_set(set_id: str, data: Confirmation, runtime: Runtime):
    with runtime.db.session.begin() as s:
        ks = require(s, KeywordSet, set_id)
        if not data.confirm:
            fail("Cần xác nhận xóa bộ và toàn bộ lịch sử rank liên quan.")
        if s.scalar(
            select(KeywordSyncJob.id).where(
                KeywordSyncJob.keyword_set_id == set_id,
                KeywordSyncJob.status.in_(["queued", "running"]),
            )
        ):
            fail("Hủy hoặc chờ đồng bộ trước khi xóa.")
        s.execute(delete(TrackedKeyword).where(TrackedKeyword.keyword_set_id == set_id))
        s.delete(ks)
        return {"deleted": True}


@router.post("/groups", status_code=201)
def create_group(data: GroupInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        require(s, KeywordSet, data.keyword_set_id)
        obj = KeywordGroup(id=uid(), **data.model_dump())
        s.add(obj)
        s.flush()
        return view(obj)


@router.patch("/groups/{group_id}")
def edit_group(group_id: str, data: GroupInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        obj = require(s, KeywordGroup, group_id)
        if data.keyword_set_id != obj.keyword_set_id:
            fail("Không chuyển nhóm giữa các bộ.")
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        return view(obj)


@router.post("/profiles", status_code=201)
def create_profile(data: ProfileInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        require(s, KeywordSet, data.keyword_set_id)
        obj = SearchProfile(
            id=uid(),
            keyword_set_id=data.keyword_set_id,
            name=data.name,
            config=data.model_dump(exclude={"keyword_set_id", "name"}),
            created_at=now(),
            updated_at=now(),
        )
        s.add(obj)
        s.flush()
        return view(obj)


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, data: ProfileInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        obj = require(s, SearchProfile, profile_id)
        if obj.keyword_set_id != data.keyword_set_id:
            fail("Search Profile không thuộc bộ từ khóa.")
        obj.name = data.name
        obj.config = data.model_dump(exclude={"keyword_set_id", "name"})
        obj.updated_at = now()
        activity(s, obj.keyword_set_id, "profile_updated", {"profile_id": obj.id})
        return view(obj)


@router.get("/keywords")
def keywords(
    runtime: Runtime,
    set_id: str,
    profile_id: str,
    week: int = Query(default=1, ge=1, le=520),
    date_start: date | None = None,
    date_end: date | None = None,
    scope: Literal["property", "page"] = "property",
    search: str = Query(default="", max_length=500),
    group_id: str = "",
    status: Literal["active", "paused", "archived", "all"] = "active",
    rank_filter: str = "",
    sort: str = "keyword",
    direction: str = "asc",
    min_clicks: int | None = Query(default=None, ge=0),
    min_impressions: int | None = Query(default=None, ge=0),
    max_position: float | None = Query(default=None, ge=1, allow_inf_nan=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    start, end = period(date_start, date_end)
    with runtime.db.session() as s:
        ks = require(s, KeywordSet, set_id)
        q = query_rows(
            s,
            set_id,
            profile_id,
            week,
            start,
            end,
            scope,
            search,
            group_id,
            status,
            rank_filter,
            sort,
            direction,
            min_clicks,
            min_impressions,
            max_position,
        )
        total = s.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
        records = s.execute(q.offset((page - 1) * page_size).limit(page_size)).all()
        weeks = grid(s, records, profile_id, max(35, week))
        return {
            "rows": [
                row_view(s, r, ks, scope, weeks.get(r[0].id, {})) for r in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "date_start": start,
            "date_end": end,
            "scope": scope,
        }


@router.post("/keywords", status_code=201)
def add_keyword(data: KeywordInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(create_keyword(s, data))


@router.patch("/keywords/{keyword_id}")
def edit_keyword(keyword_id: str, data: KeywordPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(patch_keyword(s, require(s, TrackedKeyword, keyword_id), data))


@router.post("/keywords/bulk")
def bulk_keywords(data: KeywordBulk, runtime: Runtime):
    with runtime.db.session.begin() as s:
        objects = [require(s, TrackedKeyword, id) for id in set(data.ids)]
        if len({x.keyword_set_id for x in objects}) != 1:
            fail("Một batch chỉ thay đổi từ khóa trong cùng bộ.")
        if data.changes.keyword_text and len(objects) > 1:
            fail("Không đổi nhiều từ khóa thành cùng một tên.")
        for obj in objects:
            patch_keyword(s, obj, data.changes)
            s.flush()
        return {"updated": len(objects)}


@router.post("/keywords/{keyword_id}/delete")
def delete_keyword(keyword_id: str, data: Confirmation, runtime: Runtime):
    with runtime.db.session.begin() as s:
        obj = require(s, TrackedKeyword, keyword_id)
        if not data.confirm:
            fail("Cần xác nhận xóa từ khóa và lịch sử của từ khóa này.")
        activity(
            s, obj.keyword_set_id, "keyword_deleted", {"keyword_text": obj.keyword_text}
        )
        s.delete(obj)
        return {"deleted": True}


@router.post("/ranks", status_code=201)
def rank(data: RankInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(add_rank(s, data))


@router.post("/ranks/bulk")
def bulk_ranks(data: RankBulk, runtime: Runtime):
    with runtime.db.session.begin() as s:
        keys = [(r.keyword_id, r.week_number, r.profile_id) for r in data.rows]
        if len(set(keys)) != len(keys):
            fail("Batch có ô rank bị trùng.")
        rows = [view(add_rank(s, row)) for row in data.rows]
        return {"saved": len(rows), "rows": rows}


@router.get("/keywords/{keyword_id}/history")
def history(
    keyword_id: str,
    runtime: Runtime,
    profile_id: str,
    week: int | None = Query(default=None, ge=1, le=520),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    with runtime.db.session() as s:
        kw = require(s, TrackedKeyword, keyword_id)
        profile = require(s, SearchProfile, profile_id)
        if profile.keyword_set_id != kw.keyword_set_id:
            fail("Search Profile không thuộc bộ từ khóa.")
        q = (
            select(RankObservation, TrackingWeek.week_number)
            .join(TrackingWeek, TrackingWeek.id == RankObservation.tracking_week_id)
            .where(
                RankObservation.tracked_keyword_id == kw.id,
                RankObservation.search_profile_id == profile_id,
            )
        )
        if week:
            q = q.where(TrackingWeek.week_number == week)
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        records = s.execute(
            q.order_by(RankObservation.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        latest = latest_query(profile_id)
        rep = s.execute(
            select(RankObservation, TrackingWeek.week_number)
            .join(latest, latest.c.last_id == RankObservation.id)
            .join(TrackingWeek, TrackingWeek.id == RankObservation.tracking_week_id)
            .where(RankObservation.tracked_keyword_id == kw.id)
            .order_by(TrackingWeek.week_number)
        ).all()
        technical = []
        from app.technical.models import AuditURL, AuditRun, AuditProject

        if kw.target_url:
            evidence = s.execute(
                select(AuditURL, AuditRun)
                .join(AuditRun, AuditRun.id == AuditURL.audit_id)
                .join(AuditProject, AuditProject.id == AuditRun.project_id)
                .where(
                    AuditURL.url == kw.target_url,
                    AuditProject.source_type == "live",
                    AuditRun.status == "completed",
                )
                .order_by(AuditRun.started_at.desc())
                .limit(1)
            ).first()
            if evidence:
                technical = [
                    {
                        "url_id": evidence[0].id,
                        "audit_id": evidence[1].id,
                        "project_id": evidence[1].project_id,
                        "status_code": evidence[0].status_code,
                        "indexability": evidence[0].indexability,
                        "audited_at": evidence[1].started_at,
                    }
                ]
        imported = s.scalars(
            select(KeywordImport)
            .where(
                KeywordImport.keyword_set_id == kw.keyword_set_id,
                KeywordImport.status == "imported",
            )
            .order_by(KeywordImport.created_at.desc())
            .limit(20)
        )
        imported_metrics = []
        for job in imported:
            if job.data["mode"] == "full":
                for row in job.data["rows"]:
                    if normalize(row["keyword_text"]) == kw.normalized_keyword:
                        imported_metrics.append(
                            {
                                "source": "historical_spreadsheet_unverified",
                                "filename": job.filename,
                                "imported_at": job.created_at,
                                **{
                                    k: row.get(k)
                                    for k in ("clicks", "impressions", "position")
                                },
                            }
                        )
        return {
            "keyword": view(kw),
            "rows": [{**view(o), "week_number": n} for o, n in records],
            "total": total,
            "representatives": [{**view(o), "week_number": n} for o, n in rep],
            "technical": technical,
            "imported_metrics": imported_metrics,
        }


@router.get("/overview")
def summary(
    runtime: Runtime,
    set_id: str,
    profile_id: str,
    week: int = Query(default=1, ge=1, le=520),
    date_start: date | None = None,
    date_end: date | None = None,
    scope: Literal["property", "page"] = "property",
):
    start, end = period(date_start, date_end)
    with runtime.db.session() as s:
        ks = require(s, KeywordSet, set_id)
        return {
            **overview(s, ks, profile_id, week, start, end, scope),
            "trends": trends(s, set_id, profile_id),
        }


@router.post("/gsc-sync", status_code=202)
def sync(data: SyncInput, runtime: Runtime):
    return runtime.keywords.start(data)


@router.get("/gsc-sync/status")
def sync_status(runtime: Runtime, set_id: str):
    with runtime.db.session() as s:
        return [
            view(j)
            for j in s.scalars(
                select(KeywordSyncJob)
                .where(KeywordSyncJob.keyword_set_id == set_id)
                .order_by(KeywordSyncJob.created_at.desc())
                .limit(10)
            )
        ]


@router.post("/gsc-sync/{job_id}/cancel")
def cancel_sync(job_id: str, runtime: Runtime):
    with runtime.db.session.begin() as s:
        job = require(s, KeywordSyncJob, job_id)
        if job.status in ("queued", "running"):
            job.status = "cancelled"
            job.updated_at = now()
        return view(job)


@router.post("/import")
async def import_preview(
    runtime: Runtime,
    file: UploadFile = File(),
    set_id: str = Form(),
    profile_id: str = Form(),
    mode: str = Form(default="history"),
    duplicates: str = Form(default="skip"),
    mapping: str = Form(default="{}"),
):
    content = await file.read(100 * 1024 + 1)
    try:
        columns = json.loads(mapping)
    except ValueError:
        fail("Ánh xạ cần là JSON hợp lệ.")
    if not isinstance(columns, dict):
        fail("Ánh xạ cần là danh sách cột hợp lệ.")
    with runtime.db.session.begin() as s:
        ks = require(s, KeywordSet, set_id)
        profile = require(s, SearchProfile, profile_id)
        if profile.keyword_set_id != ks.id:
            fail("Search Profile không thuộc bộ từ khóa.")
        job = spreadsheets.preview(
            s, ks, profile, content, file.filename or "", mode, duplicates, columns
        )
        result = view(job)
        result["data"] = {
            k: v for k, v in job.data.items() if k not in ("raw_rows", "rows")
        }
        result["data"]["samples"] = job.data["rows"][:20]
        result["data"]["total_rows"] = len(job.data["rows"])
        return result


@router.post("/import/{import_id}/commit")
def import_commit(
    import_id: str,
    runtime: Runtime,
    confirm: bool = Body(),
    accept_rejected: bool = Body(default=False),
):
    with runtime.db.session.begin() as s:
        return spreadsheets.commit(
            s, require(s, KeywordImport, import_id), confirm, accept_rejected
        )


@router.get("/export")
def export(
    runtime: Runtime,
    set_id: str,
    profile_id: str,
    format: Literal["csv", "xlsx"] = "csv",
    week: int = Query(default=1, ge=1, le=520),
    date_start: date | None = None,
    date_end: date | None = None,
    scope: Literal["property", "page"] = "property",
    search: str = Query(default="", max_length=500),
    group_id: str = "",
    status: Literal["active", "paused", "archived", "all"] = "active",
    rank_filter: str = "",
    sort: str = "keyword",
    direction: str = "asc",
    min_clicks: int | None = Query(default=None, ge=0),
    min_impressions: int | None = Query(default=None, ge=0),
    max_position: float | None = Query(default=None, ge=1, allow_inf_nan=False),
):
    start, end = period(date_start, date_end)
    with runtime.db.session() as s:
        s.connection().exec_driver_sql("BEGIN")
        ks = require(s, KeywordSet, set_id)
        profile = require(s, SearchProfile, profile_id)
        q = query_rows(
            s,
            set_id,
            profile_id,
            week,
            start,
            end,
            scope,
            search,
            group_id,
            status,
            rank_filter,
            sort,
            direction,
            min_clicks,
            min_impressions,
            max_position,
        )
        records = s.execute(q.limit(5001)).all()
        if len(records) > 5000:
            fail("Xuất tối đa 5.000 từ khóa mỗi lần. Thu hẹp bộ lọc.")
        groups = {
            g.id: g.name
            for g in s.scalars(
                select(KeywordGroup).where(KeywordGroup.keyword_set_id == set_id)
            )
        }
        rows = []
        for offset in range(0, len(records), 100):
            chunk = records[offset : offset + 100]
            weeks = grid(s, chunk, profile_id)
            for record in chunk:
                row = row_view(s, record, ks, scope, weeks.get(record[0].id, {}))
                row["group_name"] = groups.get(row["group_id"], "")
                rows.append(row)
        metadata = {
            "Website": ks.settings["site_url"],
            "Bộ từ khóa": ks.name,
            "Kỳ GSC": start + " – " + end,
            "Phạm vi GSC": scope,
            "Search Profile": profile.name
            + " "
            + json.dumps(profile.config, ensure_ascii=False),
            "Ngày bắt đầu": ks.start_date,
            "Múi giờ": ks.timezone,
            "Xuất lúc UTC": now(),
            "Nguồn": "Rank MANUAL; GSC có thể thiếu do privacy/row limits; ô trống không phải 0.",
        }
        content, mime = spreadsheets.export_file(rows, metadata, format)
        return Response(
            content,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="keyword-tracking-{set_id[:8]}.{format}"',
                "X-Content-Type-Options": "nosniff",
            },
        )


@router.get("/summary")
def dashboard_keyword_summary(runtime: Runtime, site_id: str):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    with runtime.db.session() as s:
        ks = s.scalar(
            select(KeywordSet)
            .where(KeywordSet.site_id == site_id, KeywordSet.status == "active")
            .order_by(KeywordSet.created_at, KeywordSet.id)
            .limit(1)
        )
        if not ks:
            return None
        profile = s.scalar(
            select(SearchProfile)
            .where(SearchProfile.keyword_set_id == ks.id)
            .order_by(SearchProfile.created_at, SearchProfile.id)
            .limit(1)
        )
        week = max(
            1,
            min(
                520,
                (
                    datetime.now(ZoneInfo(ks.timezone)).date()
                    - date.fromisoformat(ks.start_date)
                ).days
                // 7
                + 1,
            ),
        )
        start, end = period()
        return {
            "keyword_set_id": ks.id,
            "name": ks.name,
            "profile_id": profile.id,
            "week": week,
            **overview(s, ks, profile.id, week, start, end, "property")["stats"],
        }


@router.post("/keywords/{keyword_id}/move")
def move_keyword(
    keyword_id: str,
    runtime: Runtime,
    keyword_set_id: str = Body(),
    confirm: bool = Body(),
):
    with runtime.db.session.begin() as s:
        kw = require(s, TrackedKeyword, keyword_id)
        source = require(s, KeywordSet, kw.keyword_set_id)
        dest = require(s, KeywordSet, keyword_set_id)
        if not confirm:
            fail("Xác nhận chuyển từ khóa và lịch sử tương ứng.")
        if source.id == dest.id:
            return view(kw)
        if source.site_id != dest.site_id:
            fail("Chỉ chuyển giữa các bộ của cùng website.")
        if source.start_date != dest.start_date or source.timezone != dest.timezone:
            fail(
                "Bộ đích phải có cùng lịch và múi giờ để giữ ý nghĩa tuần. Nếu khác lịch, xuất rồi nhập lịch sử với ánh xạ rõ ràng."
            )
        if s.scalar(
            select(TrackedKeyword.id).where(
                TrackedKeyword.keyword_set_id == dest.id,
                TrackedKeyword.normalized_keyword == kw.normalized_keyword,
            )
        ):
            fail("Bộ đích đã có từ khóa này.", "duplicate_keyword", 409)
        profiles = {
            p.id: p
            for p in s.scalars(
                select(SearchProfile).where(SearchProfile.keyword_set_id == source.id)
            )
        }
        destination = list(
            s.scalars(
                select(SearchProfile).where(SearchProfile.keyword_set_id == dest.id)
            )
        )
        mapping = {}
        used_profiles = set()
        for old in profiles.values():
            target = next(
                (
                    p
                    for p in destination
                    if p.config == old.config
                    and p.name == old.name
                    and p.id not in used_profiles
                ),
                None,
            )
            if not target:
                target = SearchProfile(
                    id=uid(),
                    keyword_set_id=dest.id,
                    name=old.name,
                    config=old.config.copy(),
                    created_at=now(),
                    updated_at=now(),
                )
                s.add(target)
                s.flush()
                destination.append(target)
            mapping[old.id] = target.id
            used_profiles.add(target.id)
        observations = s.scalars(
            select(RankObservation).where(RankObservation.tracked_keyword_id == kw.id)
        ).all()
        week_map = {
            w.id: w.week_number
            for w in s.scalars(
                select(TrackingWeek).where(TrackingWeek.keyword_set_id == source.id)
            )
        }
        ensure_weeks(
            s, dest, max([35] + [week_map[o.tracking_week_id] for o in observations])
        )
        dest_weeks = {
            w.week_number: w.id
            for w in s.scalars(
                select(TrackingWeek).where(TrackingWeek.keyword_set_id == dest.id)
            )
        }
        for obs in observations:
            obs.tracking_week_id = dest_weeks[week_map[obs.tracking_week_id]]
            obs.search_profile_id = mapping[obs.search_profile_id]
        activity(
            s,
            source.id,
            "keyword_moved_out",
            {"to_set": dest.id, "observations": len(observations)},
            kw.id,
        )
        kw.keyword_set_id = dest.id
        kw.group_id = None
        kw.updated_at = now()
        activity(
            s,
            dest.id,
            "keyword_moved_in",
            {"from_set": source.id, "observations": len(observations)},
            kw.id,
        )
        return view(kw)
