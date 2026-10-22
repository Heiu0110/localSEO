import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.gsc.dates import now
from app.gsc.errors import GSCError
from .models import *


def uid():
    return uuid4().hex


def fail(message, code="keyword_validation", status=422):
    raise GSCError(code, message, status)


def view(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def require(session, model, id):
    obj = session.get(model, id)
    if not obj:
        fail("Không tìm thấy dữ liệu Keyword Tracking.", "keyword_not_found", 404)
    return obj


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def safe_url(value):
    if not value:
        return ""
    try:
        p = urlsplit(value)
        if (
            p.scheme not in ("https", "http")
            or not p.hostname
            or p.username
            or p.password
            or p.port not in (None, 80, 443)
        ):
            raise ValueError()
        if any(ord(c) < 33 for c in value) or "\\" in value:
            raise ValueError()
        host = p.hostname.encode("idna").decode().lower()
        return urlunsplit((p.scheme, host, p.path or "/", p.query, ""))
    except (ValueError, UnicodeError):
        fail("URL cần là HTTP/HTTPS hợp lệ, không chứa mật khẩu hoặc cổng tùy ý.")


def week_dates(start, number):
    first = date.fromisoformat(start) + timedelta(days=7 * (number - 1))
    return first.isoformat(), (first + timedelta(days=6)).isoformat()


def ensure_weeks(session, ks, count=35):
    existing = {
        x.week_number
        for x in session.scalars(
            select(TrackingWeek).where(TrackingWeek.keyword_set_id == ks.id)
        )
    }
    for n in range(1, count + 1):
        if n not in existing:
            a, b = week_dates(ks.start_date, n)
            session.add(
                TrackingWeek(
                    id=uid(),
                    keyword_set_id=ks.id,
                    week_number=n,
                    start_date=a,
                    end_date=b,
                )
            )
    session.flush()


def activity(session, set_id, action, data, keyword=None):
    session.add(
        TrackingActivity(
            keyword_set_id=set_id,
            keyword_id=keyword,
            action=action,
            data=data,
            created_at=now(),
        )
    )


def create_keyword(session, data):
    ks = require(session, KeywordSet, data.keyword_set_id)
    norm = normalize(data.keyword_text)
    if not norm:
        fail("Từ khóa không được để trống.")
    if session.scalar(
        select(TrackedKeyword).where(
            TrackedKeyword.keyword_set_id == ks.id,
            TrackedKeyword.normalized_keyword == norm,
        )
    ):
        fail(
            "Từ khóa đã tồn tại trong bộ này. Dùng bộ hoặc Search Profile riêng cho chuỗi theo dõi khác.",
            "duplicate_keyword",
            409,
        )
    if (
        data.group_id
        and require(session, KeywordGroup, data.group_id).keyword_set_id != ks.id
    ):
        fail("Nhóm không thuộc bộ từ khóa.")
    target = safe_url(data.target_url)
    mode = data.match_mode or ("exact_url" if target else "domain")
    if mode == "exact_url" and not target:
        fail("Exact Target URL cần URL đích.")
    values = data.model_dump(exclude={"match_mode", "target_url"})
    obj = TrackedKeyword(
        id=uid(),
        **values,
        normalized_keyword=norm,
        target_url=target,
        match_mode=mode,
        created_at=now(),
        updated_at=now(),
    )
    session.add(obj)
    session.flush()
    activity(session, ks.id, "keyword_added", {}, obj.id)
    return obj


def patch_keyword(session, obj, data):
    values = data.model_dump(exclude_unset=True)
    if "keyword_set_id" in values and values["keyword_set_id"] != obj.keyword_set_id:
        target = require(session, KeywordSet, values["keyword_set_id"])
        source = require(session, KeywordSet, obj.keyword_set_id)
        # Preserve assigned weeks and profile identities. Rehoming history would silently change its meaning.
        if session.scalar(
            select(RankObservation.id)
            .where(RankObservation.tracked_keyword_id == obj.id)
            .limit(1)
        ):
            fail(
                "Từ khóa có lịch sử: lưu trữ bản cũ và thêm vào bộ mới để giữ nguyên lịch và Search Profile."
            )
        if target.site_id != source.site_id:
            fail("Chỉ chuyển từ khóa giữa các bộ của cùng website.")
        values.setdefault("group_id", None)
    dest = values.get("keyword_set_id", obj.keyword_set_id)
    norm = normalize(values.get("keyword_text") or obj.keyword_text)
    duplicate = session.scalar(
        select(TrackedKeyword.id).where(
            TrackedKeyword.keyword_set_id == dest,
            TrackedKeyword.normalized_keyword == norm,
            TrackedKeyword.id != obj.id,
        )
    )
    if duplicate:
        fail("Từ khóa bị trùng trong bộ đích.", "duplicate_keyword", 409)
    if (
        values.get("group_id")
        and require(session, KeywordGroup, values["group_id"]).keyword_set_id != dest
    ):
        fail("Nhóm không thuộc bộ từ khóa.")
    if "target_url" in values:
        values["target_url"] = safe_url(values["target_url"] or "")
    if (values.get("match_mode") or obj.match_mode) == "exact_url" and not values.get(
        "target_url", obj.target_url
    ):
        fail("Exact Target URL cần URL đích.")
    before = {k: getattr(obj, k) for k in values}
    for k, v in values.items():
        if v is None and k != "group_id":
            fail("Trường dữ liệu không được null.")
        setattr(obj, k, v)
    obj.normalized_keyword = norm
    obj.updated_at = now()
    activity(
        session, dest, "keyword_updated", {"before": before, "after": values}, obj.id
    )
    return obj


def parse_rank(value, depth):
    v = value.strip().upper()
    if not v:
        return "NOT_CHECKED", None
    if v == "NA":
        return "NOT_FOUND", None
    if not re.fullmatch(r"[0-9]+", v) or not 1 <= int(v) <= depth:
        fail(f"Rank cần là số nguyên 1–{depth}, NA hoặc để trống.")
    return "FOUND", int(v)


def series_key(keyword, profile):
    return hashlib.sha256(
        json.dumps(
            {
                "profile": profile.config,
                "query": keyword.keyword_text,
                "target": keyword.target_url,
                "mode": keyword.match_mode,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def add_rank(session, data, imported=False):
    kw = require(session, TrackedKeyword, data.keyword_id)
    ks = require(session, KeywordSet, kw.keyword_set_id)
    profile = require(session, SearchProfile, data.profile_id)
    if profile.keyword_set_id != ks.id:
        fail("Search Profile không thuộc bộ từ khóa.")
    status, rank = parse_rank(data.value, profile.config["search_depth"])
    ensure_weeks(session, ks, max(35, data.week_number))
    week = session.scalar(
        select(TrackingWeek).where(
            TrackingWeek.keyword_set_id == ks.id,
            TrackingWeek.week_number == data.week_number,
        )
    )
    stamp = data.checked_at
    imported = imported or data.timestamp_precision == "week_only"
    if not imported:
        stamp = stamp or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            fail("Thời điểm kiểm tra cần có múi giờ.")
        if stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
            fail("Không thể ghi một lần kiểm tra trong tương lai.")
        local = stamp.astimezone(ZoneInfo(ks.timezone)).date().isoformat()
        if not week.start_date <= local <= week.end_date:
            fail(
                "Thời điểm kiểm tra không nằm trong tuần đã chọn. Dùng nhập lịch sử nếu chỉ biết tuần."
            )
        stamp = stamp.astimezone(timezone.utc).isoformat()
    else:
        stamp = None
    matched = safe_url(data.matched_url)
    if status != "FOUND" and matched:
        fail("Chỉ rank FOUND được có URL quan sát.")
    if matched and kw.match_mode == "exact_url" and matched != kw.target_url:
        fail("URL quan sát khác Exact Target URL.")
    if matched and kw.match_mode == "domain":
        site = ks.settings["site_url"]
        host = (
            site.removeprefix("sc-domain:")
            if site.startswith("sc-domain:")
            else urlsplit(site if "://" in site else "https://" + site).hostname
        )
        mh = urlsplit(matched).hostname
        if not host or not (mh == host or mh.endswith("." + host)):
            fail("URL quan sát không thuộc website.")
    obs = RankObservation(
        tracked_keyword_id=kw.id,
        tracking_week_id=week.id,
        search_profile_id=profile.id,
        checked_at=stamp,
        timestamp_precision="week_only" if imported else "exact",
        checked_by=data.checked_by,
        rank_status=status,
        rank_value=rank,
        method="MANUAL",
        matched_url=matched,
        target_url_snapshot=kw.target_url,
        match_mode=kw.match_mode,
        profile_snapshot={
            **profile.config,
            "name": profile.name,
            "keyword_text": kw.keyword_text,
        },
        series_key=series_key(kw, profile),
        notes=data.notes,
        created_at=now(),
    )
    session.add(obs)
    session.flush()
    activity(
        session,
        ks.id,
        "rank_recorded",
        {"observation_id": obs.id, "week": data.week_number, "status": status},
        kw.id,
    )
    return obs


def change(prev, current):
    if not current or current["rank_status"] == "NOT_CHECKED":
        return {"state": "awaiting", "value": None}
    if not prev or prev["rank_status"] == "NOT_CHECKED":
        return {"state": "new_observation", "value": None}
    if prev["series_key"] != current["series_key"]:
        return {"state": "incomparable", "value": None}
    a, b = prev["rank_status"], current["rank_status"]
    if a == "FOUND" and b == "FOUND":
        delta = prev["rank_value"] - current["rank_value"]
        return {
            "state": (
                "improved" if delta > 0 else "dropped" if delta < 0 else "unchanged"
            ),
            "value": delta,
        }
    return {
        "state": (
            "entered" if b == "FOUND" else "lost" if a == "FOUND" else "still_not_found"
        ),
        "value": None,
    }
