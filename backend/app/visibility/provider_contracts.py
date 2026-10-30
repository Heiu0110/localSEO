"""Visibility provider boundary, extended for explicit live observation envelopes."""

from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .live_schemas import LiveSettings


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    connected: bool
    supports_citations: bool | None
    supports_grounding: bool | None
    eligibility_verified: bool
    reason: str


class LiveVisibilityAdapter(Protocol):
    """Explicitly consented live collection; adapters preserve native response metadata.

    The envelope carries both a raw provider response and a normalized candidate,
    search actions/sources and usage; the manager persists via existing core.ingest.
    A parser failure carries a safe diagnostic, never a fabricated observation.
    """

    def capabilities(self) -> ProviderCapabilities: ...
    def observe(
        self,
        *,
        prompt_snapshot: str,
        consent_receipt_id: str,
        settings: "LiveSettings",
        context: dict,
        prompt_id: str,
        collection_request_id: str,
        credential_tag: str,
    ) -> dict[str, Any]: ...
