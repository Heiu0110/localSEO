import { queryOptions } from '@tanstack/react-query';
import { api, ApiError } from './apiClient';
import type { CountryReport, DataSource, Days, DimensionReport, Overview, PageDetail, Performance, Site } from '../types/api';

function report<T>(name: string, site: string, days: Days) {
  return queryOptions({
    queryKey: [name, site, days],
    queryFn: ({ signal }) => api<T>(`/dashboard/${name}?site_id=${encodeURIComponent(site)}&days=${days}`, signal),
    enabled: !!site,
    retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
  });
}
export const sitesQuery = queryOptions({ queryKey: ['sites'], queryFn: ({ signal }) => api<Site[]>('/sites', signal) });
export const sourcesQuery = queryOptions({ queryKey: ['sources'], queryFn: ({ signal }) => api<DataSource[]>('/dashboard/sources', signal) });
export const overviewQuery = (site: string, days: Days) => report<Overview>('overview', site, days);
export const performanceQuery = (site: string, days: Days) => report<Performance>('performance', site, days);
export const pagesQuery = (site: string, days: Days) => report<DimensionReport>('pages', site, days);
export const queriesQuery = (site: string, days: Days) => report<DimensionReport>('queries', site, days);
export const countriesQuery = (site: string, days: Days) => report<CountryReport>('countries', site, days);
export const detailQuery = (site: string, days: Days, id: string | null) => queryOptions({
  queryKey: ['page-detail', site, days, id],
  queryFn: ({ signal }) => api<PageDetail>(`/dashboard/pages/${encodeURIComponent(id!)}?site_id=${encodeURIComponent(site)}&days=${days}`, signal),
  enabled: !!id && !!site,
});
