"""Versioned, deterministic offline fixture. No website or Google requests are made."""

from datetime import date, datetime, timedelta, timezone
from math import sin
from random import Random

from app.models import Site
from app.providers.base import Observation


class MockProvider:
    end_date = date(2026, 10, 20)
    start_date = end_date - timedelta(days=199)
    last_updated = datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc)
    sites = (
        Site(id="xuong-may", domain="xuongmaybalogiare.com"),
        Site(id="cong-ty", domain="congtymaybalotuixach.com"),
    )
    countries = {"VN": "Vietnam", "US": "United States", "SG": "Singapore", "TH": "Thailand", "MY": "Malaysia"}

    def __init__(self) -> None:
        self._facts: dict[str, tuple[Observation, ...]] = {}
        self._pages: dict[str, dict[str, str]] = {}
        self._queries: dict[str, dict[str, str]] = {}
        slugs = ["", "may-balo-theo-yeu-cau", "xuong-may-balo", "balo-quang-cao", "balo-qua-tang", "tui-xach", "tui-du-lich", "cap-laptop", "tui-my-pham", "balo-hoc-sinh", "bao-gia", "lien-he"]
        queries = ["may balo theo yêu cầu", "xưởng may balo", "sản xuất balo quảng cáo", "may balo quà tặng", "may túi xách theo yêu cầu", "xưởng may túi du lịch", "sản xuất cặp laptop", "may túi mỹ phẩm", "balo học sinh giá sỉ", "báo giá may balo", "balo in logo công ty", "xưởng may balo giá rẻ", "túi vải canvas theo yêu cầu", "may balo số lượng lớn", "công ty may túi xách", "xưởng sản xuất balo tphcm"]
        for site_index, site in enumerate(self.sites):
            rng = Random(3107 + site_index)
            self._pages[site.id] = {f"p{i+1}": f"https://{site.domain}/{slug}" for i, slug in enumerate(slugs)}
            names = queries if site_index == 0 else queries[4:] + queries[:4]
            self._queries[site.id] = {f"q{i+1}": name for i, name in enumerate(names)}
            facts = []
            for d in range(200):
                day = self.start_date + timedelta(days=d)
                # Distinct growth, weekly seasonality, a dip, and recovery for each site.
                trend = 0.76 + d * (0.0031 if site_index == 0 else 0.0016)
                weekly = [1.04, 1.09, 1.08, 1.03, 0.98, 0.76, 0.70][day.weekday()]
                dip = 0.65 if 164 <= d <= 169 else 1.0
                growth = 1.13 if d >= 181 and site_index == 0 else 1.0
                for page_index, page_id in enumerate(self._pages[site.id]):
                    for offset in (0, 5):
                        query_id = f"q{(page_index + offset) % 16 + 1}"
                        for country, weight in zip(self.countries, (0.86, 0.055, 0.04, 0.025, 0.02)):
                            volume = (1250 - page_index * 67) * (1 if site_index == 0 else 0.72)
                            impressions = max(1, round(volume * weight * trend * weekly * dip * growth * rng.uniform(0.87, 1.13)))
                            position = round(max(1.1, 5.5 + page_index * 0.7 + site_index * 2 - d * 0.009 + 0.8 * sin(d / 11) + rng.uniform(-0.7, 0.7)), 3)
                            ctr = (0.065 - page_index * 0.0022) * (1.05 if country == "VN" else 0.65)
                            clicks = min(impressions, round(impressions * ctr * rng.uniform(0.8, 1.2)))
                            facts.append(Observation(day, page_id, query_id, country, clicks, impressions, position))
            self._facts[site.id] = tuple(facts)

    def observations(self, site_id: str) -> tuple[Observation, ...]:
        return self._facts[site_id]

    def pages(self, site_id: str) -> dict[str, str]:
        return self._pages[site_id]

    def queries(self, site_id: str) -> dict[str, str]:
        return self._queries[site_id]
