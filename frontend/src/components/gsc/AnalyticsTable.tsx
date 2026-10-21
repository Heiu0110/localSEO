import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Search } from 'lucide-react';
import { gscRowsQuery, downloadReport } from '../../services/gscApi';
import type { AnalyticsFilters } from '../../types/gsc';
import type { DimensionRow, MetricKey } from '../../types/api';
import { decimal, metric, metricNames, signed } from '../../lib/format';
import { countryName } from '../../lib/labels';
import { Button } from '../ui/button';
import { EmptyState, ErrorState } from '../ui/states';

export const tabLabels = { overview: 'Tổng quan', pages: 'URL', queries: 'Truy vấn', countries: 'Quốc gia', devices: 'Thiết bị' };
const devices: Record<string, string> = { MOBILE: 'Di động', DESKTOP: 'Máy tính', TABLET: 'Máy tính bảng' };

export function AnalyticsTable({ dataset, filters, compare, onPage, compact = false }: { dataset: 'pages' | 'queries' | 'countries' | 'devices'; filters: AnalyticsFilters; compare: boolean; onPage?: (row: DimensionRow) => void; compact?: boolean }) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(compact ? 10 : 25);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('clicks');
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');
  const [exportError, setExportError] = useState('');
  const [exporting, setExporting] = useState(false);
  const query = useQuery(gscRowsQuery(dataset, filters, { page: String(page), page_size: String(size), search, sort, direction }));
  const label = tabLabels[dataset];
  function order(key: string) { setDirection(sort === key && direction === 'desc' ? 'asc' : key === 'position' ? 'asc' : 'desc'); setSort(key); setPage(1); }
  async function exportRows() {
    setExporting(true); setExportError('');
    try { await downloadReport(dataset, filters, { search, sort, direction }); }
    catch (error) { setExportError(error instanceof Error ? error.message : 'Không thể xuất CSV.'); }
    finally { setExporting(false); }
  }
  const numeric: { key: string; label: string }[] = ([...(['clicks','impressions','ctr','position'] as MetricKey[])].map(key => ({ key, label: metricNames[key] })));
  if (compare) numeric.push({ key: 'click_change_pct', label: 'Δ nhấp' }, ...(dataset === 'pages' ? [{ key: 'impression_change_pct', label: 'Δ hiển thị' }] : []));
  const share = dataset === 'countries' || dataset === 'devices';
  return <section className="card analytics-table" aria-label={`Phân tích ${label}`}><div className="card-heading"><div><h2>{compact ? 'Top 10 ' : ''}{label}</h2><p>{dataset === 'pages' ? 'Phạm vi byPage · không cộng vào KPI property' : 'Phạm vi byProperty · dòng trả về có thể bị giới hạn'}</p></div><Button variant="outline" size="sm" disabled={exporting || !query.data?.total_rows} onClick={() => void exportRows()}><Download size={14} />{exporting ? 'Đang xuất…' : `Xuất ${label} CSV`}</Button></div>
    <div className="table-toolbar"><div className="search-input"><Search size={14} /><input aria-label={`Tìm ${label} GSC`} value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder={dataset === 'countries' ? 'Tìm mã quốc gia (vnm, usa)…' : `Tìm ${label.toLocaleLowerCase('vi-VN')}…`} /></div><span className="dataset-note">Dữ liệu đã lưu · có thể chưa đầy đủ</span></div>
    {query.isPending ? <div className="skeleton skeleton-chart" aria-label={`Đang tải ${label}`} /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <><div className="table-scroll"><table><thead><tr><th>{label}</th>{numeric.map(column => <th key={column.key} aria-sort={sort === column.key ? direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button aria-label={`Sắp xếp ${label} GSC theo ${column.label}`} onClick={() => order(column.key)}>{column.label}{sort === column.key && (direction === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}</button></th>)}{share && <th title="Tỷ trọng lượt nhấp trong các dòng đã lưu của dimension này">Tỷ trọng</th>}</tr></thead><tbody>{query.data.rows.map(row => <tr key={row.id}><td>{dataset === 'pages' ? <button className="table-link" title={row.label} onClick={() => onPage?.(row)}>{row.label}</button> : <span title={row.label} className="dimension-label">{dataset === 'countries' ? countryName(row.code ?? '', row.label) : dataset === 'devices' ? devices[row.label] ?? row.label : row.label}</span>}</td>{numeric.map(column => <td key={column.key}>{column.key === 'click_change_pct' ? row.click_change_pct === null ? '—' : `${signed(row.click_change_pct)}%` : column.key === 'impression_change_pct' ? row.impression_change_pct == null ? '—' : `${signed(row.impression_change_pct)}%` : row.current_available === false ? '—' : metric(row.metrics[column.key as MetricKey], column.key as MetricKey)}</td>)}{share && <td><span className="share-cell"><span className="share-track"><span style={{ width: `${row.share ?? 0}%` }} /></span>{decimal(row.share ?? 0)}%</span></td>}</tr>)}</tbody></table></div>{!query.data.rows.length && <EmptyState title="Chưa có dòng dữ liệu phù hợp" detail="Kiểm tra bộ lọc và độ phủ đồng bộ. Không có bản ghi không đồng nghĩa traffic bằng 0." />}<div className="table-footer"><span>{query.data.total_rows ?? 0} dòng đã lưu</span><div><label className="rows-label">Dòng<select aria-label={`Số dòng ${label} GSC`} value={size} onChange={e => { setSize(Number(e.target.value)); setPage(1); }}>{[10,25,50,100].map(n => <option key={n}>{n}</option>)}</select></label><Button variant="ghost" size="icon" aria-label={`Trang trước ${label} GSC`} disabled={page <= 1} onClick={() => setPage(p => p-1)}><ChevronLeft size={15} /></Button><span>{page} / {Math.max(1,Math.ceil((query.data.total_rows ?? 0)/size))}</span><Button variant="ghost" size="icon" aria-label={`Trang sau ${label} GSC`} disabled={page*size >= (query.data.total_rows ?? 0)} onClick={() => setPage(p => p+1)}><ChevronRight size={15} /></Button></div></div><p className="table-coverage-note">{query.data.completeness === 'api_limited' ? 'Đã chạm ngưỡng API 50.000 dòng/ngày/search type; dữ liệu chi tiết không đầy đủ. ' : query.data.completeness === 'unknown' ? 'Một số ngày chưa đồng bộ. ' : 'Đã kết thúc truy xuất API; không đảm bảo Google cung cấp mọi dòng. '}{query.data.warning}{share && ' Tỷ trọng tính trên dòng đã lưu của bảng này.'} “—” là chưa có bản ghi/kỳ đối chiếu phù hợp, không suy diễn giảm 100%.</p></>}
    {exportError && <p className="action-error" role="alert">{exportError}</p>}
  </section>;
}
