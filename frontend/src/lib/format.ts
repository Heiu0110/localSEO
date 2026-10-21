import type { MetricKey } from '../types/api';

export const number = (value: number) => new Intl.NumberFormat('en-US').format(value);
export const compact = (value: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export function metric(value: number, key: MetricKey): string {
  if (key === 'ctr') return `${value.toFixed(2)}%`;
  if (key === 'position') return value.toFixed(1);
  return number(value);
}
export function date(value: string, short = false) {
  return new Date(value + 'T00:00:00Z').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', ...(short ? {} : { year: 'numeric' }), timeZone: 'UTC',
  });
}
export const signed = (n: number, digits = 1) => `${n > 0 ? '+' : ''}${n.toFixed(digits)}`;
export const metricNames: Record<MetricKey, string> = { clicks: 'Clicks', impressions: 'Impressions', ctr: 'CTR', position: 'Position' };
