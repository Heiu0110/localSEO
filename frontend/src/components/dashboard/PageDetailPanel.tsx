import { useQuery } from '@tanstack/react-query';
import { detailQuery } from '../../services/dashboardApi';
import { Sheet } from '../ui/sheet';
import { ErrorState } from '../ui/states';
import { PerformanceChart } from './PerformanceChart';
import { metric, metricNames } from '../../lib/format';
import type { Days, DimensionRow, MetricKey } from '../../types/api';

export function PageDetailPanel({ selected, onClose, site, days, compare }: { selected: DimensionRow | null; onClose: () => void; site: string; days: Days; compare: boolean }) {
  const query = useQuery(detailQuery(site, days, selected?.id ?? null));
  return <Sheet open={!!selected} onOpenChange={open => { if (!open) onClose(); }} title="Page performance" description="Synthetic data for this URL and the selected reporting period.">
    <p className="detail-url">{selected?.label}</p><span className="badge badge-mock">Mock Data · Last {days} days</span>
    {query.isPending ? <div className="skeleton skeleton-chart" role="status" aria-label="Loading page details" /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <><div className="detail-kpis">{(Object.keys(metricNames) as MetricKey[]).map(key => <div key={key}><span>{metricNames[key]}</span><strong>{metric(query.data.current[key], key)}</strong>{compare && <small>Prior: {metric(query.data.previous[key], key)}</small>}</div>)}</div>
      <PerformanceChart points={query.data.performance} compare={compare} simple />
      <div className="detail-queries"><h3>Related search queries</h3><p>Complete URL–query relationships for this mock page.</p><table><thead><tr><th>Query</th><th>Clicks</th><th>Impressions</th></tr></thead><tbody>{query.data.queries.map(row => <tr key={row.id}><td>{row.label}</td><td>{metric(row.metrics.clicks, 'clicks')}</td><td>{metric(row.metrics.impressions, 'impressions')}</td></tr>)}</tbody></table></div></>}
  </Sheet>;
}
