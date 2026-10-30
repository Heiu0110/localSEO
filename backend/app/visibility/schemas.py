"""Strict input/output contracts; collection context is never inferred from the project."""

import json
from datetime import date, datetime, timezone, timedelta
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.ai.common import redact


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @model_validator(mode="after")
    def reject_secret_inputs(self):
        no_secrets(self.model_dump(mode="json"))
        return self


def no_secrets(value):
    if redact(value) != value:
        raise ValueError(
            "Không nhập khóa, token hoặc Authorization vào dữ liệu quan sát."
        )
    return value


class ProjectInput(Input):
    local_project_id: str = Field(min_length=1, max_length=150)
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(default="VN", pattern=r"^[A-Z]{2}$")
    language: str = Field(default="vi", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    description: str = Field(default="", max_length=2000)
    research_goal: str = Field(default="", max_length=2000)


class ProjectPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    research_goal: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None


class Alias(Input):
    name: str = Field(min_length=1, max_length=160)
    ambiguous: bool = False
    kind: Literal["alias", "former_name", "product"] = "alias"
    context_terms: list[str] = Field(default_factory=list, max_length=12)
    negative_terms: list[str] = Field(default_factory=list, max_length=12)


class OwnedDomain(Input):
    domain: str = Field(min_length=1, max_length=255)
    include_subdomains: bool = False


class EntityInput(Input):
    kind: Literal["brand", "competitor"] = "brand"
    name: str = Field(min_length=1, max_length=160)
    ambiguous: bool = False
    aliases: list[Alias] = Field(default_factory=list, max_length=30)
    domains: list[OwnedDomain] = Field(default_factory=list, max_length=20)
    social_profiles: list[str] = Field(default_factory=list, max_length=10)
    category: str = Field(default="", max_length=160)
    competitor_type: str = Field(default="direct", max_length=100)
    notes: str = Field(default="", max_length=2000)


Intent = Literal[
    "unknown",
    "informational",
    "commercial",
    "transactional",
    "navigational",
    "local",
    "mixed",
]
CohortType = Literal["neutral", "commercial_discovery", "brand_specific"]


class PromptInput(Input):
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="vi", max_length=20)
    country: str = Field(default="VN", max_length=20)
    location: str | None = Field(default=None, max_length=160)
    topic: str = Field(default="", max_length=200)
    category: str = Field(default="Brand Discovery", max_length=100)
    intent: Intent = "unknown"
    cohort_type: CohortType = "neutral"
    buyer_stage: str = Field(default="unknown", max_length=100)
    priority: int = Field(default=1, ge=0, le=3)
    status: Literal["draft", "active", "archived"] = "active"
    source: Literal[
        "manual", "import", "research", "tracking", "ai_generated_candidate"
    ] = "manual"
    research_keyword_ids: list[str] = Field(default_factory=list, max_length=20)
    research_cluster_id: str | None = Field(default=None, max_length=100)
    tracking_keyword_id: str | None = Field(default=None, max_length=100)
    target_url: str | None = Field(default=None, max_length=2048)
    notes: str = Field(default="", max_length=2000)


class CitationInput(Input):
    url: str = Field(min_length=1, max_length=4096)
    source_type: Literal[
        "provider_annotation",
        "grounding_metadata",
        "user_supplied",
        "third_party_report",
    ]
    annotation_id: str | None = Field(default=None, max_length=200)
    reported_domain: str | None = Field(default=None, max_length=255)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    offset_unit: Literal["unicode_codepoint", "utf16", "unknown"] = "unknown"
    quote: str | None = Field(default=None, max_length=2000)
    source_verification: Literal[
        "provider_reported", "user_declared", "third_party_reported"
    ] = "user_declared"


class ObservationInput(Input):
    prompt_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=160)
    collection_method: Literal[
        "MANUAL_ENTRY", "IMPORTED_RESPONSE", "PROVIDER_API", "THIRD_PARTY_REPORT"
    ] = "MANUAL_ENTRY"
    prompt_snapshot: str | None = Field(default=None, max_length=2000)
    response_text: str = Field(min_length=1, max_length=30000)
    grounding: Literal["enabled", "disabled", "unknown"] = "unknown"
    country: str | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=160)
    observed_at: datetime | None = None
    citation_capability: Literal["capable", "not_supported", "unknown"] = "unknown"
    citation_metadata: Literal["complete", "partial", "missing"] = "missing"
    completeness: Literal["complete", "partial", "invalid"] = "complete"
    citations: list[CitationInput] = Field(default_factory=list, max_length=100)
    raw_annotations: dict[str, Any] = Field(default_factory=dict)
    artifact_reference: str | None = Field(default=None, max_length=300)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def provenance(self):
        no_secrets(self.model_dump(mode="json"))
        if self.observed_at:
            if self.observed_at.tzinfo is None or self.observed_at > datetime.now(
                timezone.utc
            ) + timedelta(days=1):
                raise ValueError(
                    "Thời điểm quan sát cần timezone và không ở tương lai."
                )
        if (
            len(json.dumps([self.raw_annotations, self.source_metadata]).encode())
            > 30000
        ):
            raise ValueError("Metadata quá lớn.")
        if (
            self.citation_metadata == "complete"
            and self.citation_capability != "capable"
        ):
            raise ValueError(
                "Chỉ nguồn hỗ trợ citation mới có metadata citation complete."
            )
        return self


class Correction(Input):
    observation: ObservationInput
    reason: str = Field(min_length=5, max_length=2000)


