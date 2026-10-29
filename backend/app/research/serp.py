"""Immutable imported observations. Never fetches search engines or result URLs."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit
from sqlalchemy import select, func
from app.ai.common import uid, now, view, fail
from app.ai.context import project as local_project, host
from app.keywords.core import safe_url
from .models import SerpSnapshot, SerpResult, ResearchKeyword, ResearchProject
from .schemas import SerpInput
from .core import scoped

PROFILE = (
    "provider",
    "search_engine",
    "search_type",
    "country",
    "language",
    "location",
    "device",
    "requested_depth",
)


def save_snapshot(s, p, raw):
    data = SerpInput.model_validate(raw)
    k = scoped(s, ResearchKeyword, data.keyword_id, p.id)
    if (k.country, k.language) != (data.country, data.language):
        fail("research_locale", "Locale snapshot khác locale của keyword.")
    identity = hashlib.sha256(
        json.dumps(
            data.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = s.scalar(
        select(SerpSnapshot).where(
            SerpSnapshot.project_id == p.id, SerpSnapshot.identity == identity
        )
    )
    if existing:
        return {"snapshot_id": existing.id, "created": 0, "skipped": 1}
    if (
        s.scalar(
            select(func.count())
            .select_from(SerpSnapshot)
            .where(SerpSnapshot.project_id == p.id)
        )
        >= 500
    ):
        fail("research_limit", "Tối đa 500 snapshots/dự án.")
    values = data.model_dump(exclude={"results", "notes", "request_id", "collected_at"})
    snapshot = SerpSnapshot(
        id=uid(),
        project_id=p.id,
        **values,
        identity=identity,
        returned_depth=max((r.organic_position or 0 for r in data.results), default=0),
        collected_at=data.collected_at.astimezone(timezone.utc).isoformat(),
        data={
            "version": 1,
            "origin": "user_imported",
            "request_id": data.request_id,
            "notes": data.notes,
            "rank_definition": "organic_position_supplied_v1",
            "cost": None,
            "imported_at": now(),
            "features_coverage": "only_explicit_features",
            "provider_metadata_reference": data.request_id or "manual",
        },
    )
    s.add(snapshot)
    s.flush()
    for row in data.results:
        url = safe_url(row.url)
        s.add(
            SerpResult(
                id=uid(),
                snapshot_id=snapshot.id,
                **row.model_dump(exclude={"url"}),
                url=row.url,
                normalized_url=url,
                domain=urlsplit(url).hostname or "",
            )
        )
    s.flush()
    return {"snapshot_id": snapshot.id, "created": 1, "skipped": 0}


def snapshot_view(s, snap, db=None, limit=100):
    k = s.get(ResearchKeyword, snap.keyword_id)
    rows = list(
        s.scalars(
            select(SerpResult)
            .where(SerpResult.snapshot_id == snap.id)
            .order_by(SerpResult.organic_position.asc().nullslast(), SerpResult.id)
            .limit(limit)
        )
    )
    age = max(
        0, (datetime.now(timezone.utc) - datetime.fromisoformat(snap.collected_at)).days
    )
    presence = None
    if db:
        rp = s.get(ResearchProject, snap.project_id)
        if rp.local_project_id:
            website = local_project(db, rp.local_project_id)
            domain = host(website["site_url"])
            matches = [
                view(r)
                for r in rows
                if r.result_type == "organic"
                and domain
                and (r.domain == domain or r.domain.endswith("." + domain))
            ]
            presence = {
                "site_url": website["site_url"],
                "status": "observed" if matches else "not_found_within_observed_top_n",
                "matches": matches,
                "limited_results": len(rows),
                "observed_top_n": snap.requested_depth,
            }
    return {
        **view(snap),
        "keyword_text": k.keyword_text,
        "selected_website_presence": presence,
        "results": [view(r) for r in rows],
        "age_days": age,
        "freshness": "stale" if age > 7 else "recent",
        "limitations": [
            "Dữ liệu nhập do người dùng cung cấp, chưa xác minh với provider.",
            f"Không thấy URL chỉ có nghĩa không thấy trong Top {snap.requested_depth} quan sát.",
            "GSC Average Position và rank MANUAL là nguồn độc lập; không được cập nhật từ snapshot.",
            "Feature vắng mặt không có nghĩa chắc chắn không xuất hiện; AI Overview không chứng minh AI citation.",
        ],
    }


def compare(s, p, a, b):
    a = scoped(s, SerpSnapshot, a, p.id)
    b = scoped(s, SerpSnapshot, b, p.id)
    reasons = [
        f"{key} khác nhau" for key in PROFILE if getattr(a, key) != getattr(b, key)
    ]
    if a.completeness != "complete_observed" or b.completeness != "complete_observed":
        reasons.append("Snapshot chưa đầy đủ trong Top N khai báo")
    if a.data.get("rank_definition") != b.data.get("rank_definition"):
        reasons.append("Định nghĩa organic rank khác nhau")
    if reasons:
        return {
            "comparable": False,
            "limitations": reasons,
            "snapshot_ids": [a.id, b.id],
            "overlap": None,
        }

    def positions(id):
        return {
            r.normalized_url: r.organic_position
            for r in s.scalars(
                select(SerpResult).where(
                    SerpResult.snapshot_id == id, SerpResult.result_type == "organic"
                )
            )
        }

    aa = positions(a.id)
    bb = positions(b.id)
    inter = set(aa) & set(bb)
    union = set(aa) | set(bb)
    return {
        "comparable": True,
        "snapshot_ids": [a.id, b.id],
        "same_keyword": a.keyword_id == b.keyword_id,
        "profile": {k: getattr(a, k) for k in PROFILE},
        "collected_at": [a.collected_at, b.collected_at],
        "overlap": len(inter) / len(union) if union else None,
        "definition": "intersection / union of normalized exact organic URLs; host lowercase, fragment removed, path/query preserved",
        "shared_urls": len(inter),
        "observed_urls": len(union),
        "changes": [
            {
                "url": u,
                "before": aa.get(u),
                "after": bb.get(u),
                "status": (
                    "observed_in_both"
                    if u in inter
                    else "not_found_within_observed_top_n"
                ),
            }
            for u in sorted(union)
        ][:100],
        "limitations": [
            "Các thời điểm khác nhau; overlap không chứng minh cùng intent hoặc nên dùng chung landing page.",
            "Nhiều URL cùng domain vẫn là các kết quả riêng.",
        ],
    }


def competitors(s, p):
    snapshots = list(
        s.scalars(
            select(SerpSnapshot)
            .where(SerpSnapshot.project_id == p.id)
            .order_by(SerpSnapshot.collected_at.desc(), SerpSnapshot.id)
        )
    )
    seen = set()
    cohorts = {}
    for snap in snapshots:
        key = tuple(getattr(snap, k) for k in PROFILE)
        dedup = (snap.keyword_id, key)
        if dedup in seen:
            continue
        seen.add(dedup)
        group = cohorts.setdefault(
            key,
            {
                "profile": dict(zip(PROFILE, key)),
                "sampled_serps": 0,
                "partial_snapshots": 0,
                "domains": {},
                "snapshot_ids": [],
            },
        )
        group["sampled_serps"] += 1
        group["partial_snapshots"] += int(snap.completeness != "complete_observed")
        group["snapshot_ids"].append(snap.id)
        domains = defaultdict(list)
        for r in s.scalars(
            select(SerpResult).where(
                SerpResult.snapshot_id == snap.id, SerpResult.result_type == "organic"
            )
        ):
            domains[r.domain].append(r)
        for domain, results in domains.items():
            d = group["domains"].setdefault(
                domain,
                {
                    "domain": domain,
                    "appearances": 0,
                    "observed_urls": [],
                    "best_observed_position": 1000,
                },
            )
            d["appearances"] += 1
            d["best_observed_position"] = min(
                d["best_observed_position"], min(r.organic_position for r in results)
            )
            d["observed_urls"] = list(
                dict.fromkeys(d["observed_urls"] + [r.url for r in results])
            )[:10]
    for g in cohorts.values():
        g["domains"] = sorted(
            g["domains"].values(), key=lambda d: (-d["appearances"], d["domain"])
        )[:50]
    return {
        "cohorts": list(cohorts.values())[:20],
        "cohort_count": len(cohorts),
        "limitations": [
            "Mỗi cohort chỉ dùng snapshot mới nhất của mỗi keyword, cùng provider/locale/device/location/depth.",
            "Mẫu quan sát có mẫu số sampled_serps; không phải thị phần hoặc traffic đối thủ.",
            "Snapshot cũ vẫn là bằng chứng lịch sử, không phải thứ hạng hiện tại.",
        ],
    }
