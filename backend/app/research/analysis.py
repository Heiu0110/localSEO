"""Explainable draft suggestions, no opaque SEO scores or autonomous approval."""

import re
from sqlalchemy import select
from app.ai.common import uid, now, view, fail
from app.ai.context import project as local_project, audit_run
from app.technical.models import AuditURL
from app.keywords.models import (
    RankObservation,
    TrackingWeek,
    SearchProfile,
    TrackedKeyword,
    KeywordSet,
)
from app.keywords.core import series_key
from .models import *
from .core import (
    sources,
    scoped,
    create_cluster,
    ClusterInput,
    intent_suggestion,
    event,
)
from .serp import compare


def tokens(text):
    return set(re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)) - {
        "là",
        "và",
        "của",
        "cho",
        "the",
        "a",
        "and",
    }


def suggest(s, p, method):
    keywords = list(
        s.scalars(
            select(ResearchKeyword)
            .where(
                ResearchKeyword.project_id == p.id,
                ResearchKeyword.cluster_id.is_(None),
                ResearchKeyword.status.notin_(["rejected", "archived"]),
            )
            .order_by(ResearchKeyword.normalized_keyword)
            .limit(200)
        )
    )
    if method == "serp_overlap" and not s.scalar(
        select(SerpSnapshot.id).where(SerpSnapshot.project_id == p.id).limit(1)
    ):
        return {
            "available": False,
            "reason": "Chưa có SERP đã nhập; không dựng kết quả giả.",
            "proposals": [],
        }
    profiles = {}
    if method == "serp_overlap":
        from .serp import PROFILE

        snapshots = list(
            s.scalars(
                select(SerpSnapshot)
                .where(SerpSnapshot.project_id == p.id)
                .order_by(SerpSnapshot.collected_at.desc())
            )
        )
        result_sets = {}
        for r in s.scalars(
            select(SerpResult)
            .join(SerpSnapshot, SerpSnapshot.id == SerpResult.snapshot_id)
            .where(SerpSnapshot.project_id == p.id, SerpResult.result_type == "organic")
        ):
            result_sets.setdefault(r.snapshot_id, set()).add(r.normalized_url)
        for snap in snapshots:
            if snap.completeness == "complete_observed":
                profiles.setdefault(snap.keyword_id, {}).setdefault(
                    tuple(getattr(snap, key) for key in PROFILE),
                    (snap, result_sets.get(snap.id, set())),
                )
    proposals = []
    used = set()
    # Anchor grouping avoids transitive chaining and incompatible locale/approved intent mixing.
    for a in keywords:
        if a.id in used:
            continue
        members = [a]
        evidence = []
        for b in keywords:
            if (
                b.id == a.id
                or b.id in used
                or (a.country, a.language) != (b.country, b.language)
            ):
                continue
            if a.intent != "unknown" and b.intent != "unknown" and a.intent != b.intent:
                continue
            if method == "lexical":
                ta, tb = tokens(a.normalized_keyword), tokens(b.normalized_keyword)
                shared = ta & tb
                ratio = len(shared) / len(ta | tb) if ta | tb else 0
                matched = (a.target_url and a.target_url == b.target_url) or (
                    len(shared) >= 2 and ratio >= 0.5
                )
                reason = {
                    "keyword_ids": [a.id, b.id],
                    "shared_tokens": sorted(shared),
                    "jaccard": ratio,
                    "same_target": bool(a.target_url and a.target_url == b.target_url),
                }
            else:
                match = None
                for profile, (x, urls_a) in profiles.get(a.id, {}).items():
                    other = profiles.get(b.id, {}).get(profile)
                    if other:
                        y, urls_b = other
                        union = urls_a | urls_b
                        ratio = len(urls_a & urls_b) / len(union) if union else 0
                        match = {
                            "snapshot_ids": [x.id, y.id],
                            "profile": dict(zip(PROFILE, profile)),
                            "timestamps": [x.collected_at, y.collected_at],
                            "overlap": ratio,
                            "definition": "exact normalized organic URL intersection / union",
                        }
                        break
                matched = bool(match and match["overlap"] >= 0.5)
                reason = match or {"available": False}
            if matched:
                members.append(b)
                evidence.append(reason)
            if len(members) >= 20:
                break
        if len(members) > 1:
            used.update(k.id for k in members)
            proposals.append(
                {
                    "name": a.keyword_text[:200],
                    "keyword_ids": [k.id for k in members],
                    "primary_keyword_id": a.id,
                    "intent": a.intent,
                    "method": method,
                    "status": "draft",
                    "confidence": "low",
                    "factors": evidence,
                    "limitations": "Lexical/SERP similarity không chứng minh tương đương ngữ nghĩa hoặc kiến trúc nội dung.",
                }
            )
        if len(proposals) >= 20:
            break
    return {
        "available": True,
        "method": method,
        "sample_limit": 200,
        "proposals": proposals,
        "limitations": [
            "Đề xuất chưa lưu/chưa duyệt. Chỉ xét tối đa 200 keyword chưa gán cluster."
        ],
    }


