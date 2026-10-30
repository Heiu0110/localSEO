"""Human review is scoped to the current extraction revision, never source-content proof."""

from sqlalchemy import select
from .models import VisibilityReview
from . import core


def latest_review(s, observation):
    row = s.scalar(
        select(VisibilityReview)
        .where(
            VisibilityReview.project_id == observation.project_id,
            VisibilityReview.entity_type == "live_extraction",
            VisibilityReview.entity_id == observation.id,
        )
        .order_by(VisibilityReview.created_at.desc())
        .limit(1)
    )
    if not row:
        return None
    revision = core.latest_extraction(s, observation.id)
    if (
        revision
        and row.data.get("extraction_id") == revision.id
        and row.data.get("registry_hash") == revision.registry_hash
    ):
        return row
    return None