class Cohort(Input):
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=160)
    start: date | None = None
    end: date | None = None
    category: str | None = Field(default=None, max_length=100)
    intent: Intent | None = None
    cohort_type: (
        Literal["neutral", "commercial_discovery", "brand_specific", "all"] | None
    ) = "neutral"
    collection_method: (
        Literal[
            "MANUAL_ENTRY", "IMPORTED_RESPONSE", "PROVIDER_API", "THIRD_PARTY_REPORT"
        ]
        | None
    ) = None
    brand_id: str | None = Field(default=None, max_length=100)
    competitor_id: str | None = Field(default=None, max_length=100)
    require_complete: bool = True
    require_human_review: bool = False

    @model_validator(mode="after")
    def dates(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("Ngày bắt đầu sau ngày kết thúc.")
        return self


class MentionReview(Input):
    status: Literal[
        "CONFIRMED_MATCH", "POSSIBLE_MATCH", "REJECTED_MATCH", "NEEDS_REVIEW"
    ]
    reason: str = Field(min_length=5, max_length=2000)


class DocumentInput(Input):
    kind: Literal["page_content", "business_identity", "topic_requirement"]
    url: str = Field(default="", max_length=2048)
    content: str = Field(min_length=1, max_length=30000)
    approved: bool = False
    source_name: str = Field(min_length=1, max_length=200)
    captured_at: datetime | None = None
    verification: Literal["unverified", "user_verified"] = "unverified"
    entity_id: str | None = Field(default=None, max_length=100)
    prompt_ids: list[str] = Field(default_factory=list, max_length=30)
    business_fields: dict[
        Literal["company_name", "address", "phone", "website"], str
    ] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def safe(self):
        no_secrets(self.model_dump(mode="json"))
        if self.business_fields and any(
            not value or value not in self.content
            for value in self.business_fields.values()
        ):
            raise ValueError(
                "Thông tin business phải có nguyên văn trong nội dung nguồn."
            )
        return self


class CoverageInput(Input):
    requirement_id: str = Field(max_length=100)
    page_id: str = Field(max_length=100)
    decision: Literal["missing", "covered", "uncertain"]
    reason: str = Field(min_length=10, max_length=2000)


class OpportunityReview(Input):
    status: Literal[
        "proposed",
        "under_review",
        "approved",
        "rejected",
        "needs_more_evidence",
        "investigation",
    ]
    notes: str = Field(default="", max_length=2000)
    revised_action: str | None = Field(default=None, max_length=2000)
    ratings: dict[
        Literal[
            "observation",
            "citation",
            "entity",
            "business_relevance",
            "interpretation",
            "feasibility",
            "completeness",
            "usefulness",
        ],
        Literal["correct", "partially_correct", "incorrect", "insufficient_evidence"],
    ] = Field(default_factory=dict)


class Confirm(Input):
    confirm: bool


class ImportCommit(Confirm):
    job_id: str = Field(max_length=100)


class ImportPreview(Input):
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class SourcePrompts(Input):
    source: Literal["research_keywords", "research_clusters", "tracking"]
    ids: list[str] = Field(min_length=1, max_length=100)


class SourceReview(Input):
    approved: bool
    reason: str = Field(min_length=5, max_length=2000)


class GEOAnalysisScope(Input):
    visibility_project_id: str = Field(min_length=1, max_length=100)
    opportunity_id: str = Field(min_length=1, max_length=100)


Action = Literal[
    "Investigate",
    "Improve Existing Content",
    "Clarify Business Information",
    "Improve Page Structure",
    "Improve Internal Linking",
    "Review Technical SEO",
    "Expand Topic Coverage",
    "Differentiate Content",
    "Create Content Brief",
    "Monitor After Changes",
    "No Action",
]
Confidence = Literal["Verified", "Strong", "Limited", "Ambiguous", "Insufficient"]


class GEOClaim(Input):
    predicate: Literal[
        "brand_mentioned",
        "brand_not_observed",
        "competitor_mentioned",
        "owned_citation",
        "competitor_citation",
        "technical_issue",
        "mapping_missing",
        "identity_conflict",
        "coverage_review",
        "hypothesis",
    ]
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    explanation: str = Field(min_length=1, max_length=1500)


class GEOOpportunityOutput(Input):
    opportunity_id: str
    title: str = Field(max_length=200)
    category: str = Field(max_length=100)
    affected_topic: str = Field(max_length=200)
    affected_prompt_ids: list[str] = Field(max_length=20)
    affected_url_ids: list[str] = Field(max_length=20)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    observed_facts: list[GEOClaim] = Field(max_length=10)
    possible_explanations: list[str] = Field(max_length=10)
    counterevidence: list[str] = Field(max_length=10)
    missing_information: list[str] = Field(max_length=10)
    recommended_action: str = Field(max_length=2000)
    action_type: Action
    expected_benefit_hypothesis: str = Field(max_length=1000)
    verification_plan: str = Field(min_length=1, max_length=1500)
    evidence_confidence: Confidence
    interpretation_confidence: Confidence
    action_confidence: Confidence
    priority: Literal["P0", "P1", "P2", "Investigation"]
    review_status: Literal["proposed", "needs_human_verification"] = (
        "needs_human_verification"
    )


class GEOOpportunityAnalysis(Input):
    project_id: str
    observation_scope: str = Field(max_length=1500)
    summary: str = Field(max_length=2000)
    findings: list[GEOClaim] = Field(max_length=10)
    opportunities: list[GEOOpportunityOutput] = Field(max_length=8)
    limitations: list[str] = Field(max_length=12)
    next_investigation: str = Field(max_length=1000)


class GEOAnalysisContext(Input):
    local_project_id: str
    visibility_project_id: str
    opportunity_id: str
    objective: str
    cohort: dict[str, Any]
    candidate: dict[str, Any]
    evidence: list[dict[str, Any]] = Field(max_length=10)
    available_evidence_ids: list[str] = Field(max_length=10)
    limitations: list[str]
