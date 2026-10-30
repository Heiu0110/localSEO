import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.database import Database
from app.db.models import Checkpoint, Connection, MetricFact, Property, SyncJob
from app.gsc.client import FixtureGSCClient, GoogleGSCClient, normalize_error
from app.gsc.dates import bounds
from app.gsc.errors import GSCError
from app.gsc.oauth import SCOPE
from app.gsc.repository import create_fixture_properties, properties_view
from app.gsc.runtime import Runtime, get_runtime
from app.gsc.schemas import SyncRequest
from app.gsc.sync import fetch_dataset
from app.main import app
from app.providers.sqlite_provider import SQLiteAnalyticsProvider, dimension_id


class MemoryVault:
    """Test-only vault. Never selectable by production configuration."""
    def __init__(self):
        self.values = {}
    def get(self, key): return self.values.get(key)
    def put(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)


@pytest.fixture
def runtime(tmp_path):
    value = Runtime(Database(tmp_path / "test.db"), MemoryVault())
    yield value
    value.sync.close()
    value.db.engine.dispose()


def prop(runtime):
    create_fixture_properties(runtime.db, FixtureGSCClient())
    result = next(p for p in properties_view(runtime.db) if p.site_url.startswith("sc-domain:"))
    with runtime.db.session.begin() as session:
        session.get(Property, result.id).is_active = True
    return result


def sync(runtime, property_id, days=14, search_type="web", mode="initial", end=None):
    end = end or bounds()[1]
    job = runtime.sync.start(SyncRequest(property_id=property_id, start_date=end - timedelta(days=days-1),
        end_date=end, search_type=search_type, sync_mode=mode), submit=False)
    runtime.sync.run(job.id)
    assert runtime.sync.job(job.id).status == "completed", runtime.sync.job(job.id)
    return runtime.sync.job(job.id)


def test_migration_idempotent_foreign_keys_wal_and_persistence(runtime):
    runtime.db.migrate()
    with runtime.db.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006_ai_visibility"
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
    p = prop(runtime)
    reopened = Database(runtime.db.path)
    reopened.migrate()
    assert properties_view(reopened)[0].id in {item.id for item in properties_view(runtime.db)}
    assert len(properties_view(runtime.db)) == 2
    create_fixture_properties(runtime.db, FixtureGSCClient())
    assert len(properties_view(runtime.db)) == 2
    assert {item.site_url for item in properties_view(runtime.db)} == {"sc-domain:fixture.example", "https://fixture.example/"}
    assert p.property_type == "domain"
    reopened.engine.dispose()


def test_idempotent_sync_site_totals_independent_dimensions_and_search_types(runtime):
    p = prop(runtime)
    sync(runtime, p.id)
    provider = SQLiteAnalyticsProvider(runtime.db)
    overview = provider.overview(p.id, 7)
    assert overview.has_data and overview.comparison_available
    points = provider.performance(p.id, 7).points
    assert overview.current.clicks == sum(point.metrics.clicks for point in points)
    assert overview.current.ctr == pytest.approx(overview.current.clicks / overview.current.impressions * 100)
    assert overview.current.position == pytest.approx(sum(point.metrics.position * point.metrics.impressions for point in points) / overview.current.impressions)
    queries = provider.dimensions(p.id, 7, "query")
    assert overview.current.clicks != sum(row.metrics.clicks for row in queries.rows)
    assert queries.coverage == "partial" and queries.warning
    with runtime.db.session() as session:
        count = session.scalar(select(func.count()).select_from(MetricFact))
    sync(runtime, p.id, mode="refresh")
    assert provider.overview(p.id, 7).current == overview.current
    with runtime.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MetricFact)) == count
        assert session.scalar(select(func.count()).select_from(Checkpoint)) == 14 * 5
    assert not SQLiteAnalyticsProvider(runtime.db, "image").overview(p.id, 7).has_data
    sync(runtime, p.id, search_type="image")
    assert SQLiteAnalyticsProvider(runtime.db, "image").overview(p.id, 7).current.clicks < overview.current.clicks
    assert provider.overview(p.id, 7).current == overview.current


