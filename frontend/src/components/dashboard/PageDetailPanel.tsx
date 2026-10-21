import { useQuery } from '@tanstack/react-query';
import { detailQuery } from '../../services/dashboardApi';
import { Sheet } from '../ui/sheet';
import { ErrorState } from '../ui/states';
import { PerformanceChart } from './PerformanceChart';
import { metric, metricNames } from '../../lib/format';
import type { Days, DimensionRow, MetricKey } from '../../types/api';

export function PageDetailPanel({ selected, onClose, site, days, compare }: { selected: DimensionRow | null; onClose: () => void; site: string; days: Days; compare: boolean }) {
  const query = useQuery(detailQuery(site, days, selected?.id ?? null));
  return <Sheet open={!!selected} onOpenChange={open => { if (!open) onClose(); }} title="Hiệu suất trang" description="Dữ liệu mô phỏng của URL và kỳ báo cáo đang chọn.">
    <p className="detail-url">{selected?.label}</p><span className="badge badge-mock">Dữ liệu mô phỏng · {days} ngày gần nhất</span>
    {query.isPending ? <div className="skeleton skeleton-chart" role="status" aria-label="Đang tải chi tiết trang" /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <><div className="detail-kpis">{(Object.keys(metricNames) as MetricKey[]).map(key => <div key={key}><span>{metricNames[key]}</span><strong>{metric(query.data.current[key], key)}</strong>{compare && <small>Kỳ trước: {metric(query.data.previous[key], key)}</small>}</div>)}</div>
      <PerformanceChart points={query.data.performance} compare={compare} simple />
      <div className="detail-queries"><h3>Truy vấn tìm kiếm liên quan</h3><p>Toàn bộ truy vấn liên quan đến URL này trong dữ liệu mô phỏng.</p><table><thead><tr><th>Truy vấn</th><th>Lượt nhấp</th><th>Lượt hiển thị</th></tr></thead><tbody>{query.data.queries.map(row => <tr key={row.id}><td>{row.label}</td><td>{metric(row.metrics.clicks, 'clicks')}</td><td>{metric(row.metrics.impressions, 'impressions')}</td></tr>)}</tbody></table></div></>}
  </Sheet>;
}
