import { queryOptions } from '@tanstack/react-query';
import { api, ApiError } from './apiClient';
import type { CountryReport, DataSource, Days, DimensionReport, Overview, PageDetail, Performance, Site } from '../types/api';

function report<T>(name: string, site: string, days: Days, end?: string) {
  return queryOptions({
    queryKey: [name, site, days, end],
    queryFn: ({ signal }) => api<T>(`/dashboard/${name}?site_id=${encodeURIComponent(site)}&days=${days}${end ? `&end_date=${end}` : ''}`, signal),
    enabled: !!site,
    retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
  });
}
export const sitesQuery = queryOptions({ queryKey: ['sites'], queryFn: ({ signal }) => api<Site[]>('/sites', signal) });
export const sourcesQuery = (site?: string) => queryOptions({ queryKey: ['sources', site], queryFn: ({ signal }) => api<DataSource[]>(`/dashboard/sources${site ? `?site_id=${encodeURIComponent(site)}` : ''}`, signal) });
export const overviewQuery = (site: string, days: Days) => report<Overview>('overview', site, days);
export const performanceQuery = (site: string, days: Days, end?: string) => report<Performance>('performance', site, days, end);
export const pagesQuery = (site: string, days: Days, end?: string) => report<DimensionReport>('pages', site, days, end);
export const queriesQuery = (site: string, days: Days, end?: string) => report<DimensionReport>('queries', site, days, end);
export const countriesQuery = (site: string, days: Days, end?: string) => report<CountryReport>('countries', site, days, end);
export const detailQuery = (site: string, days: Days, id: string | null, end?: string) => queryOptions<PageDetail>({
  queryKey: ['page-detail', site, days, id, end],
  queryFn: ({ signal }) => api<PageDetail>(`/dashboard/pages/${encodeURIComponent(id!)}?site_id=${encodeURIComponent(site)}&days=${days}${end ? `&end_date=${end}` : ''}`, signal),
  enabled: !!id && !!site,
});
