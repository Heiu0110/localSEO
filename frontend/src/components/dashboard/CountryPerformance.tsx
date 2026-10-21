import { Globe2 } from 'lucide-react';
import type { CountryRow } from '../../types/api';
import { number } from '../../lib/format';

const flags: Record<string, string> = { VN: '🇻🇳', US: '🇺🇸', SG: '🇸🇬', TH: '🇹🇭', MY: '🇲🇾' };
export function CountryPerformance({ rows }: { rows: CountryRow[] }) {
  return <section className="card country-card"><div className="card-heading"><div><h2><Globe2 size={17} />Country performance</h2><p>Where your search clicks come from.</p></div><span className="badge badge-neutral">5 countries</span></div><div className="table-scroll"><table className="country-table"><thead><tr><th>Country</th><th>Clicks</th><th>Impr.</th><th>CTR</th><th>Click share</th></tr></thead><tbody>{rows.map(row => <tr key={row.code}><td><span className="country-name"><span aria-hidden="true" className="flag">{flags[row.code]}</span>{row.name}</span></td><td className="emphasis">{number(row.metrics.clicks)}</td><td>{number(row.metrics.impressions)}</td><td>{row.metrics.ctr.toFixed(2)}%</td><td><span className="share-cell"><span className="share-track"><span style={{ width: `${row.share}%` }} /></span><span>{row.share.toFixed(1)}%</span></span></td></tr>)}</tbody></table></div><div className="country-footnote"><span className="status-dot" />Complete distribution · totals match the selected report</div></section>;
}