def test_no_data_no_false_comparison_missing_series_and_no_query_page_join(runtime):
    p = prop(runtime)
    provider = SQLiteAnalyticsProvider(runtime.db)
    empty = provider.overview(p.id, 28)
    assert not empty.has_data and not empty.comparison_available
    assert all(point.metrics is None for point in provider.performance(p.id, 7).points)
    sync(runtime, p.id, days=3)
    overview = provider.overview(p.id, 7)
    assert overview.has_data and not overview.comparison_available
    assert overview.changes.clicks.delta is None and overview.changes.clicks.percent is None
    assert overview.coverage["current"]["available_days"] == 3
    assert sum(point.metrics is None for point in provider.performance(p.id, 7).points) == 4
    page = provider.dimensions(p.id, 7, "page").rows[0]
    detail = provider.page_detail(p.id, 7, page.id)
    assert detail.current == page.metrics
    assert detail.queries == [] and not detail.query_relationships_available


def test_empty_api_day_is_checkpoint_not_zero_fact(runtime):
    p = prop(runtime)
    day = bounds()[1].isoformat()
    runtime.sync.replace_dataset(p.id, day, "web", "site", [], "api_response", "byProperty")
    overview = SQLiteAnalyticsProvider(runtime.db).overview(p.id, 7)
    assert not overview.has_data
    assert overview.coverage["current"]["empty_days"] == 1
    with runtime.db.session() as session:
        assert session.scalar(select(func.count()).select_from(MetricFact)) == 0


def test_atomic_replacement_rollback_preserves_old_data(runtime):
    p = prop(runtime)
    sync(runtime, p.id, days=1)
    provider = SQLiteAnalyticsProvider(runtime.db)
    prior = provider.overview(p.id, 7).current
    row = {"dimension_value": "", "clicks": 1, "impressions": 10, "ctr": .1, "position": 2}
    with pytest.raises(IntegrityError):
        runtime.sync.replace_dataset(p.id, bounds()[1].isoformat(), "web", "site", [row, row], "api_response", "byProperty")
    assert provider.overview(p.id, 7).current == prior


def test_interruption_resume_incremental_and_cancellation(runtime):
    p = prop(runtime)
    end = bounds()[1]
    sync(runtime, p.id, days=20, end=end-timedelta(days=1))
    job = runtime.sync.start(SyncRequest(property_id=p.id, start_date=end-timedelta(days=19), end_date=end, sync_mode="incremental"), submit=False)
    assert job.total_days == 8  # latest stored - 6, plus newly available day
    with pytest.raises(GSCError, match="đồng bộ"):
        runtime.sync.start(SyncRequest(property_id=p.id, start_date=end, end_date=end), submit=False)
    runtime.sync.recover()
    assert runtime.sync.job(job.id).status == "partial"
    resumed = runtime.sync.start(SyncRequest(property_id=p.id, start_date=job.requested_date_start, end_date=end, sync_mode="resume"), submit=False)
    runtime.sync.run(resumed.id)
    assert runtime.sync.job(resumed.id).status == "completed"
    cancelled = runtime.sync.start(SyncRequest(property_id=p.id, start_date=end, end_date=end, sync_mode="refresh"), submit=False)
    runtime.sync.cancel(cancelled.id)
    runtime.sync.run(cancelled.id)
    assert runtime.sync.job(cancelled.id).status == "cancelled"


def test_dataset_pagination_ceiling_validation_and_failed_page_no_commit(runtime):
    p = prop(runtime)
    calls = []
    class ManyRows:
        def query(self, url, day, dataset, search_type, start, limit):
            calls.append(start)
            return {"responseAggregationType": "byProperty", "rows": [{"keys": [f"q{i}"], "clicks": 1, "impressions": 5, "position": 3} for i in range(start, start+25_000)]}
    rows, completeness, aggregation = fetch_dataset(ManyRows(), p, bounds()[1].isoformat(), "query", "web")
    assert calls == [0, 25_000] and len(rows) == 50_000 and completeness == "api_limited"
    class FailsSecondPage(ManyRows):
        def query(self, url, day, dataset, search_type, start, limit):
            if start: raise GSCError("quota_exceeded", "Quota", 429)
            return super().query(url, day, dataset, search_type, start, limit)
    with pytest.raises(GSCError):
        fetch_dataset(FailsSecondPage(), p, bounds()[1].isoformat(), "query", "web")
    with runtime.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Checkpoint)) == 0
    class WrongAggregation:
        def query(self, *args): return {"responseAggregationType": "byPage", "rows": []}
    with pytest.raises(GSCError, match="tổng hợp"):
        fetch_dataset(WrongAggregation(), p, bounds()[1].isoformat(), "site", "web")


