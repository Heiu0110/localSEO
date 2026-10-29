export interface ResearchProject {
  id: string;
  local_project_id: string | null;
  name: string;
  country: string;
  language: string;
  description: string;
  business_context: string;
  research_goal: string;
  status: string;
  settings: Record<string, number>;
  keyword_count: number;
  snapshot_count: number;
}
export interface ResearchMetric {
  metric_type: string;
  value: number;
  unit: string;
  scope: string;
  reporting_start: string | null;
  reporting_end: string | null;
  metadata: Record<string, string>;
}
export interface ResearchSource {
  id: string;
  provider: string;
  method: string;
  reference: string;
  collected_at: string;
  original_text: string;
  metrics: ResearchMetric[];
}
export interface ResearchKeyword {
  id: string;
  project_id: string;
  keyword_text: string;
  country: string;
  language: string;
  group_name: string;
  intent: string;
  target_url: string;
  mapping_status: string;
  brand_label: string;
  notes: string;
  status: string;
  cluster_id: string | null;
  sources: ResearchSource[];
  intent_suggestion?: { intent: string; reason: string };
  target_suggestions?: {
    suggestions: { url: string; kind: string; reason: string }[];
  };
  reviews?: unknown[];
}
export interface ResearchCluster {
  id: string;
  name: string;
  primary_keyword_id: string | null;
  intent: string;
  page_type: string;
  target_url: string;
  mapping_status: string;
  notes: string;
  status: string;
  keyword_count: number;
  keywords: ResearchKeyword[];
  evidence: unknown;
}
export interface SerpSnapshot {
  id: string;
  keyword_id: string;
  keyword_text: string;
  provider: string;
  country: string;
  language: string;
  location: string;
  device: string;
  requested_depth: number;
  returned_depth: number;
  collected_at: string;
  completeness: string;
  results?: {
    id: string;
    organic_position: number | null;
    provider_position: string;
    result_type: string;
    url: string;
    title: string;
    domain: string;
    snippet: string;
    features: string[];
  }[];
  selected_website_presence?: unknown;
  age_days?: number;
  freshness?: string;
  limitations?: string[];
}
export interface ResearchOpportunity {
  id: string;
  keyword_text: string;
  kind: string;
  priority: string;
  confidence: string;
  status: string;
  notes: string;
  proposed_action: string;
  evidence: unknown;
  updated_at: string;
}
export interface ResearchPageResult<T> {
  rows: T[];
  total: number;
  page: number;
  page_size?: number;
}
export interface ResearchJob {
  id: string;
  kind: string;
  status: string;
  data: {
    rows: Record<string, unknown>[];
    duplicates?: number;
    limitations?: string[];
    set_id?: string;
  };
  file_mapping?: unknown;
}
export interface ClusterProposal {
  name: string;
  keyword_ids: string[];
  primary_keyword_id: string;
  intent: string;
  method: string;
  status: string;
  confidence: string;
  factors: unknown[];
  limitations: string;
}
