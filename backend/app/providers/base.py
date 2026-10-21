from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.models import Site


@dataclass(frozen=True, slots=True)
class Observation:
    day: date
    page_id: str
    query_id: str
    country: str
    clicks: int
    impressions: int
    position: float


class DataProvider(Protocol):
    """Complete daily fact data; a future GSC adapter must state coverage explicitly.

    Never combine incompatible GSC aggregation levels as if they were complete facts.
    """

    sites: tuple[Site, ...]
    start_date: date
    end_date: date
    last_updated: datetime
    countries: dict[str, str]

    def observations(self, site_id: str) -> tuple[Observation, ...]: ...
    def pages(self, site_id: str) -> dict[str, str]: ...
    def queries(self, site_id: str) -> dict[str, str]: ...
