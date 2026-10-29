"""Read adapters for the existing Phase 6 registry, with server-injected website scope."""

from sqlalchemy import select, func
from pydantic import Field
from app.ai.schemas import Input
from app.ai.common import fail, view
from .models import (
    ResearchProject,
    ResearchKeyword,
    ResearchCluster,
    ResearchOpportunity,
    SerpSnapshot,
)
from . import core, analysis, serp
from app.keywords.core import normalize


class ResearchArgs(Input):
    research_id: str | None = Field(default=None, max_length=100)
    search: str = Field(default="", max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class SnapshotArgs(ResearchArgs):
    snapshot_id: str = Field(min_length=1, max_length=100)


class CompareArgs(ResearchArgs):
    a: str = Field(min_length=1, max_length=100)
    b: str = Field(min_length=1, max_length=100)


SPECS = {
    "get_keyword_research_summary": (
        ResearchArgs,
        "Dự án Research và nguồn đã lưu, không discovery mới.",
    ),
    "get_research_keyword_candidates": (
        ResearchArgs,
        "Ứng viên và provenance trong Research, có trạng thái review.",
    ),
    "get_keyword_clusters": (
        ResearchArgs,
        "Cluster manual/assisted đã lưu, không tự sửa hoặc duyệt.",
    ),
    "get_serp_snapshot": (
        SnapshotArgs,
        "Snapshot SERP nhập bất biến; không gọi provider/crawl.",
    ),
    "compare_serp_snapshots": (
        CompareArgs,
        "So sánh URL organic với cùng locale/device/source/depth, từ chối context không tương thích.",
    ),
    "get_competitor_serp_summary": (
        ResearchArgs,
        "Domain quan sát trong mẫu SERP, mẫu số theo cohort.",
    ),
    "get_keyword_opportunities": (
        ResearchArgs,
        "Đề xuất theo quy tắc và bằng chứng đã lưu; không refresh/write.",
    ),
}


def execute(registry, name, args, p):
    with registry.db.session() as s:
        q = select(ResearchProject).where(ResearchProject.local_project_id == p["id"])
        if args.research_id:
            q = q.where(ResearchProject.id == args.research_id)
        projects = list(
            s.scalars(q.order_by(ResearchProject.updated_at.desc()).limit(10))
        )
        if args.research_id and not projects:
            fail(
                "ai_scope_violation",
                "Research project không thuộc website của hội thoại.",
                403,
            )
        selected = projects[0] if projects else None
        record = selected.id if selected else None
        collected = selected.updated_at if selected else None
        if not selected:
            data = {
                "available": False,
                "reason": "Website chưa có Research project đã lưu.",
            }
        elif name == "get_keyword_research_summary":
            data = {
                "available": True,
                "projects": [core.project_view(s, x) for x in projects],
                "limitations": core.LIMITATIONS,
            }
        elif name == "get_research_keyword_candidates":
            rows = list(
                s.scalars(
                    select(ResearchKeyword)
                    .where(
                        ResearchKeyword.project_id == selected.id,
                        ResearchKeyword.normalized_keyword.contains(
                            args.search, autoescape=True
                        ),
                    )
                    .order_by(ResearchKeyword.normalized_keyword)
                    .limit(args.limit)
                )
            )
            data = {
                "rows": core.keyword_views(s, rows),
                "scope": "stored_candidates_only",
            }
        elif name == "get_keyword_clusters":
            rows = list(
                s.scalars(
                    select(ResearchCluster)
                    .where(ResearchCluster.project_id == selected.id)
                    .order_by(ResearchCluster.name)
                    .limit(args.limit)
                )
            )
            data = {"rows": [analysis.cluster_view(s, c) for c in rows]}
        elif name == "get_serp_snapshot":
            snap = core.scoped(s, SerpSnapshot, args.snapshot_id, selected.id)
            data = serp.snapshot_view(s, snap, registry.db, limit=10)
            record = snap.id
            collected = snap.collected_at
        elif name == "compare_serp_snapshots":
            data = serp.compare(s, selected, args.a, args.b)
        elif name == "get_competitor_serp_summary":
            data = serp.competitors(s, selected)
        else:
            data = {
                "rows": [
                    view(o)
                    for o in s.scalars(
                        select(ResearchOpportunity)
                        .where(ResearchOpportunity.project_id == selected.id)
                        .order_by(ResearchOpportunity.updated_at.desc())
                        .limit(args.limit)
                    )
                ]
            }
        return registry.evidence(
            p,
            "Keyword Research",
            data,
            record=record,
            scope="stored_research_project",
            collected=collected,
            reference=(
                "/keyword-research?research=" + record
                if record
                else "/keyword-research"
            ),
            completeness="bounded_stored_evidence",
            limitations=core.LIMITATIONS,
        )
