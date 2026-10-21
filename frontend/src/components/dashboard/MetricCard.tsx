import { ArrowDownRight, ArrowUpRight, CircleHelp, MousePointer2, Eye, Percent, ListOrdered } from 'lucide-react';
import type { MetricKey, Overview, PerformancePoint } from '../../types/api';
import { metric, signed } from '../../lib/format';
import { Tooltip } from '../ui/tooltip';

const config = {
  clicks: { label: 'Tổng lượt nhấp', icon: MousePointer2, info: 'Lượt nhấp tự nhiên từ Google Search trong dữ liệu mô phỏng. Clicks không phải Sessions của GA4.' },
  impressions: { label: 'Tổng lượt hiển thị', icon: Eye, info: 'Số lần kết quả xuất hiện trên Google Search, được mô phỏng. Không phải lượt hiển thị quảng cáo.' },
  ctr: { label: 'CTR trung bình', icon: Percent, info: 'Tổng lượt nhấp ÷ tổng lượt hiển thị × 100. Chênh lệch được tính bằng điểm phần trăm (đpt).' },
  position: { label: 'Vị trí trung bình', icon: ListOrdered, info: 'Vị trí trung bình có trọng số theo lượt hiển thị. Giá trị giảm thường là cải thiện; cơ cấu truy vấn cũng có thể ảnh hưởng.' },
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
  const delta = name === 'ctr' ? `${signed(change.delta, 2)} đpt` : name === 'position' ? `${signed(change.delta)} bậc` : change.percent === null ? 'Chưa có dữ liệu kỳ trước' : `${signed(change.percent)}%`;
  return <section className="card metric-card" aria-label={label}><div className="metric-top"><span className="metric-label"><Icon size={15} />{label}</span><Tooltip text={info}><button className="help-button" aria-label={`Giải thích: ${label}`}><CircleHelp size={14} /></button></Tooltip></div>
    <div className="metric-value-row"><strong className="metric-value" data-testid={`metric-${name}`}>{metric(overview.current[name], name)}</strong><Sparkline values={points.map(p => p.metrics[name])} positive={good} /></div>
    <div className="metric-bottom">{compare ? <><span className={`trend ${good ? 'positive' : 'negative'}`}><Direction size={14} />{delta}</span><span>so với kỳ trước</span></> : <span>Kỳ báo cáo đã chọn</span>}</div>
  </section>;
}
