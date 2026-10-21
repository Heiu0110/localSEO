import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { CalendarDays, ChevronDown, Globe2, Info, RefreshCw } from 'lucide-react';
import { countriesQuery, overviewQuery, pagesQuery, performanceQuery, queriesQuery, sitesQuery } from '../../services/dashboardApi';
import type { Days, DimensionRow, MetricKey } from '../../types/api';
import { date } from '../../lib/format';
import { Button } from '../../components/ui/button';
import { DashboardSkeleton, EmptyState, ErrorState } from '../../components/ui/states';
import { MetricCard } from '../../components/dashboard/MetricCard';
import { PerformanceChart } from '../../components/dashboard/PerformanceChart';
import { PerformanceTable } from '../../components/dashboard/PerformanceTable';
import { CountryPerformance } from '../../components/dashboard/CountryPerformance';
import { DataSourceStatus } from '../../components/dashboard/DataSourceStatus';
import { PageDetailPanel } from '../../components/dashboard/PageDetailPanel';
import { Sheet } from '../../components/ui/sheet';
import { metric, metricNames } from '../../lib/format';

export function DashboardPage() {
  const sites = useQuery(sitesQuery);
  const [params, setParams] = useSearchParams();
  const site = params.get('site') || sites.data?.[0]?.id || '';
  const rawDays = Number(params.get('days') || 28);
  const days: Days = rawDays === 7 || rawDays === 90 ? rawDays : 28;
  const [compare, setCompare] = useState(true);
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set('site', site);
    next.set('days', String(days));
    next.set(key, value);
    setParams(next);
  }
  return <div className="dashboard-page"><div className="page-title-row"><div><div className="eyebrow">YOUR SEARCH, AT A GLANCE</div><h1>SEO Overview<span className="badge badge-mock">Mock Data</span></h1><p>Website Search Performance Dashboard</p></div><div className="workspace-version"><span className="status-dot" />Offline demo workspace</div></div>
    <div className="filter-bar"><div className="filter-group"><label className="select-control site-control"><Globe2 size={17} /><span className="sr-only">Website</span><select aria-label="Website" value={site} disabled={!sites.data?.length} onChange={e => update('site', e.target.value)}>{site && !sites.data?.some(s => s.id === site) && <option value={site}>Unknown site</option>}{sites.data?.map(s => <option key={s.id} value={s.id}>{s.domain}</option>)}</select><ChevronDown size={14} /></label><label className="select-control"><CalendarDays size={16} /><span className="sr-only">Date range</span><select aria-label="Date range" value={days} onChange={e => update('days', e.target.value)}><option value="7">Last 7 days</option><option value="28">Last 28 days</option><option value="90">Last 90 days</option></select><ChevronDown size={14} /></label></div><label className="compare-control"><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} />Compare to previous period</label></div>
    {sites.isPending ? <DashboardSkeleton /> : sites.isError ? <ErrorState message={sites.error.message} onRetry={() => void sites.refetch()} /> : !sites.data.length ? <EmptyState title="No demo websites available" detail="Restart the local backend to load the mock provider." /> : <DashboardReport key={`${site}-${days}`} site={site} days={days} compare={compare} />}
  </div>;
}

function DashboardReport({ site, days, compare }: { site: string; days: Days; compare: boolean }) {
  const overview = useQuery(overviewQuery(site, days));
  const performance = useQuery(performanceQuery(site, days));
  const pages = useQuery(pagesQuery(site, days));
  const queries = useQuery(queriesQuery(site, days));
  const countries = useQuery(countriesQuery(site, days));
  const [selectedPage, setSelectedPage] = useState<DimensionRow | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<DimensionRow | null>(null);
  const reports = [overview, performance, pages, queries, countries];
  const error = reports.find(r => r.isError);
  if (error) return <ErrorState message={error.error!.message} onRetry={() => { reports.forEach(r => void r.refetch()); }} />;
  if (!overview.data || !performance.data || !pages.data || !queries.data || !countries.data) return <DashboardSkeleton />;
  const data = overview.data;
  const filename = `mock-pages-${site}-${data.period.start}-${data.period.end}.csv`;
  return <>
    <div className="report-meta"><span><span className="report-label">REPORTING PERIOD</span>{date(data.period.start)} – {date(data.period.end)}{compare && <span className="comparison-dates">vs. {date(data.previous_period.start, true)} – {date(data.previous_period.end)}</span>}</span><span className="updated"><RefreshCw size={12} />Mock updated: {new Date(data.last_updated).toLocaleString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })} UTC</span></div>
    <div className="kpi-grid">{(['clicks', 'impressions', 'ctr', 'position'] as MetricKey[]).map(name => <MetricCard key={name} name={name} overview={data} points={performance.data.points} compare={compare} />)}</div>
    <PerformanceChart points={performance.data.points} compare={compare} />
    <div className="report-grid"><PerformanceTable kind="pages" rows={pages.data.rows} compare={compare} onSelect={setSelectedPage} filename={filename} /><PerformanceTable kind="queries" rows={queries.data.rows} compare={compare} onSelect={setSelectedQuery} /></div>
    <div className="bottom-grid"><CountryPerformance rows={countries.data.rows} /><DataSourceStatus /></div>
    <div className="mock-notice"><Info size={15} /><span>You’re exploring a complete, synthetic dataset. Reporting windows end on {date(data.dataset_end)}. No live website or Google data is used.</span></div>
    <PageDetailPanel selected={selectedPage} onClose={() => setSelectedPage(null)} site={site} days={days} compare={compare} />
    <Sheet open={!!selectedQuery} onOpenChange={open => { if (!open) setSelectedQuery(null); }} title="Search query" description="Mock query metrics for the currently selected website and reporting period.">{selectedQuery && <><h3 className="query-title">{selectedQuery.label}</h3><span className="badge badge-mock">Mock Data · Last {days} days</span><div className="detail-kpis">{(Object.keys(metricNames) as MetricKey[]).map(key => <div key={key}><span>{metricNames[key]}</span><strong>{metric(selectedQuery.metrics[key], key)}</strong>{compare && <small>Prior: {metric(selectedQuery.previous[key], key)}</small>}</div>)}</div><p className="detail-note">Average position varies with the query mix. This synthetic dataset does not represent a fixed live keyword ranking.</p><Button variant="outline" onClick={() => setSelectedQuery(null)}>Back to report</Button></>}</Sheet>
  </>;
}
