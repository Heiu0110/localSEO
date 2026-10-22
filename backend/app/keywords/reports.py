from datetime import date
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import aliased
from app.gsc.dates import bounds
from .models import *
from .core import require, view, change, fail


def period(start=None, end=None, days=28):
    from datetime import timedelta

    end = end or bounds()[1]
    start = start or end - timedelta(days=days - 1)
    if start > end or (end - start).days > 500 or end > bounds()[1]:
        fail("Kỳ GSC cần tối đa 501 ngày và kết thúc trong vùng dữ liệu đã hoàn tất.")
    return start.isoformat(), end.isoformat()


def latest_query(profile_id, week_number=None):
    q = (
        select(
            RankObservation.tracked_keyword_id.label("keyword_id"),
            func.max(RankObservation.id).label("last_id"),
        )
        .join(TrackingWeek, TrackingWeek.id == RankObservation.tracking_week_id)
        .where(RankObservation.search_profile_id == profile_id)
    )
    if week_number is not None:
        q = q.where(TrackingWeek.week_number == week_number)
    else:
        q = q.add_columns(TrackingWeek.week_number).group_by(TrackingWeek.week_number)
    return q.group_by(RankObservation.tracked_keyword_id).subquery()


def query_rows(
    session,
    set_id,
    profile_id,
    week_number,
    start,
    end,
    scope="property",
    search="",
    group_id="",
    status="active",
    rank_filter="",
    sort="keyword",
    direction="asc",
    min_clicks=None,
    min_impressions=None,
    max_position=None,
):
    ks = require(session, KeywordSet, set_id)
    profile = require(session, SearchProfile, profile_id)
    if profile.keyword_set_id != ks.id:
        fail("Search Profile không thuộc bộ từ khóa.")
    a = latest_query(profile_id, week_number)
    b = latest_query(profile_id, week_number - 1)
    current = aliased(RankObservation)
    previous = aliased(RankObservation)
    metric = KeywordMetric
    q = (
        select(TrackedKeyword, current, previous, metric)
        .outerjoin(a, a.c.keyword_id == TrackedKeyword.id)
        .outerjoin(current, current.id == a.c.last_id)
        .outerjoin(b, b.c.keyword_id == TrackedKeyword.id)
        .outerjoin(previous, previous.id == b.c.last_id)
        .outerjoin(
            metric,
            and_(
                metric.keyword_id == TrackedKeyword.id,
                metric.scope == scope,
                metric.date_start == start,
                metric.date_end == end,
                metric.data["keyword_text"].as_string() == TrackedKeyword.keyword_text,
                or_(
                    scope == "property",
                    metric.data["target_url"].as_string() == TrackedKeyword.target_url,
                ),
            ),
        )
        .where(TrackedKeyword.keyword_set_id == set_id)
    )
    if search:
        needle = (
            "%"
            + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        q = q.where(
            or_(
                TrackedKeyword.keyword_text.ilike(needle, escape="\\"),
                TrackedKeyword.target_url.ilike(needle, escape="\\"),
            )
        )
    if group_id:
        q = q.where(TrackedKeyword.group_id == group_id)
    if status != "all":
        q = q.where(TrackedKeyword.status == status)
    if rank_filter == "unchecked":
        q = q.where(or_(current.id.is_(None), current.rank_status == "NOT_CHECKED"))
    elif rank_filter == "na":
        q = q.where(current.rank_status == "NOT_FOUND")
    elif rank_filter in ("top3", "top10", "top20", "found"):
        q = q.where(
            current.rank_status == "FOUND",
            current.rank_value
            <= {"top3": 3, "top10": 10, "top20": 20, "found": 1000}[rank_filter],
        )
    elif rank_filter:
        fail("Bộ lọc rank không hợp lệ.")
    clicks = metric.data["clicks"].as_integer()
    imps = metric.data["impressions"].as_integer()
    pos = metric.data["average_position"].as_float()
    if min_clicks is not None:
        q = q.where(clicks >= min_clicks)
    if min_impressions is not None:
        q = q.where(imps >= min_impressions)
    if max_position is not None:
        q = q.where(pos <= max_position)
    delta = case(
        (
            and_(
                previous.rank_status == "FOUND",
                current.rank_status == "FOUND",
                current.series_key == previous.series_key,
            ),
            previous.rank_value - current.rank_value,
        ),
        else_=None,
    )
    sorts = {
        "keyword": TrackedKeyword.normalized_keyword,
        "clicks": clicks,
        "impressions": imps,
        "position": pos,
        "rank": current.rank_value,
        "change": delta,
    }
    if sort not in sorts or direction not in ("asc", "desc"):
        fail("Cách sắp xếp không hợp lệ.")
    order = sorts[sort].desc() if direction == "desc" else sorts[sort].asc()
    return q.order_by(order.nulls_last(), TrackedKeyword.id)


def metric_view(metric, ks, scope, kw):
    if metric:
        return {**metric.data, "fetched_at": metric.fetched_at, "scope": scope}
    return {
        "status": "not_connected" if not ks.property_id else "not_synced",
        "clicks": None,
        "impressions": None,
        "ctr": None,
        "average_position": None,
        "scope": scope,
        "source": None,
        "target_url": kw.target_url,
    }


def row_view(session, record, ks, scope, weeks=None):
    kw, current, previous, metric = record
    result = view(kw)
    result["current"] = view(current) if current else None
    result["previous"] = view(previous) if previous else None
    result["change"] = change(result["previous"], result["current"])
    result["metrics"] = metric_view(metric, ks, scope, kw)
    result["weeks"] = weeks or {}
    indicators = []
    m = result["metrics"]
    if (
        m.get("impressions") is not None
        and m["impressions"] >= ks.settings.get("min_impressions", 100)
        and m.get("ctr", 1) < ks.settings.get("low_ctr", 0.02)
    ):
        indicators.append("low_ctr")
    if m.get("top_page") and kw.target_url and m["top_page"] != kw.target_url:
        indicators.append("url_mismatch")
    if result["change"]["state"] in ("dropped", "entered", "awaiting"):
        indicators.append(result["change"]["state"])
    result["indicators"] = indicators
    return result


def grid(session, records, profile_id, max_week=35):
    ids = [r[0].id for r in records]
    if not ids:
        return {}
    # Only history for the bounded table page and requested columns, never all observations.
    latest = latest_query(profile_id)
    rows = session.execute(
        select(RankObservation, TrackingWeek.week_number)
        .join(latest, RankObservation.id == latest.c.last_id)
        .join(TrackingWeek, TrackingWeek.id == RankObservation.tracking_week_id)
        .where(
            RankObservation.tracked_keyword_id.in_(ids),
            TrackingWeek.week_number <= max_week,
        )
    ).all()
    counts = dict(
        ((kid, n), cnt)
        for kid, n, cnt in session.execute(
            select(
                RankObservation.tracked_keyword_id,
                TrackingWeek.week_number,
                func.count(),
            )
            .join(TrackingWeek, TrackingWeek.id == RankObservation.tracking_week_id)
            .where(
                RankObservation.tracked_keyword_id.in_(ids),
                RankObservation.search_profile_id == profile_id,
                TrackingWeek.week_number <= max_week,
            )
            .group_by(RankObservation.tracked_keyword_id, TrackingWeek.week_number)
        )
    )
    result = {}
    for obs, n in rows:
        result.setdefault(obs.tracked_keyword_id, {})[str(n)] = {
            **view(obs),
            "count": counts[(obs.tracked_keyword_id, n)],
        }
    return result


def overview(session, ks, profile_id, week, start, end, scope):
    records = session.execute(
        query_rows(session, ks.id, profile_id, week, start, end, scope)
    ).all()
    stats = dict(
        total=len(records),
        top3=0,
        top10=0,
        top20=0,
        improved=0,
        dropped=0,
        not_found=0,
        not_checked=0,
        checked=0,
    )
    distribution = {
        "1–3": 0,
        "4–10": 0,
        "11–20": 0,
        "21+": 0,
        "NA": 0,
        "Chưa kiểm tra": 0,
    }
    groups = {}
    for record in records:
        row = row_view(session, record, ks, scope)
        cur = row["current"]
        state = cur["rank_status"] if cur else "NOT_CHECKED"
        group = groups.setdefault(
            row["group_id"] or "",
            {
                "total": 0,
                "checked": 0,
                "top10": 0,
                "numeric_count": 0,
                "rank_sum": 0,
                "comparable": 0,
            },
        )
        group["total"] += 1
        if state == "NOT_CHECKED":
            stats["not_checked"] += 1
            distribution["Chưa kiểm tra"] += 1
        else:
            stats["checked"] += 1
            group["checked"] += 1
            if state == "NOT_FOUND":
                stats["not_found"] += 1
                distribution["NA"] += 1
            else:
                v = cur["rank_value"]
                group["numeric_count"] += 1
                group["rank_sum"] += v
                for top in [3, 10, 20]:
                    stats[f"top{top}"] += v <= top
                group["top10"] += v <= 10
                distribution[
                    (
                        "1–3"
                        if v <= 3
                        else "4–10" if v <= 10 else "11–20" if v <= 20 else "21+"
                    )
                ] += 1
        if row["change"]["state"] in ("improved", "dropped", "unchanged"):
            group["comparable"] += 1
        if row["change"]["state"] in ("improved", "dropped"):
            stats[row["change"]["state"]] += 1
    return {
        "stats": stats,
        "distribution": [{"name": k, "value": v} for k, v in distribution.items()],
        "groups": [
            {
                "group_id": key,
                **value,
                "average_rank": (
                    value["rank_sum"] / value["numeric_count"]
                    if value["numeric_count"]
                    else None
                ),
            }
            for key, value in groups.items()
        ],
    }


def trends(session, set_id, profile_id):
    latest = latest_query(profile_id)
    rows = session.execute(
        select(
            TrackingWeek.week_number,
            RankObservation.rank_status,
            func.count(),
            func.avg(RankObservation.rank_value),
        )
        .join(RankObservation, RankObservation.tracking_week_id == TrackingWeek.id)
        .join(latest, latest.c.last_id == RankObservation.id)
        .join(TrackedKeyword, TrackedKeyword.id == RankObservation.tracked_keyword_id)
        .where(TrackingWeek.keyword_set_id == set_id, TrackedKeyword.status == "active")
        .group_by(TrackingWeek.week_number, RankObservation.rank_status)
    ).all()
    points = {}
    for n, status, count, avg in rows:
        p = points.setdefault(
            n, {"week": n, "found": 0, "not_found": 0, "average_rank": None}
        )
        if status == "FOUND":
            p.update(found=count, average_rank=avg)
        elif status == "NOT_FOUND":
            p["not_found"] = count
    return list(points.values())
