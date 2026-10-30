export interface VisibilityProject {
  id: string;
  local_project_id: string;
  name: string;
  country: string;
  language: string;
  description: string;
  research_goal: string;
  status: string;
}
export interface VisibilityEntity {
  id: string;
  kind: "brand" | "competitor";
  name: string;
  config: {
    ambiguous: boolean;
    aliases: {
      name: string;
      ambiguous: boolean;
      kind?: string;
      context_terms?: string[];
      negative_terms?: string[];
    }[];
    domains: { domain: string; include_subdomains: boolean }[];
    social_profiles: string[];
    category: string;
    competitor_type: string;
    notes: string;
  };
}
export interface VisibilityPrompt {
  id: string;
  text: string;
  category: string;
  intent: string;
  cohort_type: string;
  priority: number;
  status: string;
  topic: string;
  language: string;
  country: string;
  location: string | null;
  source: string;
  research_keyword_ids: string[];
  research_cluster_id: string | null;
  tracking_keyword_id: string | null;
  target_url: string | null;
  notes: string;
  buyer_stage: string;
}
export interface VisibilityMention {
  id: string;
  entity_id: string;
  start: number;
  end: number;
  matched_text: string;
  alias: string;
  status: string;
  detected_status: string;
  reason: string;
}
export interface VisibilityCitation {
  id: string;
  raw_url: string;
  normalized_url: string;
  domain: string;
  source_type: string;
  ownership: string;
  attribution_status: string;
  entity_id: string | null;
  observation_id?: string;
  data: {
    annotation_id?: string | null;
    start: number | null;
    end: number | null;
    quote: string | null;
    source_verification: string;
    problems: string[];
    url_verified: boolean;
    content_verified: boolean;
  };
}
export interface VisibilityObservation {
  id: string;
  prompt_id: string;
  provider: string;
  model: string | null;
  collection_method: string;
  prompt_snapshot: string;
  response_text: string;
  observed_at: string | null;
  completeness: string;
  citation_capability: string;
  citation_metadata: string;
  supersedes_id: string | null;
  original: {
    grounding: string;
    country: string | null;
    language: string | null;
    location: string | null;
    citations?: unknown[];
    raw_annotations?: object;
    source_metadata?: object;
    notes?: string;
    prompt_context: {
      category: string;
      intent: string;
      topic: string;
      cohort_type: string;
      branded_prompt_detected?: boolean;
    };
  };
  mentions: VisibilityMention[];
  citations: VisibilityCitation[];
  missing_metadata: string[];
  corrections: string[];
  extraction: {
    id: string;
    revision: number;
    data: {
      warnings: string[];
      url_mentions: { url: string; is_citation: boolean }[];
      citation_complete: boolean;
    };
  };
}
export interface Rate {
  numerator: number;
  denominator: number;
  percent: number | null;
}
export interface VisibilityGroup {
  cohort: Record<string, string | null>;
  observation_count: number;
  unique_prompt_count: number;
  collection_start: string | null;
  collection_end: string | null;
  brand_mention_rate: Rate;
  brand_citation_rate: Rate;
  citation_eligible_observations: number;
  missing_citation_metadata: number;
  unknown_citation_capability: number;
  coverage_notes: string[];
  citation_domain_distribution: {
    domain: string;
    citation_occurrences: number;
    unique_cited_urls: number;
    observations_containing_domain: number;
  }[];
  entities: {
    entity_id: string;
    name: string;
    kind: string;
    mention_rate: Rate;
    citation_rate: Rate;
    citation_occurrences: number;
    unique_cited_domains: string[];
    overlapping_prompt_ids: string[];
    competitor_without_brand_observation_ids: string[];
  }[];
}
export interface VisibilityOverview {
  eligible_observations: number;
  stored_observations: number;
  unique_prompts_observed: number;
  prompt_coverage: Rate;
  groups: VisibilityGroup[];
  exclusion_counts: Record<string, number>;
  needs_review_mentions: number;
  opportunities: number;
  pending_review: number;
  limitations: string[];
}
export interface VisibilityEvidence {
  id: string;
  source_type: string;
  source_id: string;
  data: { source_reference: string | null; value: Record<string, unknown> };
  created_at: string;
}
export interface GEOOpportunity {
  id: string;
  opportunity_id: string;
  title: string;
  rule_id: string;
  category: string;
  priority: string;
  review_status: string;
  affected_topic: string;
  affected_url_ids: string[];
  affected_prompt_ids: string[];
  observation_ids: string[];
  observation_count: number;
  evidence_ids: string[];
  observed_facts: {
    predicate: string;
    evidence_ids: string[];
    explanation: string;
  }[];
  possible_explanations: string[];
  counterevidence: string[];
  missing_information: string[];
  recommended_action: string;
  action_type: string;
  verification_plan: string;
  expected_benefit_hypothesis: string;
  evidence_confidence: string;
  interpretation_confidence: string;
  action_confidence: string;
  priority_reason: string;
  evidence?: VisibilityEvidence[];
  human_review?: { notes: string; revised_action?: string };
  analyses: {
    id: string;
    message_id: string | null;
    data: Record<string, unknown>;
  }[];
}
export interface VisibilityDocument {
  id: string;
  kind: string;
  url: string;
  content: string;
  approved: boolean;
  data: {
    source_name: string;
    captured_at: string | null;
    verification: string;
    prompt_ids: string[];
    entity_id: string | null;
    business_fields: Record<string, string>;
    notes: string;
  };
}
export interface VisibilityReferences {
  research_keywords: { id: string; name: string }[];
  research_clusters: { id: string; name: string }[];
  tracking: { id: string; name: string }[];
}
export interface VisibilityJob {
  id: string;
  status: string;
  kind: string;
  data: {
    rows: unknown[];
    errors: { row: number; detail: string }[];
    input_rows: number;
    validated_rows: number;
    created?: number;
    duplicates?: number;
  };
}
export interface VisibilityRun {
  id: string;
  data: {
    summary: string;
    opportunity_ids: string[];
    included_observation_ids: string[];
    excluded_observations: unknown[];
    abstentions: { rule_id: string; reason: string }[];
    truncated: boolean;
    seo_availability: unknown;
  };
}
export interface VisibilityPage<T> {
  rows: T[];
  total: number;
  page: number;
}
