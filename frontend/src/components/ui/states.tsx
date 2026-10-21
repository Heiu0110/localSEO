import { AlertCircle, SearchX } from 'lucide-react';
import { Button } from './button';

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div role="alert" className="state-box error-box"><AlertCircle size={23} /><strong>We couldn’t load this report</strong><p>{message}</p><Button variant="outline" onClick={onRetry}>Try again</Button></div>;
}
export function EmptyState({ title = 'No matching results', detail = 'Try a different search or clear your filter.' }: { title?: string; detail?: string }) {
  return <div className="state-box"><SearchX size={25} /><strong>{title}</strong><p>{detail}</p></div>;
}
export function DashboardSkeleton() {
  return <div aria-label="Loading dashboard" role="status" className="dashboard-skeleton"><span className="sr-only">Loading report…</span><div className="kpi-grid">{[0,1,2,3].map(i => <div key={i} className="skeleton skeleton-kpi" />)}</div><div className="skeleton skeleton-chart" /><div className="report-grid"><div className="skeleton skeleton-chart" /><div className="skeleton skeleton-chart" /></div></div>;
}
