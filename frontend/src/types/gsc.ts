import type { SearchType, SourceType } from './api';

export interface IntegrationStatus {
  status: string; configured: boolean; secure_storage_available: boolean; connection_id: string | null;
  display_name: string | null; message: string | null; scope: string; latest_final_date: string; history_start: string; pending_authorization: boolean;
}
export interface GSCProperty {
  id: string; connection_id: string; site_url: string; display_name: string; property_type: string;
  permission_level: string; source_type: SourceType; is_active: boolean; added_at: string;
  last_synced_at: string | null; local_start: string | null; local_end: string | null; sync_status: string;
}
export interface SyncJob {
  id: string; property_id: string; search_type: string; sync_mode: string; status: string;
  requested_date_start: string; requested_date_end: string; completed_days: number; total_days: number;
  rows_fetched: number; current_task: string; retry_count: number; cancel_requested: boolean;
  started_at: string; updated_at: string; finished_at: string | null; error_code: string | null; error_message: string | null;
}
export interface AnalyticsFilters { property: string; start: string; end: string; type: SearchType }
export type AnalyticsTab = 'overview' | 'pages' | 'queries' | 'countries' | 'devices';
