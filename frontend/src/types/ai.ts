export interface AIProject {
  id: string;
  name: string;
  site_url: string;
  source_type: string;
  active: boolean;
  property_id: string | null;
  technical_id: string | null;
}
export interface AISource {
  id: string;
  name: string;
  status: string;
  date_start?: string | null;
  date_end?: string | null;
  last_collected_at?: string | null;
  limitations: string;
}
export interface AIContext {
  project: AIProject;
  sources: AISource[];
  keyword_sets: {
    id: string;
    name: string;
    start_date: string;
    timezone: string;
    status: string;
  }[];
  keyword_set_count: number;
  retrieved_at: string;
  limitations: string[];
}
export interface AIConversation {
  id: string;
  project_id: string;
  title: string;
  provider: "local_report" | "openai" | "chatgpt";
  model: string;
  saved: boolean;
  created_at: string;
  updated_at: string;
}
export interface AIEvidence {
  evidence_id: string;
  project_id: string;
  source_type: string;
  source_name: string;
  source_record_id: string | null;
  metric_scope: string;
  date_start: string | null;
  date_end: string | null;
  collected_at: string | null;
  retrieved_at: string;
  data_freshness: { age_days: number | null; status: string };
  completeness: string;
  source_reference: string | null;
  limitations: string[];
  value_summary?: Record<string, unknown>;
}
export interface AIFinding {
  title: string;
  interpretation: string;
  kind: "interpretation" | "hypothesis";
  confidence: string;
  evidence_ids: string[];
}
export interface AIRecommendation {
  id: string;
  project_id: string;
  message_id: string;
  title: string;
  proposed_action: string;
  priority: string;
  confidence: string;
  evidence_ids: string[];
  approval_status: string;
  user_notes: string;
  reviewed_at: string | null;
}
export interface AIAnalysis {
  summary: string;
  findings: AIFinding[];
  limitations: string[];
  next_step: string;
}
export interface AITool {
  id: string;
  tool_name: string;
  tool_version: string;
  status: string;
  duration_ms: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
}
export interface AIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: string;
  created_at: string;
  data: {
    provider: string;
    model?: string;
    window: { days: number; end_date: string | null };
    analysis?: AIAnalysis;
    error?: string;
    error_code?: string;
    tool_calls?: number;
    streaming_characters_received?: number;
    focus_url?: string | null;
  };
  evidence: AIEvidence[];
  metrics: {
    evidence_id: string;
    source_type: string;
    period: { start: string; end: string };
    metrics: Record<string, number>;
  }[];
  tools: AITool[];
  recommendations: AIRecommendation[];
}
export interface AIConversationDetail {
  conversation: AIConversation;
  messages: AIMessage[];
  total_messages: number;
  page: number;
  active_turn: string | null;
}
export interface AISettings {
  enabled: boolean;
  model: string;
  max_tool_calls: number;
  max_context_bytes: number;
  max_output_tokens: number;
  daily_limit_usd: number;
  warning_usd: number;
  input_usd_per_million: number | null;
  output_usd_per_million: number | null;
  pricing_reviewed_on: string | null;
}
export interface AIProviderState {
  settings: AISettings;
  provider: string;
  key_configured: boolean;
  secure_storage_available: boolean;
  model_validated: boolean;
  model_reference: string;
  pricing_reference: string;
  pricing_status: string;
  pricing_note: string;
  local_mode: string;
}
export interface AIUsageRecord {
  id: string;
  provider: string;
  model: string;
  status: string;
  input_tokens: number | null;
  output_tokens: number | null;
  reserved_usd: number;
  estimated_cost_usd: number | null;
  created_at: string;
  request_id: string | null;
}
export interface AIUsage {
  rows: AIUsageRecord[];
  total: number;
  daily_used_estimate_usd: number;
  daily_limit_usd: number;
  day_timezone: string;
  note: string;
}
export interface AIEstimate {
  model?: string;
  connection_id?: string;
  billing_source?: string;
  provider: string;
  estimated_cost_usd?: number | null;
  turn_upper_estimate_usd?: number;
  per_call_reserved_usd?: number;
  max_calls?: number;
  within_daily_limit?: boolean;
  daily_limit_usd?: number;
  daily_used_estimate_usd?: number;
  requires_external_consent: boolean;
  warning?: boolean;
}

export interface ChatGPTStatus {
  provider: "chatgpt";
  status: string;
  secure_storage_available: boolean;
  authorization_status: string;
  pending_authorization: boolean;
  account: { sub: string; name?: string; email?: string } | null;
  connection_id: string | null;
  granted_scopes: string[];
  plan_usage_authorized: boolean;
  access_expires_at: number | null;
  refresh_expires_at: number | null;
  models: { slug: string; display_name: string }[];
  selected_model: string | null;
  models_stale: boolean;
  model_listing_status?: "unavailable" | "not_loaded" | "ready" | "empty" | "failed";
  last_error: { code: string; detail: string; stage?: string; reason?: string } | null;
  eligibility: {
    status: string;
    repository_license_found: boolean;
    user_review_required: boolean;
    note: string;
  };
  live_verification: string;
  quota: { status: string; remaining: number | null; note: string };
  documentation: string[];
  full_preview_limitations_verified: boolean;
  fallback_to_api_key: false;
}
