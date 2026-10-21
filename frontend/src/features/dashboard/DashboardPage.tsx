import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
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
import { SourceBadge, sourceLabel } from '../../components/dashboard/SourceBadge';

export function DashboardPage() {
  const sites = useQuery(sitesQuery);
  const [params, setParams] = useSearchParams();
  const latestParams = useRef(params);
  useEffect(() => { latestParams.current = params; }, [params]);
  const site = params.get('site') || sites.data?.[0]?.id || '';
  const rawDays = Number(params.get('days') || 28);
  const days: Days = rawDays === 7 || rawDays === 90 ? rawDays : 28;
  const [compare, setCompare] = useState(true);
  const source = sites.data?.find(s => s.id === site)?.source_type ?? 'mock';
  function update(key: string, value: string) {
    // React Router transitions can overlap when two controls change rapidly.
    const next = new URLSearchParams(latestParams.current);
    if (!next.has('site')) next.set('site', site);
    if (!next.has('days')) next.set('days', String(days));
    next.set(key, value);
    latestParams.current = next;
    setParams(next);
  }
  return <div className="dashboard-page"><div className="page-title-row"><div><div className="eyebrow">HIỆU SUẤT TÌM KIẾM TRONG TẦM MẮT</div><h1>Tổng quan SEO<SourceBadge source={source} /></h1><p>Theo dõi và phân tích hiệu suất tìm kiếm của website</p></div><div className="workspace-version"><span className="status-dot" />{source === 'mock' ? 'Không gian mô phỏng ngoại tuyến' : 'Dữ liệu đã lưu trong SQLite'}</div></div>
    <div className="filter-bar"><div className="filter-group"><label className="select-control site-control"><Globe2 size={17} /><span className="sr-only">Website</span><select aria-label="Website" value={site} disabled={!sites.data?.length} onChange={e => update('site', e.target.value)}>{site && !sites.data?.some(s => s.id === site) && <option value={site}>Website không tồn tại</option>}{sites.data?.map(s => <option key={s.id} value={s.id}>[{sourceLabel(s.source_type)}] {s.domain}</option>)}</select><ChevronDown size={14} /></label><label className="select-control"><CalendarDays size={16} /><span className="sr-only">Khoảng thời gian</span><select aria-label="Khoảng thời gian" value={days} onChange={e => update('days', e.target.value)}><option value="7">7 ngày gần nhất</option><option value="28">28 ngày gần nhất</option><option value="90">90 ngày gần nhất</option></select><ChevronDown size={14} /></label></div><label className="compare-control"><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} />So sánh với kỳ trước</label></div>
    {sites.isPending ? <DashboardSkeleton /> : sites.isError ? <ErrorState message={sites.error.message} onRetry={() => void sites.refetch()} /> : !sites.data.length ? <EmptyState title="Chưa có website mô phỏng" detail="Khởi động lại backend cục bộ để tải dữ liệu mô phỏng." /> : <DashboardReport key={`${site}-${days}`} site={site} days={days} compare={compare} />}
  </div>;
}

