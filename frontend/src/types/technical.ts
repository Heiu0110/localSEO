export interface CrawlConfig {
  mode: 'quick' | 'standard' | 'advanced'; max_urls: number; delay_seconds: number; max_depth: number; timeout_seconds: number;
  allowed_hosts: string[]; include_patterns: string[]; exclude_patterns: string[]; query_policy: 'preserve' | 'drop_tracking' | 'drop_all';
  follow_redirects: boolean; sitemap_urls: string[]; important_urls: string[]; use_gsc: boolean; user_agent: string;
}
export interface AuditProject { id: string; name: string; root_url: string; property_id: string | null; source_type: 'live' | 'fixture'; config: CrawlConfig; created_at: string; updated_at: string }
export interface AuditSummary {
  discovered?: number; crawled?: number; robots_blocked?: number; issues?: number; critical?: number; high?: number; broken_links?: number; redirects?: number; sitemap_errors?: number; canonical_issues?: number; maximum_depth?: number;
  http?: Record<string,number>; indexability?: Record<string,number>; severity?: Record<string,number>; checks?: Record<string,number>;
}
export interface AuditRun { id: string; project_id: string; name: string; status: string; phase: string; processed: number; requests: number; config: CrawlConfig; coverage: { complete?: boolean; warnings?: string[]; sources?: Record<string,string>; robots?: Record<string,unknown>; gsc?: unknown }; summary: AuditSummary; started_at: string; finished_at: string | null; error: string | null }
export interface TechnicalRule { id: string; name: string; category: string; capability: string; state: string; evaluated_urls: number; priority_group: string; version: string; recommendation: string }
export interface TechnicalOverview extends AuditRun { project: AuditProject; top_issues: TechnicalIssue[]; rules: TechnicalRule[] }
export interface TechnicalPageResult<T> { rows: T[]; total: number; page: number; page_size: number }
export interface TechnicalIntent { importance: string; should_index: string; page_type?: string; notes?: string }
export interface TechnicalURL { id: string; audit_id: string; url: string; original_url: string; final_url: string | null; state: string; status_code: number | null; depth: number | null; title: string; indexability: string; inbound: number | null; outbound: number | null; duration_ms: number | null; sources: string[]; word_count?: number; intent?: TechnicalIntent; gsc?: { clicks:number; impressions:number; start:string; end:string; search_type:string }; fetch_error?: string }
export interface TechnicalURLDetail extends TechnicalURL { data: Record<string,unknown>; incoming: TechnicalLink[]; outgoing: TechnicalLink[]; issues: TechnicalIssue[]; google_index_status: null; google_selected_canonical: null; limitations: string[]; canonical_target_status: number | null }
export interface TechnicalIssue { id:string; audit_id:string; project_id:string; url:string; url_id:string; fingerprint:string; rule_id:string; category:string; title:string; severity:string; confidence:string; evidence_type:string; evidence:Record<string,unknown>; recommendation:string; verification:string; priority:number; priority_reasons:string[]; first_seen_at:string; last_seen_at:string; affected_url_count?:number; status?:string; task?:TechnicalTask; description?:string; expected_behavior?:string; actual_behavior?:unknown; business_impact?:string }
export interface TechnicalTask { id:string; project_id:string; rule_id:string; url:string; title:string; severity:string; status:string; owner:string; notes:string; verification:string; verification_audit_id:string|null; priority:number; first_seen_at:string; last_seen_at:string }
export interface TechnicalLink { id:number; source_url?:string; target_url:string; anchor:string; rel:string; context:string; internal:boolean; target_status:number|null }
export interface TechnicalSitemap { id:string; url:string; status_code:number|null; data:{valid:boolean;kind?:string;entries?:number;error?:string;content_type?:string} }
export interface TechnicalComparison { comparable:boolean; warning:string|null; counts:Record<string,number>; rows:Array<{id:string;state:string;rule_id:string;url:string;title:string;severity:string}>; total:number; url_changes:Array<{url:string;changes:Record<string,unknown>}>; url_changes_total:number }
export interface TechnicalImport { id:string; filename:string; count:number; preview:Array<{url:string;importance:string;should_index:string}>; status:string }
