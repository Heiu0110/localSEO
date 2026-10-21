import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Download, FileText, Search, SearchCheck, X } from 'lucide-react';
import type { DimensionRow, MetricKey } from '../../types/api';
import { metric, signed } from '../../lib/format';
import { Button } from '../ui/button';
import { EmptyState } from '../ui/states';
import { downloadPages } from '../../features/dashboard/utils/csv';

export function PerformanceTable({ kind, rows, compare, onSelect, filename }: { kind: 'pages' | 'queries'; rows: DimensionRow[]; compare: boolean; onSelect: (row: DimensionRow) => void; filename?: string }) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<MetricKey>('clicks');
  const [asc, setAsc] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(5);
  const [exported, setExported] = useState(false);
  const isPages = kind === 'pages';
  const filtered = useMemo(() => rows.filter(r => r.label.toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => (a.metrics[sort] - b.metrics[sort]) * (asc ? 1 : -1) || a.id.localeCompare(b.id)), [rows, search, sort, asc]);
  const pageCount = Math.ceil(filtered.length / pageSize);
  const currentPage = Math.min(page, Math.max(0, pageCount - 1));
  const visible = filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const setOrder = (key: MetricKey) => { setAsc(sort === key ? !asc : key === 'position'); setSort(key); setPage(0); };
  const Icon = isPages ? FileText : SearchCheck;
  return <section className="card table-card" aria-label={isPages ? 'Top pages' : 'Top queries'}>
    <div className="card-heading"><div><h2><Icon size={17} />{isPages ? 'Top performing pages' : 'Top search queries'}</h2><p>{isPages ? 'The pages bringing people to your website.' : 'What people search to discover your website.'}</p></div>{isPages && <Button variant="outline" size="sm" disabled={!filtered.length} title="Export all matching pages, in the current sort order" onClick={() => { downloadPages(filtered, filename!); setExported(true); }}><Download size={14} />Export CSV</Button>}</div>
    <div className="table-toolbar"><div className="search-input"><Search size={15} /><input aria-label={isPages ? 'Search URL' : 'Search queries'} placeholder={isPages ? 'Search page URL…' : 'Search queries…'} value={search} onChange={e => { setSearch(e.target.value); setPage(0); setExported(false); }} />{search && <button aria-label={`Clear ${kind} search`} onClick={() => { setSearch(''); setPage(0); }}><X size={14} /></button>}</div><span className="dataset-note">Complete mock dataset</span></div>
    <div className="table-scroll"><table><thead><tr><th scope="col">{isPages ? 'Page URL' : 'Search query'}</th>{(['clicks', 'impressions', 'ctr', 'position'] as MetricKey[]).map(key => <th key={key} scope="col" aria-sort={sort === key ? asc ? 'ascending' : 'descending' : 'none'}><button onClick={() => setOrder(key)} aria-label={`Sort ${kind} by ${key}`}>{key === 'ctr' ? 'CTR' : key === 'impressions' ? 'Impr.' : key[0].toUpperCase() + key.slice(1)}{sort === key ? asc ? <ArrowUp size={12} /> : <ArrowDown size={12} /> : <ArrowUpDown size={12} />}</button></th>)}{compare && <th scope="col" title="Click change vs. the previous equal-length period">Change</th>}</tr></thead>
      <tbody>{visible.map(row => <tr key={row.id}><td><button className="table-link" title={row.label} onClick={() => onSelect(row)}>{isPages ? new URL(row.label).pathname : row.label}</button></td>{(['clicks', 'impressions', 'ctr', 'position'] as MetricKey[]).map(key => <td key={key} className={key === 'clicks' ? 'emphasis' : ''}>{metric(row.metrics[key], key)}</td>)}{compare && <td><span className={`change-chip ${(row.click_change_pct ?? 0) >= 0 ? 'positive' : 'negative'}`}>{row.click_change_pct === null ? '—' : `${signed(row.click_change_pct)}%`}</span></td>}</tr>)}</tbody>
    </table></div>{!filtered.length && <EmptyState />}
    <div className="table-footer"><span>{filtered.length ? `${currentPage * pageSize + 1}–${Math.min((currentPage + 1) * pageSize, filtered.length)} of ${filtered.length}` : '0 results'}<span className="sr-only" role="status">{exported ? ' CSV exported.' : ''}</span></span><div><label className="rows-label">Rows <select aria-label={`Rows per ${kind} page`} value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(0); }}>{[5, 10, 20].map(n => <option key={n} value={n}>{n}</option>)}</select></label><Button variant="ghost" size="icon" aria-label={`Previous ${kind} page`} disabled={currentPage === 0} onClick={() => setPage(p => p - 1)}><ChevronLeft size={15} /></Button><span>{pageCount ? currentPage + 1 : 0} / {pageCount}</span><Button variant="ghost" size="icon" aria-label={`Next ${kind} page`} disabled={currentPage + 1 >= pageCount} onClick={() => setPage(p => p + 1)}><ChevronRight size={15} /></Button></div></div>
  </section>;
}
