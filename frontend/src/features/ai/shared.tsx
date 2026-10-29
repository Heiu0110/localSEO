import type { AIEvidence } from "../../types/ai";
export const labels: Record<string, string> = {
  inactive: "Property đã tắt",
  available: "Có dữ liệu",
  demo: "Mô phỏng",
  fixture: "Thử nghiệm",
  not_synced: "Chưa đồng bộ",
  not_connected: "Chưa kết nối",
  not_audited: "Chưa có audit",
  not_configured: "Chưa cấu hình",
  not_implemented: "Chưa triển khai",
  recent: "Gần đây",
  stale: "Dữ liệu cũ",
  unknown: "Chưa rõ",
  queued: "Đang chờ",
  running: "Đang xử lý",
  completed: "Hoàn tất",
  failed: "Lỗi",
  proposed: "Đề xuất mới",
  under_review: "Đang rà soát",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  needs_more_evidence: "Cần thêm bằng chứng",
  high: "Cao",
  medium: "Trung bình",
  low: "Thấp",
  reserved: "Đang dự phòng",
};
export const textLabel = (value: string) => labels[value] || value;
export const money = (n: number | null | undefined) =>
  n == null
    ? "Chưa xác định"
    : new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 5,
      }).format(n);
export const stamp = (n: string | null | undefined) =>
  n
    ? new Date(n).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
    : "Chưa có thời điểm thu thập";
export function EvidenceButtons({
  ids,
  evidence,
  onOpen,
}: {
  ids: string[];
  evidence: AIEvidence[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="ai-evidence-buttons">
      {ids.map((id) => {
        const e = evidence.find((e) => e.evidence_id === id);
        return (
          <button
            key={id}
            type="button"
            onClick={() => onOpen(id)}
            aria-label={`Mở bằng chứng ${e?.source_name || id}`}
          >
            {e?.source_name || "Bằng chứng"} · {id.slice(0, 6)}
          </button>
        );
      })}
    </div>
  );
}
export function DataView({ data }: { data: unknown }) {
  if (data === null || data === undefined)
    return <span className="muted-copy">Chưa có dữ liệu; không phải 0</span>;
  if (Array.isArray(data)) {
    if (!data.length)
      return <p className="muted-copy">Không có bản ghi được trả về.</p>;
    const rows = data.filter(
      (x) => x && typeof x === "object" && !Array.isArray(x),
    ) as Record<string, unknown>[];
    if (rows.length === data.length) {
      const columns = [...new Set(rows.flatMap(Object.keys))].slice(0, 8);
      return (
        <div className="ai-data-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c}>
                      {r[c] === null || r[c] === undefined ? (
                        "—"
                      ) : typeof r[c] === "object" ? (
                        <details>
                          <summary>Chi tiết</summary>
                          <pre>{JSON.stringify(r[c], null, 2)}</pre>
                        </details>
                      ) : (
                        String(r[c])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return (
      <ul>
        {data.map((x, i) => (
          <li key={i}>
            <DataView data={x} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof data === "object")
    return (
      <dl className="ai-data-fields">
        {Object.entries(data).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>
              <DataView data={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span>{String(data)}</span>;
}
