import type { DimensionRow } from '../../../types/api';

// Escape formula-like labels as well as RFC 4180 quoting. UTF-8 BOM supports Excel.
export function pagesCsv(rows: DimensionRow[]): string {
  const cell = (value: string | number) => {
    const raw = String(value);
    const safe = typeof value === 'string' && /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  return '\uFEFF' + [['Page', 'Clicks', 'Impressions', 'CTR (%)', 'Position', 'Click change (%)'], ...rows.map(r => [r.label, r.metrics.clicks, r.metrics.impressions, Number(r.metrics.ctr.toFixed(4)), Number(r.metrics.position.toFixed(4)), r.click_change_pct === null ? '' : Number(r.click_change_pct.toFixed(4))])].map(row => row.map(cell).join(',')).join('\r\n');
}
export function downloadPages(rows: DimensionRow[], filename: string) {
  const url = URL.createObjectURL(new Blob([pagesCsv(rows)], { type: 'text/csv;charset=utf-8;' }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
