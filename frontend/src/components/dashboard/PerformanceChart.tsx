import { useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartNoAxesCombined } from 'lucide-react';
import { compact, date, metric, metricNames } from '../../lib/format';
import type { MetricKey, PerformancePoint } from '../../types/api';

interface PlotPoint { date: string; previousDate: string; current: number; previous: number }
function ChartTooltip({ active, payload, name, current, previous }: { active?: boolean; payload?: ReadonlyArray<{ payload: PlotPoint }>; name: MetricKey; current: boolean; previous: boolean }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <div className="chart-tooltip"><strong>{metricNames[name]}</strong>{current && <div><span>{date(row.date)}</span><b>{metric(row.current, name)}</b></div>}{previous && <div><span>{date(row.previousDate)} · prior</span><b>{metric(row.previous, name)}</b></div>}</div>;
}

export function PerformanceChart({ points, compare, simple = false }: { points: PerformancePoint[]; compare: boolean; simple?: boolean }) {
  const [name, setName] = useState<MetricKey>('clicks');
  const [showCurrent, setCurrent] = useState(true);
  const [showPrevious, setPrevious] = useState(true);
  const plot = points.map(p => ({ date: p.date, previousDate: p.previous_date, current: p.metrics[name], previous: p.previous_metrics[name] }));
  return <section className={`card performance-card ${simple ? 'simple-chart' : ''}`} aria-label={`${metricNames[name]} performance chart`} data-metric={name}>
    <div className="card-heading"><div><h2>{!simple && <ChartNoAxesCombined size={17} />}Search performance</h2><p>{simple ? 'Daily clicks for this page' : 'Your organic search visibility, over time.'}</p></div>{!simple && <div className="metric-tabs" aria-label="Chart metric">{(Object.keys(metricNames) as MetricKey[]).map(key => <button key={key} aria-pressed={key === name} onClick={() => setName(key)}>{metricNames[key]}</button>)}</div>}</div>
    <div className="chart-legend"><button aria-pressed={showCurrent} onClick={() => setCurrent(v => !v)} className={!showCurrent ? 'series-off' : ''}><span className="legend-line" />Current period</button>{compare && <button aria-pressed={showPrevious} onClick={() => setPrevious(v => !v)} className={!showPrevious ? 'series-off' : ''}><span className="legend-line previous" />Previous period</button>}<span className="chart-unit">{name === 'ctr' ? 'CTR (%)' : name === 'position' ? 'Average position · lower is better' : metricNames[name]}</span></div>
    <div className="chart-area">{showCurrent || (compare && showPrevious) ? <ResponsiveContainer width="100%" height="100%" minWidth={0}><LineChart data={plot} margin={{ top: 14, right: 10, left: 0, bottom: 6 }} accessibilityLayer>
      <CartesianGrid vertical={false} stroke="#e9efed" strokeDasharray="3 4" />
      <XAxis dataKey="date" tickFormatter={value => date(String(value), true)} tick={{ fontSize: 11, fill: '#718380' }} axisLine={false} tickLine={false} minTickGap={40} dy={8} />
      <YAxis width={simple ? 38 : 49} tickFormatter={value => name === 'ctr' ? `${Number(value).toFixed(1)}%` : name === 'position' ? Number(value).toFixed(1) : compact(Number(value))} tick={{ fontSize: 11, fill: '#718380' }} axisLine={false} tickLine={false} domain={name === 'position' ? ['auto', 'auto'] : [0, 'auto']} />
      <Tooltip content={<ChartTooltip name={name} current={showCurrent} previous={compare && showPrevious} />} cursor={{ stroke: '#b5d3cd', strokeDasharray: '3 3' }} />
      {compare && showPrevious && <Line name="Previous period" type="monotone" dataKey="previous" stroke="#adc5c0" strokeWidth={1.8} strokeDasharray="5 5" dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />}
      {showCurrent && <Line name="Current period" type="monotone" dataKey="current" stroke="#0d9488" strokeWidth={2.4} dot={false} activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />}
    </LineChart></ResponsiveContainer> : <div className="state-box"><p>Select a series above to display the chart.</p></div>}</div>
  </section>;
}
