import { ArrowDownRight, ArrowUpRight, CircleHelp, MousePointer2, Eye, Percent, ListOrdered } from 'lucide-react';
import type { MetricKey, Overview, PerformancePoint } from '../../types/api';
import { metric, signed } from '../../lib/format';
import { Tooltip } from '../ui/tooltip';

const config = {
  clicks: { label: 'Total Clicks', icon: MousePointer2, info: 'Organic Google Search clicks in this mock dataset. Clicks are not GA4 sessions.' },
  impressions: { label: 'Total Impressions', icon: Eye, info: 'Times a result appeared in Google Search, simulated here. Not advertising impressions.' },
  ctr: { label: 'Average CTR', icon: Percent, info: 'Total clicks ÷ total impressions × 100. Comparison is in percentage points.' },
  position: { label: 'Average Position', icon: ListOrdered, info: 'Impression-weighted average position. Lower usually means better visibility; query mix can also affect this metric.' },
};

export function Sparkline({ values, positive = true }: { values: number[]; positive?: boolean }) {
  const min = Math.min(...values), span = Math.max(...values) - min || 1;
  const points = values.map((v, i) => `${i / Math.max(1, values.length - 1) * 100},${30 - (v - min) / span * 25}`).join(' ');
  return <svg className={`sparkline ${positive ? '' : 'negative'}`} viewBox="0 0 100 35" aria-hidden="true"><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round" /></svg>;
}

export function MetricCard({ name, overview, points, compare }: { name: MetricKey; overview: Overview; points: PerformancePoint[]; compare: boolean }) {
  const { label, icon: Icon, info } = config[name];
  const change = overview.changes[name];
  const good = name === 'position' ? change.delta <= 0 : change.delta >= 0;
  const Direction = change.delta >= 0 ? ArrowUpRight : ArrowDownRight;
  const delta = name === 'ctr' ? `${signed(change.delta, 2)} pp` : name === 'position' ? `${signed(change.delta)} places` : change.percent === null ? 'No prior data' : `${signed(change.percent)}%`;
  return <section className="card metric-card" aria-label={label}><div className="metric-top"><span className="metric-label"><Icon size={15} />{label}</span><Tooltip text={info}><button className="help-button" aria-label={`About ${label}`}><CircleHelp size={14} /></button></Tooltip></div>
    <div className="metric-value-row"><strong className="metric-value" data-testid={`metric-${name}`}>{metric(overview.current[name], name)}</strong><Sparkline values={points.map(p => p.metrics[name])} positive={good} /></div>
    <div className="metric-bottom">{compare ? <><span className={`trend ${good ? 'positive' : 'negative'}`}><Direction size={14} />{delta}</span><span>vs. previous period</span></> : <span>Selected reporting period</span>}</div>
  </section>;
}
