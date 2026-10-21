from uuid import uuid4

from sqlalchemy import func, select

from app.db.models import Connection, MetricFact, Property, SyncJob
from app.gsc.dates import now
from app.gsc.errors import GSCError
from app.gsc.schemas import PropertyView


def require_property(session, property_id: str, active: bool = False) -> Property:
    prop = session.get(Property, property_id)
    if not prop or (active and not prop.is_active):
        raise GSCError("property_not_found", "Không tìm thấy property đang hoạt động trong workspace.", 404)
    return prop


def register_properties(db, connection_id: str, entries: list[dict], source_type: str):
    with db.session.begin() as session:
        existing = {p.site_url: p for p in session.scalars(select(Property).where(Property.connection_id == connection_id))}
        for entry in entries:
            site_url = entry.get("siteUrl", "")
            if not (site_url.startswith("sc-domain:") or site_url.startswith(("http://", "https://"))):
                continue
            permission = entry.get("permissionLevel", "siteUnverifiedUser")
            if site_url not in existing:
                session.add(Property(id=str(uuid4()), connection_id=connection_id, site_url=site_url,
                                     display_name=site_url, property_type="domain" if site_url.startswith("sc-domain:") else "url_prefix",
                                     permission_level=permission, source_type=source_type, is_active=False, added_at=now()))
            else:
                existing[site_url].permission_level = permission
        for site_url, prop in existing.items():
            if site_url not in {entry.get("siteUrl") for entry in entries}:
                prop.permission_level = "unavailable"


def properties_view(db) -> list[PropertyView]:
    with db.session() as session:
        result = []
        for prop in session.scalars(select(Property).order_by(Property.added_at, Property.site_url)):
            start, end = session.execute(select(func.min(MetricFact.date), func.max(MetricFact.date)).where(
                MetricFact.property_id == prop.id, MetricFact.dataset_type == "site", MetricFact.search_type == "web")).one()
            job = session.scalar(select(SyncJob).where(SyncJob.property_id == prop.id).order_by(SyncJob.started_at.desc()).limit(1))
            view = PropertyView.model_validate(prop)
            view.local_start, view.local_end = start, end
            view.sync_status = job.status if job else "not_started"
            result.append(view)
        return result


def create_fixture_properties(db, client):
    stamp = now()
    with db.session.begin() as session:
        if not session.get(Connection, "fixture"):
            session.add(Connection(id="fixture", display_name="Bộ thử nghiệm SQLite", provider="fixture", status="fixture", scope="none", created_at=stamp, updated_at=stamp))
    register_properties(db, "fixture", client.sites(), "fixture")