def test_quota_backoff_permanent_permissions_and_refresh_expiry(runtime, monkeypatch):
    quota = HttpError(Response({"status": "429", "retry-after": "3"}), b'{"error":{"errors":[{"reason":"rateLimitExceeded"}]}}')
    assert normalize_error(quota).retryable and normalize_error(quota).retry_after == 3
    assert not normalize_error(HttpError(Response({"status": "403"}), b'{}')).retryable
    p = prop(runtime)
    runtime.oauth.vault.put(f"tokens:{p.connection_id}", {"client_id": "fake", "client_secret": "fixture-secret", "refresh_token": "test-only", "token": None})
    monkeypatch.setattr("google.oauth2.credentials.Credentials.refresh", Mock(side_effect=RefreshError("invalid_grant")))
    with pytest.raises(GSCError) as failure:
        runtime.oauth.credentials(p.connection_id)
    assert failure.value.code == "reauthorization_required"
    # Exercise actual retry policy without a network request.
    oauth = SimpleNamespace(credentials=Mock(side_effect=[GSCError("quota", "Wait", 429, True, 3)] * 4), mark_reauthorization=Mock())
    sleep, retry = Mock(), Mock()
    client = GoogleGSCClient(oauth, "test", retry, sleep)
    with pytest.raises(GSCError): client.sites()
    assert sleep.call_count == retry.call_count == 3
    assert all(call.args[0] >= 3 for call in sleep.call_args_list)


def client_config():
    return {"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fixture-only",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}


def test_oauth_desktop_pkce_scope_state_timeout_and_denial(runtime):
    with pytest.raises(GSCError): runtime.oauth.configure(b'{"web":{}}')
    with pytest.raises(GSCError): runtime.oauth.configure(json.dumps({"installed": {**client_config()["installed"], "token_uri": "https://evil.example/token"}}).encode())
    runtime.oauth.configure(json.dumps(client_config()).encode())
    result = runtime.oauth.start()
    assert "code_challenge=" in result["authorization_url"] and "code_challenge_method=S256" in result["authorization_url"]
    assert "webmasters.readonly" in result["authorization_url"]
    pending = runtime.oauth.pending
    with pytest.raises(GSCError): runtime.oauth.callback("invalid", "code", None)
    assert runtime.oauth.pending is pending
    with pytest.raises(GSCError): runtime.oauth.callback(pending.state, None, "access_denied")
    assert runtime.oauth.pending is None
    runtime.oauth.start()
    runtime.oauth.pending.expires = 0
    with pytest.raises(GSCError): runtime.oauth.callback(runtime.oauth.pending.state, "code", None)


