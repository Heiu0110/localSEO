from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import Observation
from app.providers.mock_provider import MockProvider
from app.services.dashboard_service import aggregate, change, get_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


def test_weighted_position_and_ctr_not_mean_of_daily_rates():
    rows = [Observation(date(2026, 1, 1), "p1", "q1", "VN", 1, 10, 2),
            Observation(date(2026, 1, 2), "p1", "q1", "VN", 9, 90, 8)]
    result = aggregate(rows)
    assert result.clicks == 10
    assert result.impressions == 100
    assert result.ctr == 10
    assert result.position == pytest.approx(7.4)  # not (2 + 8) / 2
    unequal_ctr = aggregate([rows[0], Observation(date(2026, 1, 2), "p1", "q1", "VN", 18, 90, 8)])
    assert unequal_ctr.ctr == 19  # not (10% + 20%) / 2


def test_empty_aggregation_and_zero_baseline():
    assert aggregate([]).model_dump() == {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
    assert change(5, 0).percent is None
    assert change(5, 10).percent == -50
    assert change(2, 8).delta == -6


@pytest.mark.parametrize("site", ["xuong-may", "cong-ty"])
@pytest.mark.parametrize("days", [7, 28, 90])
def test_consistency_across_all_complete_dimensions(client, site, days):
    params = {"site_id": site, "days": days}
    overview = client.get("/api/dashboard/overview", params=params)
    assert overview.status_code == 200, overview.text
    o = overview.json()
    series = client.get("/api/dashboard/performance", params=params).json()["points"]
    pages = client.get("/api/dashboard/pages", params=params).json()
    queries = client.get("/api/dashboard/queries", params=params).json()
    countries = client.get("/api/dashboard/countries", params=params).json()["rows"]
    assert len(series) == days
    assert len(pages["rows"]) >= 10
    assert len(queries["rows"]) >= 10
    assert pages["coverage"] == queries["coverage"] == "complete"
    assert len(countries) == 5
    for name in ("clicks", "impressions"):
        total = o["current"][name]
        assert total == sum(p["metrics"][name] for p in series)
        assert total == sum(r["metrics"][name] for r in pages["rows"])
        assert total == sum(r["metrics"][name] for r in queries["rows"])
        assert total == sum(r["metrics"][name] for r in countries)
        assert o["previous"][name] == sum(p["previous_metrics"][name] for p in series)
        assert o["previous"][name] == sum(p["previous"][name] for p in pages["rows"])
    assert sum(r["share"] for r in countries) == pytest.approx(100)
    assert o["current"]["ctr"] == pytest.approx(o["current"]["clicks"] / o["current"]["impressions"] * 100)
    assert o["current"]["position"] == pytest.approx(sum(p["metrics"]["position"] * p["metrics"]["impressions"] for p in series) / o["current"]["impressions"])
    assert date.fromisoformat(o["period"]["start"]) - date.fromisoformat(o["previous_period"]["end"]) == timedelta(days=1)
    assert (date.fromisoformat(o["period"]["end"]) - date.fromisoformat(o["period"]["start"])).days == days - 1
    assert series[0]["date"] == o["period"]["start"]
    assert series[-1]["date"] == o["period"]["end"]
    assert series[0]["previous_date"] == o["previous_period"]["start"]
    assert series[-1]["previous_date"] == o["previous_period"]["end"]
    assert o["changes"]["clicks"]["percent"] == pytest.approx((o["current"]["clicks"] - o["previous"]["clicks"]) / o["previous"]["clicks"] * 100)
    assert o["source"] == "mock"


@pytest.mark.parametrize("site", ["xuong-may", "cong-ty"])
def test_page_detail_is_partition_of_site_and_queries(client, site):
    params = {"site_id": site, "days": 28}
    pages = client.get("/api/dashboard/pages", params=params).json()["rows"]
    for page in pages:
        response = client.get(f'/api/dashboard/pages/{page["id"]}', params=params)
        assert response.status_code == 200
        detail = response.json()
        assert detail["current"] == page["metrics"]
        assert detail["previous"] == page["previous"]
        assert len(detail["performance"]) == 28
        assert sum(row["metrics"]["clicks"] for row in detail["queries"]) == page["metrics"]["clicks"]
        assert sum(row["metrics"]["impressions"] for row in detail["queries"]) == page["metrics"]["impressions"]
        assert sum(point["metrics"]["clicks"] for point in detail["performance"]) == page["metrics"]["clicks"]


def test_fixture_is_repeatable_and_has_200_days():
    first, second = get_service().provider, MockProvider()
    for site in first.sites:
        assert first.observations(site.id) == second.observations(site.id)
        assert len({r.day for r in first.observations(site.id)}) == 200
        assert min(r.day for r in first.observations(site.id)) == first.start_date
        assert max(r.day for r in first.observations(site.id)) == first.end_date
        assert all(0 <= r.clicks <= r.impressions for r in first.observations(site.id))
    assert aggregate(first.observations("xuong-may")) != aggregate(first.observations("cong-ty"))


@pytest.mark.parametrize("endpoint", ["overview", "performance", "pages", "queries", "countries", "pages/p1"])
def test_unknown_site_returns_404(client, endpoint):
    response = client.get(f"/api/dashboard/{endpoint}", params={"site_id": "unknown"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Site not found"


@pytest.mark.parametrize("days", [0, 1, 8, 89, 91, -7, "invalid", "7.5"])
def test_only_supported_date_ranges(client, days):
    assert client.get("/api/dashboard/overview", params={"site_id": "xuong-may", "days": days}).status_code == 422


def test_health_sites_schema_sources_and_validation(client):
    assert client.get("/api/health").json() == {"status": "ok", "provider": "hybrid", "version": "0.7.0"}
    assert [site["domain"] for site in client.get("/api/sites").json()] == ["xuongmaybalogiare.com", "congtymaybalotuixach.com"]
    assert client.get("/api/dashboard/pages/missing", params={"site_id": "xuong-may"}).status_code == 404
    assert client.get("/api/dashboard/overview").status_code == 422
    assert client.get("/api/dashboard/overview", params={"site_id": ""}).status_code == 422
    assert len(client.get("/api/dashboard/sources").json()) == 5
    assert client.get("/openapi.json").json()["components"]["schemas"]["Overview"]


def test_cors_is_limited_to_local_frontend(client):
    allowed = client.options("/api/sites", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    denied = client.options("/api/sites", headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_api_docs_assets_are_local(client):
    docs = client.get('/docs')
    assert docs.status_code == 200
    assert '/docs-assets/swagger-ui-bundle.js' in docs.text
    assert 'cdn.jsdelivr.net' not in docs.text
    assert '"validatorUrl": null' in docs.text
    for asset in ['swagger-ui-bundle.js', 'swagger-ui.css', 'favicon-32x32.png']:
        assert client.get('/docs-assets/' + asset).status_code == 200
