import type { DataSource } from '../types/api';

// API identifiers remain stable; presentation belongs to the Vietnamese interface.
export const countryNames: Record<string, string> = {
  VN: 'Việt Nam', US: 'Hoa Kỳ', SG: 'Singapore', TH: 'Thái Lan', MY: 'Malaysia',
};

export const sourceStatuses: Record<DataSource['status'], string> = {
  'Mock Mode': 'Dữ liệu mô phỏng',
  'Not Connected': 'Chưa kết nối',
  Planned: 'Dự kiến',
  'Not Configured': 'Chưa cấu hình',
};

export const sourceDetails: Record<string, { name: string; detail: string }> = {
  gsc: { name: 'Google Search Console', detail: 'Dữ liệu mô phỏng cố định · chưa kết nối Google' },
  ga4: { name: 'Google Analytics 4', detail: 'Sessions và tương tác · tích hợp trong tương lai' },
  technical: { name: 'Technical SEO', detail: 'Crawl và khả năng lập chỉ mục · phiên bản tương lai' },
  backlinks: { name: 'Nguồn Backlink', detail: 'Nhà cung cấp bên ngoài · tích hợp trong tương lai' },
  ai: { name: 'AI SEO Analyst', detail: 'Phân tích dựa trên dữ liệu · phiên bản tương lai' },
};
