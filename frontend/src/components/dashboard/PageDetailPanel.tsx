import { useQuery } from '@tanstack/react-query';
import { detailQuery } from '../../services/dashboardApi';
import { Sheet } from '../ui/sheet';
import { ErrorState } from '../ui/states';
import { PerformanceChart } from './PerformanceChart';
import { metric, metricNames } from '../../lib/format';
import type { Days, DimensionRow, MetricKey } from '../../types/api';
import type { AnalyticsFilters } from '../../types/gsc';
import { gscDetailQuery } from '../../services/gscApi';
import { SourceBadge } from './SourceBadge';

export function PageDetailPanel({ selected, onClose, site, days, compare, filters, end }: { selected: DimensionRow | null; onClose: () => void; site: string; days: Days; compare: boolean; filters?: AnalyticsFilters; end?: string }) {
  const query = useQuery(filters ? gscDetailQuery(filters, selected?.id ?? null) : detailQuery(site, days, selected?.id ?? null, end));
  return <Sheet open={!!selected} onOpenChange={open => { if (!open) onClose(); }} title="Hiệu suất trang" description="Dữ liệu của URL và kỳ báo cáo đang chọn. Dòng chi tiết có thể bị giới hạn theo nguồn.">
    <p className="detail-url">{selected?.label}</p><SourceBadge source={query.data?.source} />
    {query.isPending ? <div className="skeleton skeleton-chart" role="status" aria-label="Đang tải chi tiết trang" /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <><div className="detail-kpis">{(Object.keys(metricNames) as MetricKey[]).map(key => <div key={key}><span>{metricNames[key]}</span><strong>{query.data.has_data === false ? '—' : metric(query.data.current[key], key)}</strong>{compare && query.data.comparison_available !== false && <small>Kỳ trước: {metric(query.data.previous[key], key)}</small>}</div>)}</div>
      <PerformanceChart points={query.data.performance} compare={compare && query.data.comparison_available !== false} simple={query.data.source === 'mock'} />
      {query.data.query_relationships_available === false ? <p className="detail-note">Chưa đồng bộ quan hệ URL–query. Không thể suy ra truy vấn của trang từ hai bảng tổng hợp độc lập. Khoảng trống trên biểu đồ là ngày không có bản ghi, không phải 0.</p> : <div className="detail-queries"><h3>Truy vấn tìm kiếm liên quan</h3><p>Toàn bộ truy vấn liên quan đến URL này trong dữ liệu mô phỏng.</p><table><thead><tr><th>Truy vấn</th><th>Lượt nhấp</th><th>Lượt hiển thị</th></tr></thead><tbody>{query.data.queries.map(row => <tr key={row.id}><td>{row.label}</td><td>{metric(row.metrics.clicks, 'clicks')}</td><td>{metric(row.metrics.impressions, 'impressions')}</td></tr>)}</tbody></table></div>}</>}
  </Sheet>;
}
