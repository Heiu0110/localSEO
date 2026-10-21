import { queryOptions } from '@tanstack/react-query';
import { api } from './apiClient';
import type { DimensionReport, Overview, PageDetail, Performance } from '../types/api';
import type { AnalyticsFilters, GSCProperty, IntegrationStatus, SyncJob } from '../types/gsc';

export const integrationQuery = queryOptions({ queryKey: ['gsc-status'], queryFn: ({ signal }) => api<IntegrationStatus>('/integrations/gsc/status', signal), staleTime: 10_000 });
export const propertiesQuery = queryOptions({ queryKey: ['gsc-properties'], queryFn: ({ signal }) => api<GSCProperty[]>('/integrations/gsc/properties', signal) });
export const jobsQuery = (property?: string) => queryOptions({ queryKey: ['gsc-jobs', property], queryFn: ({ signal }) => api<SyncJob[]>(`/gsc/sync/jobs${property ? `?property_id=${encodeURIComponent(property)}` : ''}`, signal), refetchInterval: query => query.state.data?.some(j => ['queued', 'running'].includes(j.status)) ? 1500 : false });
export function filterParams(filters: AnalyticsFilters) {
  return new URLSearchParams({ property_id: filters.property, start_date: filters.start, end_date: filters.end, search_type: filters.type });
}
export function analyticsQuery<T>(name: string, filters: AnalyticsFilters, extras: Record<string, string> = {}) {
  const params = filterParams(filters);
  Object.entries(extras).forEach(([key, value]) => params.set(key, value));
  return queryOptions<T>({ queryKey: ['gsc-analytics', name, filters, extras], queryFn: ({ signal }) => api<T>(`/gsc/analytics/${name}?${params}`, signal), enabled: !!filters.property && !!filters.start && !!filters.end, retry: 1 });
}
export const gscOverviewQuery = (filters: AnalyticsFilters) => analyticsQuery<Overview>('overview', filters);
export const gscPerformanceQuery = (filters: AnalyticsFilters) => analyticsQuery<Performance>('performance', filters);
export const gscRowsQuery = (name: string, filters: AnalyticsFilters, extras: Record<string, string>) => analyticsQuery<DimensionReport>(name, filters, extras);
export const gscDetailQuery = (filters: AnalyticsFilters, id: string | null) => ({ ...analyticsQuery<PageDetail>('pages/detail', filters, { page_id: id || '' }), enabled: !!id && !!filters.property });
export async function downloadReport(dataset: string, filters: AnalyticsFilters, extras: Record<string, string>) {
  const params = filterParams(filters);
  Object.entries(extras).forEach(([key, value]) => params.set(key, value));
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/gsc/export/${dataset}?${params}`);
  if (!response.ok) throw new Error('Không thể xuất dữ liệu. Hãy kiểm tra property và thử lại.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `stored-${dataset}-${filters.property}-${filters.start}-${filters.end}-${filters.type}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
