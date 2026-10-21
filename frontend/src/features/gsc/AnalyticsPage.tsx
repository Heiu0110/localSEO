import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { Info } from 'lucide-react';
import { propertiesQuery, integrationQuery, gscOverviewQuery, gscPerformanceQuery } from '../../services/gscApi';
import { AnalyticsTable, tabLabels } from '../../components/gsc/AnalyticsTable';
import { SyncPanel, shiftDay, searchTypes, jobLabels } from '../../components/gsc/SyncPanel';
import { MetricCard } from '../../components/dashboard/MetricCard';
import { PerformanceChart } from '../../components/dashboard/PerformanceChart';
import { PageDetailPanel } from '../../components/dashboard/PageDetailPanel';
import { SourceBadge, sourceLabel } from '../../components/dashboard/SourceBadge';
import { Button } from '../../components/ui/button';
import { DashboardSkeleton, EmptyState, ErrorState } from '../../components/ui/states';
import type { AnalyticsFilters, AnalyticsTab } from '../../types/gsc';
import type { DimensionRow, MetricKey, SearchType } from '../../types/api';
import { date, timestamp } from '../../lib/format';

export function AnalyticsPage() {
  const properties = useQuery(propertiesQuery);
  const status = useQuery(integrationQuery);
  const [params, setParams] = useSearchParams();
  const latestParams = useRef(params);
  useEffect(() => { latestParams.current = params; }, [params]);
  const [compare, setCompare] = useState(true);
  const active = properties.data?.filter(p => p.is_active) ?? [];
  const requestedSite = params.get('site');
  const selected = requestedSite && !['xuong-may','cong-ty'].includes(requestedSite) ? active.find(p => p.id === requestedSite) : active[0];
  const days = ['7','28','90'].includes(params.get('days') ?? '') ? Number(params.get('days')) : 28;
  const end = params.get('end') || selected?.local_end || status.data?.latest_final_date || '';
  const start = params.get('start') || (end ? shiftDay(end, -days+1) : '');
  const type = (Object.keys(searchTypes).includes(params.get('type') ?? '') ? params.get('type') : 'web') as SearchType;
  const tab = (Object.keys(tabLabels).includes(params.get('tab') ?? '') ? params.get('tab') : 'overview') as AnalyticsTab;
  useEffect(() => {
    if (selected && params.get('site') !== selected.id) setParams(old => { old.set('site',selected.id); return old; }, { replace: true });
  }, [selected?.id, params.get('site'), setParams]);
  function update(values: Record<string,string>) {
    const next = new URLSearchParams(latestParams.current);
    Object.entries(values).forEach(([key,value]) => next.set(key,value));
    if (selected && !next.has('site')) next.set('site',selected.id);
    latestParams.current = next;
    setParams(next);
  }
  const valid = !!selected && !!start && !!end && start <= end && (Date.parse(end)-Date.parse(start))/86400000 <= 500;
  const filters: AnalyticsFilters = { property: selected?.id ?? '', start, end, type };
  return <div className="gsc-page"><div className="page-title-row"><div><div className="eyebrow">DỮ LIỆU SEARCH CONSOLE ĐÃ LƯU</div><h1>Phân tích GSC{selected && <SourceBadge source={selected.source_type} />}</h1><p>Phân tích dữ liệu SQLite ngoại tuyến, theo đúng phạm vi tổng hợp.</p></div></div>
    {properties.isPending ? <DashboardSkeleton /> : properties.isError ? <ErrorState message={properties.error.message} onRetry={() => void properties.refetch()} /> : !selected ? <><EmptyState title="Chưa có property trong workspace" detail="Kết nối Google hoặc thêm bộ thử nghiệm SQLite tại Cài đặt. Hai website demo vẫn hoạt động tại Tổng quan." /><Button asChild><Link to="/settings">Mở Cài đặt Google Search Console</Link></Button></> : <>
      <div className="analytics-filters"><label>Property<select aria-label="Property phân tích" value={selected.id} onChange={e => { const p=active.find(p=>p.id===e.target.value); const nextEnd=p?.local_end || status.data?.latest_final_date || end; update({site:e.target.value,end:nextEnd,start:shiftDay(nextEnd,-days+1)}); }}>{active.map(p=><option value={p.id} key={p.id}>[{sourceLabel(p.source_type)}] {p.site_url}</option>)}</select></label><label>Khoảng nhanh<select aria-label="Khoảng nhanh GSC" value={days} onChange={e=>update({days:e.target.value,start:shiftDay(end,-Number(e.target.value)+1),end})}>{[7,28,90].map(n=><option key={n} value={n}>{n} ngày</option>)}</select></label><label>Từ ngày<input aria-label="Phân tích từ ngày" type="date" value={start} max={end} onChange={e=>update({start:e.target.value})} /></label><label>Đến ngày<input aria-label="Phân tích đến ngày" type="date" value={end} min={start} onChange={e=>update({end:e.target.value})} /></label><label>Search type<select aria-label="Search type phân tích" value={type} onChange={e=>update({type:e.target.value})}>{Object.entries(searchTypes).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>
      <div className="analytics-meta"><label className="compare-control"><input type="checkbox" checked={compare} onChange={e=>setCompare(e.target.checked)} />So sánh hai kỳ bằng nhau</label><span>{jobLabels[selected.sync_status] ?? selected.sync_status} · Đồng bộ: {selected.last_synced_at ? timestamp(selected.last_synced_at) : 'Chưa có'}</span></div>
      <div className="analytics-tabs" role="tablist" aria-label="Báo cáo GSC">{Object.entries(tabLabels).map(([key,label])=><button role="tab" aria-selected={tab===key} key={key} onClick={()=>update({tab:key})}>{label}</button>)}</div>
      {!valid ? <div className="report-warning" role="alert">Chọn khoảng ngày hợp lệ, tối đa 501 ngày.</div> : <AnalyticsContent key={`${selected.id}-${start}-${end}-${type}`} filters={filters} tab={tab} compare={compare} />}
      <details className="sync-details"><summary>Đồng bộ và lịch sử tác vụ</summary><SyncPanel key={selected.id} property={selected} /></details>
    </>}
  </div>;
}

function AnalyticsContent({ filters, tab, compare }: { filters: AnalyticsFilters; tab: AnalyticsTab; compare: boolean }) {
  const overview = useQuery(gscOverviewQuery(filters));
  const performance = useQuery(gscPerformanceQuery(filters));
  const [page, setPage] = useState<DimensionRow | null>(null);
  if (overview.isError || performance.isError) return <ErrorState message={(overview.error ?? performance.error)!.message} onRetry={()=>{void overview.refetch();void performance.refetch();}} />;
  if (!overview.data || !performance.data) return <DashboardSkeleton />;
  const o = overview.data;
  const canCompare = compare && o.comparison_available;
  return <><div className="report-warning" role="status"><Info size={15} /><div><p>{date(o.period.start)} – {date(o.period.end)}{compare && ` · Kỳ trước: ${date(o.previous_period.start)} – ${date(o.previous_period.end)}`}. KPI chỉ dùng site dataset byProperty, không cộng Top Queries/Pages.</p><p>Độ phủ tổng: {o.coverage?.current.available_days ?? 0}/{o.period.days} ngày có bản ghi; {o.coverage?.current.empty_days ?? 0} ngày API trả rỗng. {o.warnings.join(' ')}</p><p>Đọc từ SQLite; có thể phân tích khi mất Internet. Đồng bộ để cập nhật dữ liệu. Các dòng chi tiết có thể bị lọc hoặc giới hạn API.</p></div></div>
    {tab === 'overview' ? !o.has_data ? <EmptyState title="Chưa có dữ liệu tổng trong kỳ này" detail="Đồng bộ site dataset hoặc chọn lại kỳ/search type. Không dùng số liệu demo thay cho property này." /> : <><div className="kpi-grid">{(['clicks','impressions','ctr','position'] as MetricKey[]).map(name=><MetricCard key={name} name={name} overview={o} points={performance.data.points} compare={compare} />)}</div><PerformanceChart points={performance.data.points} compare={canCompare} /><div className="report-grid"><AnalyticsTable dataset="pages" filters={filters} compare={canCompare} onPage={setPage} compact /><AnalyticsTable dataset="queries" filters={filters} compare={canCompare} compact /></div></> : <AnalyticsTable key={tab} dataset={tab} filters={filters} compare={canCompare} onPage={setPage} />}
    <PageDetailPanel selected={page} onClose={()=>setPage(null)} site={filters.property} days={28} compare={canCompare} filters={filters} />
  </>;
}