def cluster_view(s, c):
    members = list(
        s.scalars(
            select(ResearchKeyword)
            .where(ResearchKeyword.cluster_id == c.id)
            .order_by(ResearchKeyword.normalized_keyword)
            .limit(500)
        )
    )
    return {
        **view(c),
        "keyword_count": len(members),
        "keywords": [view(k) for k in members],
        "limitations": [
            "Không cộng volume thành unique demand; các close variants có thể chồng lấn."
        ],
    }


def target_suggestions(db, s, p, k):
    candidates = []
    for src in sources(s, [k.id])[k.id]:
        if src["provider"] == "Keyword Tracking":
            tracked = s.get(TrackedKeyword, src["reference"])
            if (
                tracked
                and s.get(KeywordSet, tracked.keyword_set_id).site_id
                == p.local_project_id
                and tracked.target_url
            ):
                candidates.append(
                    {
                        "url": tracked.target_url,
                        "kind": "tracking_existing",
                        "evidence": src["id"],
                        "reason": "URL đích đã lưu trong Tracking; chưa tự duyệt mapping Research.",
                    }
                )
    if p.local_project_id:
        run = audit_run(db, local_project(db, p.local_project_id))
        if run:
            kt = tokens(k.normalized_keyword)
            for u in s.scalars(
                select(AuditURL).where(AuditURL.audit_id == run.id).limit(2000)
            ):
                overlap = kt & tokens(u.title)
                if len(overlap) >= 2:
                    candidates.append(
                        {
                            "url": u.url,
                            "kind": "crawl_title_heuristic",
                            "evidence": u.id,
                            "title": u.title,
                            "reason": "Token trùng title: "
                            + ", ".join(sorted(overlap)),
                            "indexability": u.indexability,
                        }
                    )
                    if len(candidates) >= 10:
                        break
    return {
        "suggestions": candidates[:10],
        "status": "needs_review",
        "limitations": [
            "Không tự áp dụng URL; không suy ra query–page từ hai tập GSC độc lập.",
            "URL crawl/Tracking không chứng minh đang xếp hạng cho query này.",
        ],
    }


def rank_declines(s, k):
    declines = []
    for src in sources(s, [k.id])[k.id]:
        if src["provider"] != "Keyword Tracking":
            continue
        tracked = s.get(TrackedKeyword, src["reference"])
        if (
            not tracked
            or s.get(KeywordSet, tracked.keyword_set_id).site_id
            != s.get(ResearchProject, k.project_id).local_project_id
        ):
            continue
        for profile in s.scalars(
            select(SearchProfile).where(
                SearchProfile.keyword_set_id == tracked.keyword_set_id
            )
        ):
            observations = list(
                s.execute(
                    select(RankObservation, TrackingWeek)
                    .join(
                        TrackingWeek,
                        TrackingWeek.id == RankObservation.tracking_week_id,
                    )
                    .where(
                        RankObservation.tracked_keyword_id == tracked.id,
                        RankObservation.search_profile_id == profile.id,
                    )
                    .order_by(
                        TrackingWeek.week_number.desc(), RankObservation.id.desc()
                    )
                    .limit(1040)
                )
            )
            latest = {}
            for obs, week in observations:
                latest.setdefault(week.week_number, obs)
            if not latest:
                continue
            n = max(latest)
            a = latest[n]
            b = latest.get(n - 1)
            if (
                b
                and a.rank_status == b.rank_status == "FOUND"
                and a.series_key == b.series_key == series_key(tracked, profile)
                and a.rank_value > b.rank_value
            ):
                declines.append(
                    {
                        "current_observation": a.id,
                        "previous_observation": b.id,
                        "profile_id": profile.id,
                        "profile": profile.config,
                        "week": n,
                        "before": b.rank_value,
                        "after": a.rank_value,
                        "method": "MANUAL",
                    }
                )
    return declines[:5]