function DashboardReport({ site, days, compare }: { site: string; days: Days; compare: boolean }) {
  const overview = useQuery(overviewQuery(site, days));
  const performance = useQuery({ ...performanceQuery(site, days, overview.data?.period.end), enabled: !!overview.data });
  const pages = useQuery({ ...pagesQuery(site, days, overview.data?.period.end), enabled: !!overview.data });
  const queries = useQuery({ ...queriesQuery(site, days, overview.data?.period.end), enabled: !!overview.data });
  const countries = useQuery({ ...countriesQuery(site, days, overview.data?.period.end), enabled: !!overview.data });
  const [selectedPage, setSelectedPage] = useState<DimensionRow | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<DimensionRow | null>(null);
  const reports = [overview, performance, pages, queries, countries];
  const error = reports.find(r => r.isError);
  if (error) return <ErrorState message={error.error!.message} onRetry={() => { reports.forEach(r => void r.refetch()); }} />;
  if (!overview.data || !performance.data || !pages.data || !queries.data || !countries.data) return <DashboardSkeleton />;
  const data = overview.data;
  const partial = data.source !== 'mock';
  const canCompare = compare && data.comparison_available !== false;
  if (data.has_data === false) return <><EmptyState title="Chưa có dữ liệu đã đồng bộ" detail="Property được giữ riêng với demo. Đồng bộ dữ liệu trong Cài đặt; ứng dụng không tự thay bằng số liệu mô phỏng." /><Button asChild variant="outline"><Link to={`/settings?site=${encodeURIComponent(site)}`}>Đến Cài đặt để đồng bộ</Link></Button></>;
  const filename = `${partial ? 'stored' : 'mock'}-pages-${site}-${data.period.start}-${data.period.end}.csv`;
  return <>
    <div className="report-meta"><span><span className="report-label">KỲ BÁO CÁO</span>{date(data.period.start)} – {date(data.period.end)}{compare && <span className="comparison-dates">so với {date(data.previous_period.start, true)} – {date(data.previous_period.end)}</span>}</span><span className="updated"><RefreshCw size={12} />{partial ? 'Đồng bộ gần nhất:' : 'Cập nhật mô phỏng:'} {new Date(data.last_updated).toLocaleString('vi-VN', { timeZone: 'Asia/Bangkok', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })} (UTC+7)</span></div>
    {partial && <div className="report-warning" role="status"><Info size={15} /><div>{data.warnings.map(message => <p key={message}>{message}</p>)}<p>KPI dùng dữ liệu tổng cấp property (byProperty). Bảng chi tiết là Top 100 đã lưu; API có thể giới hạn. Phân tích và xuất toàn bộ dữ liệu đã lưu tại <Link to={`/gsc-analytics?site=${site}`}>Phân tích GSC</Link>.</p></div></div>}
    <div className="kpi-grid">{(['clicks', 'impressions', 'ctr', 'position'] as MetricKey[]).map(name => <MetricCard key={name} name={name} overview={data} points={performance.data.points} compare={compare} />)}</div>
    <PerformanceChart points={performance.data.points} compare={canCompare} />
    <div className="report-grid"><PerformanceTable kind="pages" rows={pages.data.rows} compare={canCompare} onSelect={setSelectedPage} filename={filename} partial={partial} /><PerformanceTable kind="queries" rows={queries.data.rows} compare={canCompare} onSelect={setSelectedQuery} partial={partial} /></div>
    <div className="bottom-grid"><CountryPerformance rows={countries.data.rows} partial={partial} /><DataSourceStatus site={site} /></div>
    <div className="mock-notice"><Info size={15} /><span>{partial ? `Đọc ngoại tuyến từ SQLite · ngày có dữ liệu gần nhất ${date(data.dataset_end)}. ${data.source === 'fixture' ? 'Đây là dữ liệu thử nghiệm, không phải tài khoản Google thật.' : 'Đồng bộ trong Cài đặt để làm mới dữ liệu.'}` : `Bạn đang xem bộ dữ liệu mô phỏng đầy đủ. Kỳ báo cáo kết thúc vào ${date(data.dataset_end)}. Không sử dụng dữ liệu thực từ website hoặc Google.`}</span></div>
    <PageDetailPanel selected={selectedPage} onClose={() => setSelectedPage(null)} site={site} days={days} compare={canCompare} end={data.period.end} />
    <Sheet open={!!selectedQuery} onOpenChange={open => { if (!open) setSelectedQuery(null); }} title="Truy vấn tìm kiếm" description="Chỉ số truy vấn của website và kỳ báo cáo đang chọn; phạm vi theo nguồn dữ liệu.">{selectedQuery && <><h3 className="query-title">{selectedQuery.label}</h3><SourceBadge source={data.source} /><div className="detail-kpis">{(Object.keys(metricNames) as MetricKey[]).map(key => <div key={key}><span>{metricNames[key]}</span><strong>{metric(selectedQuery.metrics[key], key)}</strong>{canCompare && <small>Kỳ trước: {metric(selectedQuery.previous[key], key)}</small>}</div>)}</div><p className="detail-note">Vị trí trung bình thay đổi theo cơ cấu truy vấn. Dữ liệu trung bình này không thể hiện thứ hạng cố định của từ khóa thực tế.</p><Button variant="outline" onClick={() => setSelectedQuery(null)}>Quay lại báo cáo</Button></>}</Sheet>
  </>;
}
