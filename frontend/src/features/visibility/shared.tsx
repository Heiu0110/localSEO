import type { ReactNode } from "react";
import type { Rate, VisibilityMention } from "../../types/visibility";
export const labels: Record<string, string> = {
  neutral: "Khám phá trung lập",
  commercial_discovery: "Khám phá thương mại",
  brand_specific: "Có brand trong prompt",
  CONFIRMED_MATCH: "Mention xác nhận",
  POSSIBLE_MATCH: "Có thể khớp · cần review",
  NEEDS_REVIEW: "Cần review",
  REJECTED_MATCH: "Đã loại",
  CONFIRMED_ATTRIBUTION: "Citation được nguồn khai báo",
  OWNED_BRAND: "Nguồn brand",
  COMPETITOR: "Nguồn đối thủ",
  THIRD_PARTY: "Nguồn ngoài",
  AMBIGUOUS: "Ownership mơ hồ",
  UNKNOWN: "Chưa rõ",
  capable: "Có hỗ trợ citation",
  not_supported: "Không hỗ trợ citation",
  unknown: "Chưa rõ",
  complete: "Đầy đủ",
  partial: "Một phần",
  missing: "Thiếu metadata",
  invalid: "Không hợp lệ",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  proposed: "Đề xuất",
  under_review: "Đang review",
  needs_more_evidence: "Cần thêm bằng chứng",
  investigation: "Điều tra",
  active: "Đang dùng",
  draft: "Bản nháp",
  archived: "Lưu trữ",
  MANUAL_ENTRY: "Nhập thủ công",
  IMPORTED_RESPONSE: "Phản hồi nhập",
  PROVIDER_API: "Nguồn khai báo API",
  THIRD_PARTY_REPORT: "Báo cáo bên thứ ba",
  provider_annotation: "Annotation của provider",
  grounding_metadata: "Grounding metadata",
  user_supplied: "Citation do người dùng khai báo",
  third_party_report: "Citation từ báo cáo ngoài",
};
export const categories = [
  "Brand Discovery",
  "Supplier Discovery",
  "Product Research",
  "Service Comparison",
  "Pricing & Costs",
  "Technical Education",
  "Local Recommendations",
  "Alternatives",
  "Purchase Decision",
  "Brand-Specific",
];
export const stamp = (v: string | null) =>
  v ? new Date(v).toLocaleString("vi-VN") : "Unknown";
export function RateValue({ value }: { value: Rate }) {
  return (
    <>
      <strong>
        {value.percent === null
          ? "Unknown"
          : `${value.percent.toLocaleString("vi-VN")}%`}
      </strong>
      <small>
        {value.numerator} / {value.denominator} quan sát đủ điều kiện
      </small>
    </>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label>
      {label}
      {children}
    </label>
  );
}
export const text = (f: FormData, key: string) => String(f.get(key) ?? "");
export const lines = (f: FormData, key: string) =>
  text(f, key)
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
export function Highlighted({
  text: response,
  mentions,
}: {
  text: string;
  mentions: VisibilityMention[];
}) {
  const chars = Array.from(response),
    result: ReactNode[] = [];
  let pos = 0;
  for (const m of [...mentions].sort(
    (a, b) => a.start - b.start || b.end - a.end,
  )) {
    if (m.start < pos || m.end > chars.length) continue;
    result.push(chars.slice(pos, m.start).join(""));
    result.push(
      <mark key={m.id} title={`${m.alias}: ${labels[m.status] || m.status}`}>
        {chars.slice(m.start, m.end).join("")}
      </mark>,
    );
    pos = m.end;
  }
  result.push(chars.slice(pos).join(""));
  return <pre className="visibility-response">{result}</pre>;
}
