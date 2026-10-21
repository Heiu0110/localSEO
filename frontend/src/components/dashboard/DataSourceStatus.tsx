import { useQuery } from '@tanstack/react-query';
import { Activity, Bot, Database, Link2, BarChart3, SearchCheck } from 'lucide-react';
import { sourceDetails, sourceStatuses } from '../../lib/labels';
import { sourcesQuery } from '../../services/dashboardApi';
import { ErrorState } from '../ui/states';

const icons = { gsc: SearchCheck, ga4: BarChart3, technical: Activity, backlinks: Link2, ai: Bot };
export function DataSourceStatus({ site }: { site?: string }) {
  const query = useQuery(sourcesQuery(site));
  return <section className="card sources-card"><div className="card-heading"><div><h2><Database size={17} />Nguồn dữ liệu</h2><p>Trạng thái kết nối của các nguồn dữ liệu.</p></div></div>{query.isPending ? <div className="skeleton skeleton-chart" role="status" aria-label="Đang tải nguồn dữ liệu" /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className="source-list">{query.data.map(source => {
    const Icon = icons[source.id as keyof typeof icons] ?? Database;
    return <div className="source-row" key={source.id} title={source.id === 'gsc' && source.status !== 'Mock Mode' ? source.detail : sourceDetails[source.id]?.detail ?? source.detail}><span className={`source-icon source-${source.id}`}><Icon size={18} /></span><strong>{sourceDetails[source.id]?.name ?? source.name}</strong><span className={`source-status ${source.status === 'Mock Mode' ? 'mock' : ''}`}><span />{sourceStatuses[source.status]}</span></div>;
  })}</div>}<div className="sources-footnote">{query.data?.[0]?.status === 'Mock Mode' ? 'Không gian mô phỏng. Chưa kết nối tài khoản thực.' : 'GSC dùng dữ liệu SQLite đã lưu; các nguồn còn lại chưa tích hợp.'}</div></section>;
}