def test_mutations_csrf_origin_api_export_and_mock_real_isolation(runtime):
    app.dependency_overrides[get_runtime] = lambda: runtime
    # Dashboard report resolver calls the cached runtime directly; patch it at source.
    import app.api.routes as dashboard_routes
    original = dashboard_routes.get_runtime
    dashboard_routes.get_runtime = lambda: runtime
    try:
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            assert client.post('/api/integrations/gsc/fixtures').status_code == 403
            token = client.get('/api/session').json()['csrf_token']
            headers = {'X-CSRF-Token': token, 'Origin': 'http://127.0.0.1:5173'}
            assert client.post('/api/integrations/gsc/fixtures', headers={**headers, 'Origin':'https://evil.example'}).status_code == 403
            configured = client.post('/api/integrations/gsc/configure', headers=headers,
                files={'file': ('desktop.json', json.dumps(client_config()), 'application/json')})
            assert configured.status_code == 200 and configured.json()['configured']
            assert 'client_secret' not in configured.text
            response = client.post('/api/integrations/gsc/fixtures', headers=headers)
            assert response.status_code == 200
            p = response.json()[0]
            assert client.post('/api/integrations/gsc/properties', headers=headers, json={'property_id':p['id'], 'is_active':True}).status_code == 200
            sync(runtime, p['id'], days=14)
            overview = client.get('/api/dashboard/overview', params={'site_id':p['id'], 'days':7}).json()
            assert overview['source']=='fixture' and overview['current']['clicks'] > 0
            assert client.get('/api/dashboard/overview', params={'site_id':'xuong-may'}).json()['source']=='mock'
            params={'property_id':p['id'], 'start_date':overview['period']['start'], 'end_date':overview['period']['end'], 'search_type':'web'}
            pages=client.get('/api/gsc/analytics/pages',params={**params,'page_size':5})
            assert pages.status_code==200 and len(pages.json()['rows'])==5 and pages.json()['total_rows']==12
            assert client.get('/api/gsc/analytics/pages',params={**params,'sort':'DROP TABLE'}).status_code==422
            assert client.get('/api/gsc/analytics/pages',params={**params,'search':'%'}).json()['rows']==[]
            exported=client.get('/api/gsc/export/pages',params={**params,'search':'trang-1'})
            assert exported.status_code==200 and exported.text.startswith('\ufeff')
            assert 'fixture' in exported.text and 'refresh_token' not in exported.text
            payload=json.dumps(client.get('/api/integrations/gsc/status').json())
            assert 'client_secret' not in payload and 'refresh_token' not in payload
            # Removing from workspace retains the metrics for later reactivation.
            client.post('/api/integrations/gsc/properties',headers=headers,json={'property_id':p['id'],'is_active':False})
            assert client.get('/api/dashboard/overview',params={'site_id':p['id']}).status_code==404
            with runtime.db.session() as session:
                assert session.scalar(select(func.count()).select_from(MetricFact))>0
    finally:
        dashboard_routes.get_runtime = original
        app.dependency_overrides.clear()


@pytest.mark.parametrize("revocation_status", [200, 503])
def test_oauth_success_secure_persistence_and_disconnect_semantics(runtime, monkeypatch, revocation_status):
    runtime.oauth.configure(json.dumps(client_config()).encode())
    runtime.oauth.start()
    pending = runtime.oauth.pending
    payload = {"refresh_token": "fixture-refresh-never-in-sqlite", "token": "fixture-access-never-in-api", "client_id": "test.apps.googleusercontent.com", "client_secret": "fixture-secret-never-in-sqlite"}
    pending.flow = SimpleNamespace(fetch_token=Mock(), credentials=SimpleNamespace(refresh_token=payload["refresh_token"], to_json=lambda: json.dumps(payload)))
    runtime.oauth.callback(pending.state, "test-code", None)
    assert runtime.oauth.status().status == "connected"
    assert runtime.oauth.vault.get(f"tokens:{pending.connection_id}")["refresh_token"] == payload["refresh_token"]
    with runtime.db.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    database_content = runtime.db.path.read_bytes()
    assert all(secret.encode() not in database_content for secret in (payload["refresh_token"], payload["token"], payload["client_secret"]))
    monkeypatch.setattr("app.gsc.oauth.httpx.post", Mock(return_value=SimpleNamespace(status_code=revocation_status)))
    result = runtime.oauth.disconnect(True)
    assert result.local_credentials_removed and result.remote_revoked == (revocation_status == 200)
    assert runtime.oauth.vault.get(f"tokens:{pending.connection_id}") is None
    assert runtime.oauth.status().status == "disconnected"


