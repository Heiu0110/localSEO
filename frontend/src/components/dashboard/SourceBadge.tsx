import type { SourceType } from '../../types/api';

export function SourceBadge({ source = 'mock' }: { source?: SourceType }) {
  return <span className={`badge ${source === 'gsc' ? 'badge-neutral' : 'badge-mock'}`}>{source === 'gsc' ? 'Google Search Console · SQLite' : source === 'fixture' ? 'Thử nghiệm SQLite' : 'Dữ liệu mô phỏng'}</span>;
}
export function sourceLabel(source?: SourceType) {
  return source === 'gsc' ? 'GSC' : source === 'fixture' ? 'THỬ NGHIỆM SQLITE' : 'DEMO';
}
