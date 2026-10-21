// Mirrors backend/app/models.py. CTR and shares are percentages (0–100).
export interface Site { id: string; domain: string }
export type Days = 7 | 28 | 90;
export type MetricKey = 'clicks' | 'impressions' | 'ctr' | 'position';
export interface Metrics { clicks: number; impressions: number; ctr: number; position: number }
export interface Period { start: string; end: string; days: number }
export interface Change { delta: number; percent: number | null }
export interface Overview {
  site_id: string; period: Period; previous_period: Period;
  current: Metrics; previous: Metrics; changes: Record<MetricKey, Change>;
  source: 'mock'; last_updated: string; dataset_start: string; dataset_end: string;
}
export interface PerformancePoint { date: string; metrics: Metrics; previous_date: string; previous_metrics: Metrics }
export interface Performance { site_id: string; period: Period; points: PerformancePoint[] }
export interface DimensionRow { id: string; label: string; metrics: Metrics; previous: Metrics; click_change_pct: number | null }
export interface DimensionReport { site_id: string; period: Period; coverage: 'complete'; rows: DimensionRow[] }
export interface CountryRow { code: string; name: string; metrics: Metrics; share: number }
export interface CountryReport { site_id: string; period: Period; rows: CountryRow[] }
export interface DataSource { id: string; name: string; status: 'Mock Mode' | 'Not Connected' | 'Planned' | 'Not Configured'; detail: string }
export interface PageDetail {
  id: string; url: string; period: Period; current: Metrics; previous: Metrics;
  performance: PerformancePoint[]; queries: DimensionRow[];
}