def test_vault_rejects_plaintext_backend(runtime, monkeypatch):
    from app.gsc.vault import CredentialVault
    class InsecureBackend:
        priority = 100
    InsecureBackend.__module__ = "keyrings.alt.file"
    monkeypatch.setattr("keyring.get_keyring", lambda: InsecureBackend())
    with pytest.raises(GSCError) as failure:
        CredentialVault().put("tokens:test", {"refresh_token": "fixture-only"})
    assert failure.value.code == "secure_storage_unavailable"


def test_missing_dimension_rows_do_not_claim_100_percent_traffic_loss(runtime):
    p = prop(runtime)
    sync(runtime, p.id)
    end = bounds()[1]
    row = {"dimension_value": "new-query", "clicks": 1, "impressions": 10, "ctr": .1, "position": 2}
    for offset in range(7):
        runtime.sync.replace_dataset(p.id, (end-timedelta(days=offset)).isoformat(), "web", "query", [row], "api_limited", "byProperty")
    report = SQLiteAnalyticsProvider(runtime.db).dimensions(p.id, 7, "query", page_size=100)
    assert report.completeness == "api_limited"
    assert any(r.current_available is False and r.click_change_pct is None for r in report.rows)
    assert all(r.click_change_pct is None for r in report.rows)


def test_sqlite_backup_includes_wal_and_does_not_overwrite(runtime, tmp_path):
    import subprocess
    import sys
    import sqlite3
    p = prop(runtime)
    sync(runtime, p.id, days=1)
    script = Path(__file__).resolve().parents[2] / "scripts" / "backup_database.py"
    target = tmp_path / "backup.db"
    command = [sys.executable, str(script), "--source", str(runtime.db.path), "--destination", str(target)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT count(*) FROM gsc_daily_metrics").fetchone()[0] > 0
    assert subprocess.run(command, capture_output=True).returncode != 0


def test_google_client_request_scope_and_callback_logging(runtime, monkeypatch):
    import logging
    from google.oauth2.credentials import Credentials
    from app.main import RedactOAuthAccessLog
    credentials = Credentials(token="fixture-token", scopes=[SCOPE])
    oauth = SimpleNamespace(credentials=Mock(return_value=credentials), save_credentials=Mock())
    query = Mock(return_value=SimpleNamespace(execute=Mock(return_value={"rows": [], "responseAggregationType":"byPage"})))
    service = SimpleNamespace(searchanalytics=lambda: SimpleNamespace(query=query))
    monkeypatch.setattr("app.gsc.client.build", Mock(return_value=service))
    result = GoogleGSCClient(oauth,"connection").query("sc-domain:exact.example", "2026-10-01", "page", "image", 25_000, 25_000)
    assert result["responseAggregationType"]=="byPage"
    assert query.call_args.kwargs == {"siteUrl":"sc-domain:exact.example", "body":{"startDate":"2026-10-01","endDate":"2026-10-01","dimensions":["page"],"type":"image","aggregationType":"byPage","dataState":"final","rowLimit":25000,"startRow":25000}}
    record=logging.LogRecord("uvicorn.access",logging.INFO,"",1,"%s %s %s %s %s",("local","GET","/api/integrations/gsc/oauth/callback?code=fixture-sensitive&state=hidden","1.1",400),None)
    RedactOAuthAccessLog().filter(record)
    assert 'fixture-sensitive' not in record.getMessage() and 'state=hidden' not in record.getMessage()


def test_disconnected_credentials_cannot_be_resurrected_by_inflight_request(runtime):
    from google.oauth2.credentials import Credentials
    runtime.oauth.configure(json.dumps(client_config()).encode())
    runtime.oauth.start()
    pending = runtime.oauth.pending
    pending.flow = SimpleNamespace(fetch_token=Mock(), credentials=SimpleNamespace(refresh_token="test-refresh", to_json=lambda:json.dumps({"refresh_token":"test-refresh"})))
    runtime.oauth.callback(pending.state,"test-code",None)
    runtime.oauth.disconnect(False)
    with pytest.raises(GSCError) as failure:
        runtime.oauth.save_credentials(pending.connection_id, Credentials(token="stale-inflight"))
    assert failure.value.code == "connection_changed"
    assert runtime.oauth.vault.get(f"tokens:{pending.connection_id}") is None
