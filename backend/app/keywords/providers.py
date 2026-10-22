"""Extension boundary only. No automatic SERP collector is configured in v0.4."""

from typing import Protocol, TypedDict


class ProviderObservation(TypedDict):
    provider: str
    checked_at: str
    rank_status: str
    rank_value: int | None
    matched_url: str | None
    profile_snapshot: dict
    match_mode: str
    evidence: dict
    confidence: str
    cost_metadata: dict


class RankProvider(Protocol):
    def check(
        self, keyword: str, search_profile: dict, target: dict
    ) -> ProviderObservation: ...