def refresh_opportunities(s, p):
    rows = list(
        s.scalars(
            select(ResearchKeyword)
            .where(
                ResearchKeyword.project_id == p.id,
                ResearchKeyword.status.notin_(["archived", "rejected"]),
            )
            .order_by(ResearchKeyword.id)
            .limit(5000)
        )
    )
    all_sources = sources(s, [k.id for k in rows])
    active = set()
    for k in rows:
        generated = []
        # Choose a single observation for GSC, never mix periods or sum providers.
        gsc = next(
            (
                src
                for src in all_sources[k.id]
                if any(m["metric_type"] == "gsc_impressions" for m in src["metrics"])
            ),
            None,
        )
        if gsc:
            metrics = {m["metric_type"]: m for m in gsc["metrics"]}
            imp = metrics.get("gsc_impressions", {}).get("value")
            ctr = metrics.get("gsc_ctr", {}).get("value")
            pos = metrics.get("gsc_position", {}).get("value")
            base = {
                "source_id": gsc["id"],
                "provider": gsc["provider"],
                "metrics": gsc["metrics"],
                "target_url": k.target_url,
                "mapping_status": k.mapping_status,
                "rules": p.settings,
            }
            if (
                imp is not None
                and imp >= p.settings["min_impressions"]
                and ctr is not None
                and ctr < p.settings["low_ctr"]
            ):
                generated.append(
                    (
                        "high_impressions_low_ctr",
                        "high",
                        "medium",
                        "Kiểm tra SERP, title và kỳ dữ liệu trước khi kết luận CTR thấp.",
                        base,
                    )
                )
            if (
                pos is not None
                and p.settings["near_min"] <= pos <= p.settings["near_max"]
            ):
                generated.append(
                    (
                        "near_top_average_position",
                        "medium",
                        "medium",
                        "Điều tra URL và intent; đây là GSC Average Position, không phải rank live.",
                        base,
                    )
                )
            if k.mapping_status != "approved":
                generated.append(
                    (
                        "visibility_without_mapping",
                        "medium",
                        "medium",
                        "Rà soát và duyệt target URL; không tự tạo URL.",
                        base,
                    )
                )
        if not k.target_url:
            generated.append(
                (
                    "candidate_content_gap",
                    "low",
                    "low",
                    "Đánh giá ứng viên thiếu mapping trong phạm vi Research; chưa kết luận content gap toàn thị trường.",
                    {"keyword_id": k.id, "scope": "selected_research_project"},
                )
            )
        declines = rank_declines(s, k)
        if declines:
            generated.append(
                (
                    "declining_manual_rank",
                    "high",
                    "medium",
                    "Đối chiếu hai tuần MANUAL cùng profile và kiểm tra SERP thủ công.",
                    {"observations": declines},
                )
            )
        for kind, priority, confidence, action, evidence in generated:
            active.add((k.id, kind))
            old = s.scalar(
                select(ResearchOpportunity).where(
                    ResearchOpportunity.keyword_id == k.id,
                    ResearchOpportunity.kind == kind,
                )
            )
            if not old:
                old = ResearchOpportunity(
                    id=uid(),
                    project_id=p.id,
                    keyword_id=k.id,
                    kind=kind,
                    priority=priority,
                    confidence=confidence,
                    proposed_action=action,
                    evidence=evidence,
                    status="draft",
                    notes="",
                    updated_at=now(),
                )
                s.add(old)
            elif old.status == "draft":
                old.evidence = evidence
                old.updated_at = now()
    # Reviewed evidence stays frozen. Obsolete drafts are labelled, never silently treated as current.
    for old in s.scalars(
        select(ResearchOpportunity).where(
            ResearchOpportunity.project_id == p.id,
            ResearchOpportunity.status == "draft",
        )
    ):
        if (old.keyword_id, old.kind) not in active:
            old.status = "archived"
            old.updated_at = now()
    s.flush()
    return {
        "evaluated_keywords": len(rows),
        "active_rules": len(active),
        "limitations": [
            "Ưu tiên nội bộ theo quy tắc, không phải điểm Google.",
            "CTR cần kiểm tra context SERP; dữ liệu cũ không trở thành hiện tại khi refresh.",
            "Emerging trend/cannibalization chưa suy luận khi thiếu bằng chứng.",
        ],
    }
