import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { Sheet } from "../../components/ui/sheet";
import { Button } from "../../components/ui/button";
import { ErrorState } from "../../components/ui/states";
import { keywordQuery, keywordWrite } from "../../services/keywordApi";
import type {
  Keyword,
  KeywordSet,
  KeywordHistory,
  Profile,
} from "../../types/keywords";
import { KeywordForm, type Action } from "./KeywordForms";
import { num, metricLabels, rankText } from "./shared";
export function KeywordDetail({
  id,
  set,
  profile,
  metricsRow,
  reportPeriod,
  close,
  action,
  busy,
  error,
}: {
  id: string;
  set: KeywordSet;
  profile: Profile;
  metricsRow?: Keyword;
  reportPeriod: string;
  close: () => void;
  action: Action;
  busy: boolean;
  error: string;
}) {
  const [page, setPage] = useState(1);
  const sets = useQuery(
    keywordQuery<KeywordSet[]>(
      `/sets?site_id=${encodeURIComponent(set.site_id)}`,
    ),
  );
  const history = useQuery(
    keywordQuery<KeywordHistory>(
      `/keywords/${id}/history?profile_id=${profile.id}&page=${page}`,
      !!id,
    ),
  );
  const data = history.data;
  const reps = data?.representatives || [];
  const series = [...new Set(reps.map((o) => o.series_key))];
  const points = Array.from(
    { length: Math.max(35, ...reps.map((o) => o.week_number || 1)) },
    (_, i) => {
      const obs = reps.find((o) => o.week_number === i + 1);
      return {
        week: i + 1,
        observation: obs,
        ...Object.fromEntries(
          series.map((s) => [
            s,
            obs?.series_key === s && obs.rank_status === "FOUND"
              ? obs.rank_value
              : null,
          ]),
        ),
      };
    },
  );
  function checked(stamp: string | null) {
    return stamp
      ? new Date(stamp).toLocaleString("vi-VN", { timeZone: set.timezone })
      : "Chỉ biết tuần; không có giờ kiểm tra";
  }
  return (
    <Sheet
      open={!!id}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={data?.keyword.keyword_text || "Chi tiết từ khóa"}
      description="GSC và rank thủ công là hai phép đo độc lập. Lịch sử giữ nguyên snapshot URL, profile và phương pháp."
    >
      {history.isError ? (
        <ErrorState
          message={history.error.message}
          onRetry={() => void history.refetch()}
        />
      ) : !data ? (
        <p role="status">Đang tải lịch sử…</p>
      ) : (
        <>
          {error && (
            <p role="alert" className="action-error">
              {error}
            </p>
          )}
          <KeywordForm
            set={set}
            keyword={data.keyword}
            busy={busy}
            onSave={(body) =>
              void action(() => keywordWrite(`/keywords/${id}`, body, "PATCH"))
            }
            onDelete={() => {
              if (
                window.confirm(
                  "Xóa từ khóa này và toàn bộ lịch sử rank? Thao tác này không thể hoàn tác.",
                )
              )
                void action(async () => {
                  await keywordWrite(`/keywords/${id}/delete`, {
                    confirm: true,
                  });
                  close();
                });
            }}
          />
          <form
            className="kw-form"
            onSubmit={(e) => {
              e.preventDefault();
              const dest = String(
                new FormData(e.currentTarget).get("destination"),
              );
              if (
                window.confirm(
                  "Chuyển từ khóa và lịch sử sang bộ đã chọn? Cần cùng lịch, múi giờ; nhóm sẽ được bỏ để bạn chọn lại.",
                )
              )
                void action(async () => {
                  await keywordWrite(`/keywords/${id}/move`, {
                    keyword_set_id: dest,
                    confirm: true,
                  });
                  close();
                });
            }}
          >
            <label>
              Chuyển sang bộ cùng website
              <select name="destination" required>
                <option value="">Chọn bộ đích…</option>
                {sets.data
                  ?.filter((s) => s.id !== set.id)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </select>
            </label>
            <Button
              variant="outline"
              disabled={busy || !sets.data?.some((s) => s.id !== set.id)}
            >
              Chuyển từ khóa và lịch sử…
            </Button>
          </form>
          <p className="muted-copy">Kỳ báo cáo GSC: {reportPeriod}</p>
          <h3>
            GSC ·{" "}
            {metricsRow?.metrics.scope === "page"
              ? "Query theo URL đích"
              : "Query toàn property"}
          </h3>
          <p className="muted-copy">
            {metricLabels[metricsRow?.metrics.status || "not_synced"]} · Dữ
            liệu:{" "}
            {metricsRow?.metrics.fetched_at
              ? checked(
                  metricsRow.metrics.source_fetched_at ||
                    metricsRow.metrics.fetched_at,
                )
              : "chưa có cache cho kỳ đã chọn"}
          </p>
          <div className="detail-kpis">
            {(
              [
                ["Click", metricsRow?.metrics.clicks],
                ["Impression", metricsRow?.metrics.impressions],
                [
                  "CTR (%)",
                  metricsRow?.metrics.ctr == null
                    ? null
                    : metricsRow.metrics.ctr * 100,
                ],
                ["GSC Position", metricsRow?.metrics.average_position],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{num(value, 2)}</strong>
              </div>
            ))}
          </div>
          <p className="muted-copy">
            Nguồn: {metricsRow?.metrics.source || "chưa đồng bộ"}. Dữ liệu chi
            tiết có thể bị lọc vì privacy/row limits.
          </p>
          {metricsRow?.metrics.observed_pages?.map((p) => (
            <p className="kw-page-observed" key={p.url}>
              {p.url === data.keyword.target_url
                ? "✓ Trùng URL đích"
                : "URL GSC quan sát"}
              : {p.url} · {num(p.impressions)} impression
            </p>
          ))}
          <h3>Lịch sử rank · vị trí 1 ở phía trên</h3>
          {series.length > 1 && (
            <p className="report-warning">
              Có {series.length} chuỗi do URL, từ khóa hoặc Search Profile thay
              đổi. Các đường được tách riêng, không nối qua phép đo khác.
            </p>
          )}
          {reps.length ? (
            <div className="kw-chart" aria-label="Biểu đồ lịch sử rank">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points}>
                  <CartesianGrid
                    stroke="var(--chart-grid)"
                    strokeDasharray="3 3"
                  />
                  <XAxis dataKey="week" tickFormatter={(n) => `T${n}`} />
                  <YAxis
                    reversed
                    domain={[
                      1,
                      Math.max(
                        profile.config.search_depth,
                        ...reps.map((r) => r.rank_value || 1),
                      ),
                    ]}
                    width={38}
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      const obs = points.find(
                        (p) => p.week === Number(label),
                      )?.observation;
                      return active ? (
                        <div className="kw-tooltip">
                          {data.keyword.keyword_text} · Tuần {label}
                          <br />
                          {rankText(obs)} · {obs?.method || "Chưa kiểm tra"}
                          <br />
                          {checked(obs?.checked_at || null)}
                          <br />
                          {obs?.profile_snapshot.device} ·{" "}
                          {obs?.profile_snapshot.location_label}
                          <br />
                          {payload?.length ? "" : ""}
                        </div>
                      ) : null;
                    }}
                  />
                  {series.map((s, i) => (
                    <Line
                      key={s}
                      type="linear"
                      dataKey={s}
                      stroke={
                        [
                          "var(--chart-current)",
                          "var(--earth)",
                          "var(--silver)",
                        ][i % 3]
                      }
                      connectNulls={false}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="muted-copy">
              Chưa có lịch sử. Không có điểm rank giả.
            </p>
          )}
          <div className="kw-week-chips">
            {reps.map((o) => (
              <span
                key={o.id}
                title={`${o.match_mode} · ${checked(o.checked_at)}`}
              >
                T{o.week_number}: <strong>{rankText(o)}</strong>
              </span>
            ))}
          </div>
          <p className="muted-copy">
            NA là chú thích riêng, không vẽ thành 0 hoặc 101. Ô chưa kiểm tra
            tạo khoảng trống.
          </p>
          <h3>Tất cả lần ghi nhận ({num(data.total)})</h3>
          <div className="kw-observation-list">
            {data.rows.map((o) => (
              <article key={o.id}>
                <strong>
                  Tuần {o.week_number} · {rankText(o)}
                </strong>
                <span>
                  {checked(o.checked_at)} · {o.method}
                </span>
                <span>
                  {o.profile_snapshot.name} · {o.profile_snapshot.device} ·{" "}
                  {o.profile_snapshot.location_label} · top{" "}
                  {o.profile_snapshot.search_depth}
                </span>
                <span>
                  {o.match_mode} ·{" "}
                  {o.target_url_snapshot || set.settings.site_url}
                </span>
                {o.notes && <p>{o.notes}</p>}
              </article>
            ))}
          </div>
          <div className="technical-inline">
            <Button
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Trước
            </Button>
            <span>Trang {page}</span>
            <Button
              variant="outline"
              disabled={page * 50 >= data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Sau
            </Button>
          </div>
          <h3>Technical SEO đã lưu</h3>
          {data.technical.length ? (
            data.technical.map((t) => (
              <p key={t.url_id}>
                HTTP {t.status_code ?? "—"} · {t.indexability} ·{" "}
                {checked(t.audited_at)}{" "}
                <Link
                  to={`/technical-seo?project=${t.project_id}&audit=${t.audit_id}&tab=urls&url=${t.url_id}`}
                >
                  Mở URL Investigation
                </Link>
              </p>
            ))
          ) : (
            <p className="muted-copy">
              Chưa có bằng chứng audit phù hợp. Không thể kết luận URL không có
              lỗi.
            </p>
          )}
          {data.imported_metrics.length > 0 && (
            <>
              <h3>Metric bảng tính lịch sử · chưa xác minh GSC</h3>
              {data.imported_metrics.map((m, i) => (
                <p key={i}>
                  {m.filename} · {m.clicks} click · {m.impressions} impression ·
                  position {m.position}. Không dùng thay cache GSC hiện tại.
                </p>
              ))}
            </>
          )}
        </>
      )}
    </Sheet>
  );
}
