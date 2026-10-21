import type { MetricKey } from '../types/api';

export const number = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
export const decimal = (value: number, digits = 1) => new Intl.NumberFormat('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
export const compact = (value: number) => new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export function metric(value: number, key: MetricKey): string {
  if (key === 'ctr') return `${decimal(value, 2)}%`;
  if (key === 'position') return decimal(value);
  return number(value);
}
export function date(value: string, short = false) {
  // API dates are ISO calendar dates, with no timezone conversion required.
  const [year, month, day] = value.split('-');
  return short ? `${day}/${month}` : `${day}/${month}/${year}`;
}
export const signed = (n: number, digits = 1) => `${n > 0 ? '+' : ''}${decimal(n, digits)}`;
export const metricNames: Record<MetricKey, string> = { clicks: 'Lượt nhấp', impressions: 'Lượt hiển thị', ctr: 'CTR', position: 'Vị trí TB' };
