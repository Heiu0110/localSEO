import type { ResearchKeyword } from "../../types/research";
export const statuses: Record<string, string> = {
  draft: "Bản nháp",
  needs_review: "Cần rà soát",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  archived: "Lưu trữ",
};
export const intents: Record<string, string> = {
  unknown: "Chưa rõ",
  informational: "Thông tin",
  commercial: "Thương mại",
  transactional: "Giao dịch",
  navigational: "Điều hướng",
  local: "Địa phương",
  mixed: "Hỗn hợp",
};
export const mappings: Record<string, string> = {
  undecided: "Chưa quyết định",
  suggested: "URL đề xuất",
  approved: "URL đã duyệt",
  planned: "URL dự kiến mới",
};
export const kinds: Record<string, string> = {
  high_impressions_low_ctr: "Impressions cao · cần kiểm tra CTR",
  near_top_average_position: "GSC Average Position gần Top",
  visibility_without_mapping: "Có hiển thị · chưa duyệt mapping",
  candidate_content_gap: "Ứng viên thiếu URL đích",
  declining_manual_rank: "Rank MANUAL giảm",
};
export const number = (n: number | null | undefined) =>
  n == null
    ? "Chưa có"
    : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);
export function Options({ values }: { values: Record<string, string> }) {
  return Object.entries(values).map(([v, t]) => (
    <option key={v} value={v}>
      {t}
    </option>
  ));
}
export function metric(k: ResearchKeyword, type: string) {
  const src = k.sources.find((s) =>
    s.metrics.some((m) => m.metric_type === type),
  );
  const m = src?.metrics.find((m) => m.metric_type === type);
  return m ? `${number(m.value)} ${m.unit} · ${src?.provider}` : "Chưa có";
}
