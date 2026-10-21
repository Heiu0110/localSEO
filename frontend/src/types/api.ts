// Mirrors backend/app/models.py. CTR and shares are percentages (0–100).
export type SourceType = 'mock' | 'gsc' | 'fixture';
export interface Site { id: string; domain: string; source_type: SourceType }
export type SearchType = 'web' | 'image' | 'video' | 'news';
export type Days = 7 | 28 | 90;
export type MetricKey = 'clicks' | 'impressions' | 'ctr' | 'position';
export interface Metrics { clicks: number; impressions: number; ctr: number; position: number }
export interface Period { start: string; end: string; days: number }
export interface Change { delta: number | null; percent: number | null }
export interface Overview {
  site_id: string; period: Period; previous_period: Period;
  current: Metrics; previous: Metrics; changes: Record<MetricKey, Change>;
  source: SourceType; last_updated: string; dataset_start: string; dataset_end: string;
  has_data: boolean; comparison_available: boolean; last_synced_at: string | null; warnings: string[];
  coverage: { current: Coverage; previous: Coverage; comparison_available: boolean } | null;
}
export interface Coverage { expected_days: number; synchronized_days: number; available_days: number; empty_days: number; completeness: string; aggregation_type: string }
export interface PerformancePoint { date: string; metrics: Metrics | null; previous_date: string; previous_metrics: Metrics | null }
export interface Performance { site_id: string; period: Period; points: PerformancePoint[] }
export interface DimensionRow { id: string; label: string; metrics: Metrics; previous: Metrics; click_change_pct: number | null; impression_change_pct?: number | null; share?: number | null; current_available?: boolean; previous_available?: boolean; code?: string | null }
export interface DimensionReport { site_id: string; period: Period; coverage: 'complete' | 'partial' | 'unknown'; rows: DimensionRow[]; total_rows: number | null; warning?: string | null; page: number; page_size: number; completeness: 'complete' | 'api_response' | 'api_limited' | 'unknown' }
export interface CountryRow { code: string; name: string; metrics: Metrics; share: number; current_available?: boolean }
export interface CountryReport { site_id: string; period: Period; rows: CountryRow[]; coverage: 'complete' | 'partial'; share_basis: 'site' | 'returned_rows' }
export interface DataSource { id: string; name: string; status: 'Mock Mode' | 'Not Connected' | 'Planned' | 'Not Configured' | 'Connected' | 'Syncing' | 'Up to Date' | 'Stale' | 'Reauthorization Required' | 'Error' | 'Fixture'; detail: string }
export interface PageDetail {
  id: string; url: string; period: Period; current: Metrics; previous: Metrics;
  performance: PerformancePoint[]; queries: DimensionRow[];
  source: SourceType; query_relationships_available: boolean; has_data: boolean; comparison_available: boolean;
}
