import { Globe2 } from 'lucide-react';
import type { CountryRow } from '../../types/api';
import { decimal, metric, number } from '../../lib/format';
import { countryNames } from '../../lib/labels';

const flags: Record<string, string> = { VN: '🇻🇳', US: '🇺🇸', SG: '🇸🇬', TH: '🇹🇭', MY: '🇲🇾' };
export function CountryPerformance({ rows }: { rows: CountryRow[] }) {
  return <section className="card country-card"><div className="card-heading"><div><h2><Globe2 size={17} />Hiệu suất theo quốc gia</h2><p>Phân bố lượt nhấp tìm kiếm theo quốc gia.</p></div><span className="badge badge-neutral">5 quốc gia</span></div><div className="table-scroll"><table className="country-table"><thead><tr><th>Quốc gia</th><th>Lượt nhấp</th><th>Hiển thị</th><th>CTR</th><th>Tỷ trọng nhấp</th></tr></thead><tbody>{rows.map(row => <tr key={row.code}><td><span className="country-name"><span aria-hidden="true" className="flag">{flags[row.code]}</span>{countryNames[row.code] ?? row.name}</span></td><td className="emphasis">{number(row.metrics.clicks)}</td><td>{number(row.metrics.impressions)}</td><td>{metric(row.metrics.ctr, 'ctr')}</td><td><span className="share-cell"><span className="share-track"><span style={{ width: `${row.share}%` }} /></span><span>{decimal(row.share)}%</span></span></td></tr>)}</tbody></table></div><div className="country-footnote"><span className="status-dot" />Phân bố đầy đủ · tổng khớp với báo cáo đã chọn</div></section>;
}
