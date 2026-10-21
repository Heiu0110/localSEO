import { useQuery } from '@tanstack/react-query';
import { Activity, Bot, Database, Link2, BarChart3, SearchCheck } from 'lucide-react';
import { sourcesQuery } from '../../services/dashboardApi';
import { ErrorState } from '../ui/states';

const icons = { gsc: SearchCheck, ga4: BarChart3, technical: Activity, backlinks: Link2, ai: Bot };
export function DataSourceStatus() {
  const query = useQuery(sourcesQuery);
  return <section className="card sources-card"><div className="card-heading"><div><h2><Database size={17} />Data sources</h2><p>A clear picture of what’s connected.</p></div></div>{query.isPending ? <div className="skeleton skeleton-chart" role="status" aria-label="Loading data sources" /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className="source-list">{query.data.map(source => {
    const Icon = icons[source.id as keyof typeof icons] ?? Database;
    return <div className="source-row" key={source.id} title={source.detail}><span className={`source-icon source-${source.id}`}><Icon size={18} /></span><strong>{source.name}</strong><span className={`source-status ${source.status === 'Mock Mode' ? 'mock' : ''}`}><span />{source.status}</span></div>;
  })}</div>}<div className="sources-footnote">Demo workspace. No live accounts connected.</div></section>;
}
