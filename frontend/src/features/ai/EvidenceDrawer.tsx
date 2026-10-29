import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Sheet } from "../../components/ui/sheet";
import { ErrorState } from "../../components/ui/states";
import { aiQuery } from "../../services/aiApi";
import type { AIEvidence, AIContext } from "../../types/ai";
import { DataView, stamp, textLabel } from "./shared";
export function EvidenceDrawer({
  id,
  project,
  onClose,
}: {
  id: string;
  project: string;
  onClose: () => void;
}) {
  const query = useQuery(
    aiQuery<AIEvidence>(
      `/evidence/${id}?project_id=${encodeURIComponent(project)}`,
      !!id,
    ),
  );
  const e = query.data;
  const safeReference =
    e?.source_reference &&
    [
      "/gsc-analytics?",
      "/technical-seo?",
      "/keyword-tracking?",
      "/keyword-research?",
      "/ai-workspace?",
      "/?",
    ].some((prefix) => e.source_reference!.startsWith(prefix))
      ? e.source_reference
      : null;
  return (
    <Sheet
      open={!!id}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Bằng chứng đã sử dụng"
      description="Tóm tắt có giới hạn tại thời điểm phân tích. Báo cáo gốc có thể đã thay đổi hoặc bị xóa; dữ liệu thu thập không phải suy luận AI."
    >
      {query.isError ? (
        <ErrorState
          message={query.error.message}
          onRetry={() => void query.refetch()}
        />
      ) : !e ? (
        <p role="status">Đang đọc bằng chứng…</p>
      ) : (
        <div className="ai-evidence-detail">
          <div className="ai-badges">
            <span className="badge badge-neutral">{e.source_type}</span>
            <span className="badge badge-neutral">
              {textLabel(e.data_freshness.status)}
            </span>
          </div>
          <dl className="ai-meta">
            <dt>Website</dt>
            <dd>{e.project_id}</dd>
            <dt>Phạm vi</dt>
            <dd>{e.metric_scope}</dd>
            <dt>Kỳ dữ liệu</dt>
            <dd>
              {e.date_start || "—"} → {e.date_end || "—"}
            </dd>
            <dt>Thu thập</dt>
            <dd>{stamp(e.collected_at)}</dd>
            <dt>Đọc vào</dt>
            <dd>{stamp(e.retrieved_at)}</dd>
            <dt>Độ phủ</dt>
            <dd>{e.completeness}</dd>
            <dt>Record gốc</dt>
            <dd>{e.source_record_id || "Chưa có"}</dd>
          </dl>
          {e.limitations.map((l, i) => (
            <p className="report-warning" key={i}>
              {l}
            </p>
          ))}
          {safeReference && (
            <Link className="button button-outline" to={safeReference}>
              Mở báo cáo gốc
            </Link>
          )}
          <h3>Dữ liệu từ dịch vụ ứng dụng</h3>
          <DataView data={e.value_summary} />
        </div>
      )}
    </Sheet>
  );
}
export function ContextDrawer({
  open,
  context,
  onClose,
}: {
  open: boolean;
  context?: AIContext;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
      title="Ngữ cảnh website"
      description="Hội thoại giữ website riêng. Tool chỉ đọc dữ liệu thuộc ngữ cảnh này; không tự crawl hoặc đồng bộ."
    >
      {context ? (
        <div className="ai-context-detail">
          <h3>{context.project.name}</h3>
          <p className="muted-copy">{context.project.site_url}</p>
          {context.sources.map((s) => (
            <article className="ai-source-card" key={s.id}>
              <div>
                <strong>{s.name}</strong>
                <span className="badge badge-neutral">
                  {textLabel(s.status)}
                </span>
              </div>
              {s.date_end && (
                <p>
                  {s.date_start} → {s.date_end}
                </p>
              )}
              {s.last_collected_at && (
                <p>Thu thập: {stamp(s.last_collected_at)}</p>
              )}
              <p>{s.limitations}</p>
            </article>
          ))}
          {context.keyword_sets.length > 0 && (
            <>
              <h3>Bộ Keyword Tracking ({context.keyword_set_count})</h3>
              {context.keyword_sets.map((s) => (
                <p key={s.id}>
                  {s.name} · bắt đầu {s.start_date} · {s.timezone}
                </p>
              ))}
            </>
          )}
          {context.limitations.map((l) => (
            <p className="report-warning" key={l}>
              {l}
            </p>
          ))}
        </div>
      ) : (
        <p>Chưa có ngữ cảnh website.</p>
      )}
    </Sheet>
  );
}
