import { useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartNoAxesCombined } from 'lucide-react';
import { compact, date, decimal, metric, metricNames } from '../../lib/format';
import type { MetricKey, PerformancePoint } from '../../types/api';

interface PlotPoint { date: string; previousDate: string; current: number | null; previous: number | null }
function ChartTooltip({ active, payload, name, current, previous }: { active?: boolean; payload?: ReadonlyArray<{ payload: PlotPoint }>; name: MetricKey; current: boolean; previous: boolean }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <div className="chart-tooltip"><strong>{metricNames[name]}</strong>{current && <div><span>{date(row.date)}</span><b>{row.current === null ? 'Chưa có số liệu' : metric(row.current, name)}</b></div>}{previous && <div><span>{date(row.previousDate)} · kỳ trước</span><b>{row.previous === null ? 'Chưa có số liệu' : metric(row.previous, name)}</b></div>}</div>;
}

export function PerformanceChart({ points, compare, simple = false }: { points: PerformancePoint[]; compare: boolean; simple?: boolean }) {
  const [name, setName] = useState<MetricKey>('clicks');
  const [showCurrent, setCurrent] = useState(true);
  const [showPrevious, setPrevious] = useState(true);
  const plot = points.map(p => ({ date: p.date, previousDate: p.previous_date, current: p.metrics?.[name] ?? null, previous: p.previous_metrics?.[name] ?? null }));
  return <section className={`card performance-card ${simple ? 'simple-chart' : ''}`} aria-label={`Biểu đồ ${metricNames[name]}`} data-metric={name}>
    <div className="card-heading"><div><h2>{!simple && <ChartNoAxesCombined size={17} />}Hiệu suất tìm kiếm</h2><p>{simple ? 'Lượt nhấp theo ngày của trang này' : 'Theo dõi khả năng hiển thị tự nhiên theo thời gian.'}</p></div>{!simple && <div className="metric-tabs" aria-label="Chỉ số biểu đồ">{(Object.keys(metricNames) as MetricKey[]).map(key => <button key={key} aria-pressed={key === name} onClick={() => setName(key)}>{metricNames[key]}</button>)}</div>}</div>
    <div className="chart-legend"><button aria-pressed={showCurrent} onClick={() => setCurrent(v => !v)} className={!showCurrent ? 'series-off' : ''}><span className="legend-line" />Kỳ hiện tại</button>{compare && <button aria-pressed={showPrevious} onClick={() => setPrevious(v => !v)} className={!showPrevious ? 'series-off' : ''}><span className="legend-line previous" />Kỳ trước</button>}<span className="chart-unit">{name === 'ctr' ? 'CTR (%)' : name === 'position' ? 'Vị trí TB · thấp hơn thường tốt hơn' : metricNames[name]}</span></div>
    <div className="chart-area">{showCurrent || (compare && showPrevious) ? <ResponsiveContainer width="100%" height="100%" minWidth={0}><LineChart data={plot} margin={{ top: 14, right: 10, left: 0, bottom: 6 }} accessibilityLayer>
      <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="3 4" />
      <XAxis dataKey="date" tickFormatter={value => date(String(value), true)} tick={{ fontSize: 11, fill: 'var(--muted)' }} axisLine={false} tickLine={false} minTickGap={40} dy={8} />
      <YAxis width={simple ? 46 : 55} tickFormatter={value => name === 'ctr' ? `${decimal(Number(value))}%` : name === 'position' ? decimal(Number(value)) : compact(Number(value))} tick={{ fontSize: 11, fill: 'var(--muted)' }} axisLine={false} tickLine={false} domain={name === 'position' ? ['auto', 'auto'] : [0, 'auto']} />
      <Tooltip content={<ChartTooltip name={name} current={showCurrent} previous={compare && showPrevious} />} cursor={{ stroke: 'var(--silver)', strokeDasharray: '3 3' }} />
      {compare && showPrevious && <Line name="Kỳ trước" type="monotone" dataKey="previous" stroke="var(--chart-previous)" strokeWidth={1.8} strokeDasharray="5 5" dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />}
      {showCurrent && <Line name="Kỳ hiện tại" type="monotone" dataKey="current" stroke="var(--chart-current)" strokeWidth={2.4} dot={false} activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }} isAnimationActive={false} />}
    </LineChart></ResponsiveContainer> : <div className="state-box"><p>Chọn một chuỗi dữ liệu ở trên để hiển thị biểu đồ.</p></div>}</div>
  </section>;
}
