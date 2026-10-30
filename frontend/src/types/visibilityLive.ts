export interface LiveSettings {
  enabled: boolean;
  model: string | null;
  max_output_tokens: number;
  max_tool_calls: number;
  search_context_size: "low" | "medium" | "high";
  daily_limit_usd: number;
  input_usd_per_million: number | null;
  output_usd_per_million: number | null;
  tool_usd_per_thousand_calls: number | null;
  search_content_billing:
    | "reported_input"
    | "additional_estimate"
    | "unverified";
  search_content_tokens_per_call: number;
  pricing_source: string;
  pricing_reviewed_on: string | null;
  pricing_notes: string;
}
export interface LiveProviderState {
  provider: string;
  settings: LiveSettings;
  key_configured: boolean;
  secure_storage_available: boolean;
  capability_status: string;
  web_search_capability?: string;
  model_accessible: boolean;
  web_search_supported: boolean;
  last_validation: string | null;
  pricing_status: string;
  daily_used_estimate_usd: number;
  effective_daily_limit_usd: number;
  live_verification: string;
  limitations: string[];
}
export interface CollectionUsage {
  status: string;
  input_tokens: number | null;
  output_tokens: number | null;
  reserved_usd: number;
  estimated_cost_usd: number | null;
  data: Record<string, unknown>;
}
export interface CollectionRequest {
  id: string;
  project_id: string;
  prompt_id: string;
  status: string;
  binding_hash: string;
  observation_id: string | null;
  usage_id: string | null;
  dispatched_at: string | null;
  created_at: string;
  snapshot: {
    binding: {
      prompt_snapshot: string;
      provider: string;
      settings: LiveSettings;
      context: {
        country: string | null;
        language: string | null;
        city: string | null;
        region: string | null;
      };
      authorized_max_usd: number;
    };
    estimate: {
      known_component_estimate_usd: number;
      total_estimate_usd: number | null;
      model_estimate_usd: number;
      tool_estimate_usd: number;
      estimated_input_tokens: number;
      estimated_search_calls: number;
      unknown_cost_components: string[];
      limitations: string[];
    };
    expires_at: string;
    capability_status: string;
  };
  result: {
    search_execution?: string;
    citation_count?: number;
    source_count?: number;
    actual_model?: string;
    response_id?: string;
    error_code?: string;
    detail?: string;
    problems?: string[];
    notes?: string[];
    provider_response?: unknown;
    costs?: Record<string, unknown>;
  };
  usage: CollectionUsage | null;
  consent_id: string | null;
}
export interface SearchSource {
  id: string;
  normalized_url: string;
  data: {
    type: "SEARCH_SOURCE";
    call_id: string;
    source_content_verified: false;
  };
}
export interface LiveCitationMetadata {
  annotation_id: string;
  title?: string;
  normalized_url?: string;
  span_mapping?: { status: string; highlight_verified: false };
  original_annotation?: unknown;
  response_item_id?: string;
}
export interface LiveObservationMetadata {
  collection_request_id?: string;
  provider_response_id?: string;
  search_execution?: string;
  answer_citations?: LiveCitationMetadata[];
  tool_configuration?: unknown;
  requested_context?: unknown;
  applied_location?: unknown;
  normalization_notes?: string[];
  measurement_profile?: string;
}
export const activeCollection = (status: string) =>
  ["QUEUED", "RUNNING"].includes(status);
export const collectionLabels: Record<string, string> = {
  PREFLIGHT_READY: "Chờ xác nhận",
  QUEUED: "Đang xếp hàng",
  RUNNING: "Đang kiểm tra AI Search",
  COMPLETED: "Đã hoàn tất",
  PARTIAL: "Kết quả chưa đầy đủ",
  FAILED: "Không hoàn tất",
  UNKNOWN_REMOTE_OUTCOME: "Chưa rõ kết quả từ xa / có thể đã tính phí",
  INTERRUPTED: "Đã gián đoạn trước khi gửi",
  CANCELLED_BEFORE_SUBMISSION: "Đã hủy trước khi gửi",
  SEARCH_COMPLETED: "Search đã hoàn tất",
  SEARCH_EXECUTED: "Search đã chạy nhưng chưa hoàn tất",
  SEARCH_FAILED: "Search không hoàn tất",
  NO_SEARCH_EXECUTED: "Không thực hiện search",
  SEARCH_EXECUTION_UNKNOWN: "Chưa xác định search execution",
};
