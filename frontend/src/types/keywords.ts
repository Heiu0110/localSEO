export interface KeywordGroup {
  id: string;
  keyword_set_id: string;
  name: string;
  color: string;
  sort_order: number;
}
export interface Profile {
  id: string;
  keyword_set_id: string;
  name: string;
  config: {
    search_engine: "Google";
    country: string;
    language: string;
    location_label: string;
    device: "desktop" | "mobile" | "tablet";
    search_depth: number;
    result_type: "organic_web";
  };
}
export interface Week {
  id: string;
  week_number: number;
  start_date: string;
  end_date: string;
}
export interface KeywordSet {
  id: string;
  site_id: string;
  property_id: string | null;
  name: string;
  description: string;
  start_date: string;
  timezone: string;
  status: string;
  settings: { site_url: string; min_impressions: number; low_ctr: number };
  profiles: Profile[];
  groups: KeywordGroup[];
  weeks: Week[];
}
export interface Observation {
  id: number;
  tracked_keyword_id: string;
  rank_status: "FOUND" | "NOT_FOUND" | "NOT_CHECKED";
  rank_value: number | null;
  checked_at: string | null;
  timestamp_precision: string;
  method: string;
  profile_snapshot: Profile["config"] & { name: string; keyword_text: string };
  target_url_snapshot: string;
  match_mode: string;
  series_key: string;
  notes: string;
  created_at: string;
  count?: number;
  week_number?: number;
}
export interface KeywordMetrics {
  date_start?: string;
  date_end?: string;
  status: string;
  clicks: number | null;
  impressions: number | null;
  ctr: number | null;
  average_position: number | null;
  fetched_at?: string;
  source_fetched_at?: string;
  source?: string | null;
  scope: string;
  top_page?: string | null;
  observed_pages?: { url: string; impressions: number; clicks: number }[];
  coverage_note?: string;
}
export interface Keyword {
  id: string;
  keyword_set_id: string;
  keyword_text: string;
  group_id: string | null;
  target_url: string;
  match_mode: "exact_url" | "domain";
  priority: string;
  search_intent: string;
  status: string;
  notes: string;
  current: Observation | null;
  previous: Observation | null;
  change: { state: string; value: number | null };
  metrics: KeywordMetrics;
  weeks: Record<string, Observation>;
  indicators: string[];
}
export interface KeywordPageResult {
  rows: Keyword[];
  total: number;
  page: number;
  page_size: number;
  date_start: string;
  date_end: string;
  scope: string;
}
export interface KeywordOverview {
  stats: Record<string, number>;
  distribution: { name: string; value: number }[];
  groups: {
    group_id: string;
    total: number;
    checked: number;
    top10: number;
    average_rank: number | null;
    comparable: number;
  }[];
  trends: {
    week: number;
    found: number;
    not_found: number;
    average_rank: number | null;
  }[];
}
export interface KeywordHistory {
  keyword: Keyword;
  rows: Observation[];
  total: number;
  representatives: Observation[];
  technical: {
    url_id: string;
    audit_id: string;
    project_id: string;
    status_code: number | null;
    indexability: string;
    audited_at: string;
  }[];
  imported_metrics: Record<string, string>[];
}
export interface KeywordJob {
  id: string;
  status: string;
  completed: number;
  total: number;
  error: string | null;
  updated_at: string;
}
export interface ImportPreview {
  id: string;
  filename: string;
  data: {
    headers: string[];
    mapping: Record<string, string | null>;
    samples: Record<string, string | number | boolean>[];
    total_rows: number;
    errors: { row: number; message: string }[];
    warnings: { row: number; message: string }[];
  };
}
export interface RankPayload {
  keyword_id: string;
  profile_id: string;
  week_number: number;
  value: string;
  timestamp_precision: "exact" | "week_only";
  checked_at?: string;
  notes?: string;
}
