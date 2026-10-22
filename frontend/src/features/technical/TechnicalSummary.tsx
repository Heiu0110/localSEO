import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { api } from '../../services/apiClient';
import type { AuditRun } from '../../types/technical';
import { count, TechnicalBadge } from './shared';
import { timestamp } from '../../lib/format';

export function TechnicalSummary({site}:{site:string}){
  const query=useQuery({queryKey:['technical','dashboard-summary',site],queryFn:({signal})=>api<AuditRun|null>(`/technical/summary?site_id=${encodeURIComponent(site)}`,signal),staleTime:60000});
  if(!query.data)return null;
  const row=query.data;
  return <section className="card technical-dashboard-summary"><div><h2><Activity size={16}/>Technical SEO đã lưu <TechnicalBadge value={row.status}/></h2><p>{count(row.summary.crawled)} URL crawl · {count(row.summary.critical)} nghiêm trọng · {count(row.summary.high)} mức cao · {timestamp(row.started_at)}</p></div><Link className="button button-outline" to={`/technical-seo?project=${row.project_id}&audit=${row.id}`}>Xem audit kỹ thuật</Link></section>;
}
