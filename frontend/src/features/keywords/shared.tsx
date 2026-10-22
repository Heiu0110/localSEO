import type { Observation, RankPayload, Profile } from "../../types/keywords";
export const changeLabels: Record<string, string> = {
  improved: "Tăng",
  dropped: "Giảm",
  unchanged: "Không đổi",
  entered: "Vào phạm vi",
  lost: "Rời phạm vi",
  still_not_found: "Vẫn NA",
  new_observation: "Quan sát mới",
  awaiting: "Chờ kiểm tra",
  incomparable: "Khác chuỗi theo dõi",
};
export const metricLabels: Record<string, string> = {
  available: "Có dữ liệu",
  no_rows: "API không trả rows; có thể do privacy",
  not_synced: "Chưa đồng bộ kỳ này",
  not_connected: "Chưa kết nối GSC",
  target_missing: "Chưa có URL đích",
  api_error: "Lỗi API; thử đồng bộ lại",
};
export const num = (n: number | null | undefined, digits = 0) =>
  n == null
    ? "—"
    : n.toLocaleString("vi-VN", { maximumFractionDigits: digits });
export const rankText = (o: Observation | null | undefined) =>
  o?.rank_status === "FOUND"
    ? String(o.rank_value)
    : o?.rank_status === "NOT_FOUND"
      ? "NA"
      : "—";
export function shiftDate(day: string, offset: number) {
  const d = new Date(day + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + offset);
  return d.toISOString().slice(0, 10);
}
export function localToday(zone = "Asia/Ho_Chi_Minh") {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: zone }).format(
    new Date(),
  );
}
export function monday() {
  const today = localToday();
  return shiftDate(
    today,
    -((new Date(today + "T12:00:00Z").getUTCDay() + 6) % 7),
  );
}
export function rankError(value: string, depth: number) {
  const v = value.trim().toUpperCase();
  return v === "" ||
    v === "NA" ||
    (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= depth)
    ? ""
    : `Nhập số nguyên 1–${depth}, NA hoặc để trống.`;
}
export function makeRank(
  keyword: string,
  profile: Profile,
  week: number,
  value: string,
  weekOnly: boolean,
  checkedAt: string,
  notes = "",
): RankPayload {
  return {
    keyword_id: keyword,
    profile_id: profile.id,
    week_number: week,
    value: value.trim().toUpperCase(),
    timestamp_precision: weekOnly ? "week_only" : "exact",
    ...(checkedAt ? { checked_at: new Date(checkedAt).toISOString() } : {}),
    notes,
  };
}
export function Change({
  value,
}: {
  value: { state: string; value: number | null };
}) {
  return (
    <span
      className={`kw-change ${value.state}`}
      title="So với tuần liền trước, cùng Search Profile, URL và cách đo"
    >
      {value.value != null
        ? (value.value > 0 ? "↑ " : value.value < 0 ? "↓ " : "") +
          Math.abs(value.value) +
          " · "
        : ""}
      {changeLabels[value.state] || value.state}
    </span>
  );
}
