"""Future live collection boundary; Core deliberately has no implementation or credentials."""

from dataclasses import dataclass
from typing import Protocol
from .schemas import ObservationInput


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    connected: bool
    supports_citations: bool | None
    supports_grounding: bool | None
    eligibility_verified: bool
    reason: str


class LiveVisibilityAdapter(Protocol):
    """Implement only after provider terms, tool eligibility, cost and consent are verified.

    Inference credentials alone do not establish web search/grounding capability.
    Implementations must preserve original answer/annotations and actual collection context.
    No adapter is constructed or invoked in v0.8 Core.
    """

    def capabilities(self) -> ProviderCapabilities: ...
    def observe(
        self, *, prompt_snapshot: str, consent_receipt_id: str
    ) -> ObservationInput: ...
