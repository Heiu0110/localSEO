import { useState } from "react";
import { Button } from "../../components/ui/button";
import type { AIMessage, AIRecommendation } from "../../types/ai";
import { EvidenceButtons, textLabel, stamp } from "./shared";
const reviewStatuses = [
  "proposed",
  "under_review",
  "approved",
  "rejected",
  "needs_more_evidence",
];
export function RecommendationCard({
  row,
  onSave,
  busy,
  onEvidence,
  message,
}: {
  row: AIRecommendation;
  onSave: (id: string, status: string, notes: string) => void;
  busy: boolean;
  onEvidence: (id: string) => void;
  message: AIMessage;
}) {
  const [status, setStatus] = useState(row.approval_status);
  const [notes, setNotes] = useState(row.user_notes);
  return (
    <article className="ai-recommendation" data-recommendation={row.id}>
      <div className="ai-recommendation-heading">
        <h4>{row.title}</h4>
        <span className="badge badge-neutral">
          Ưu tiên {textLabel(row.priority)}
        </span>
      </div>
      <p>{row.proposed_action}</p>
      <small>
        Mức tin cậy: {textLabel(row.confidence)} ·{" "}
        {textLabel(row.approval_status)}
      </small>
      <EvidenceButtons
        ids={row.evidence_ids}
        evidence={message.evidence}
        onOpen={onEvidence}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(row.id, status, notes);
        }}
      >
        <label>
          Trạng thái review
          <select
            aria-label={`Review ${row.title}`}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {reviewStatuses.map((s) => (
              <option key={s} value={s}>
                {textLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ghi chú review
          <textarea
            aria-label={`Ghi chú ${row.title}`}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={2000}
          />
        </label>
        <Button type="submit" variant="outline" size="sm" disabled={busy}>
          Lưu review
        </Button>
      </form>
      <p className="muted-copy">
        Duyệt chỉ lưu trạng thái. Không sửa website, tạo backlog Technical SEO
        hay thực thi bên ngoài.
      </p>
    </article>
  );
}
export function AgentMessage({
  message,
  onEvidence,
  onReview,
  busy,
}: {
  message: AIMessage;
  onEvidence: (id: string) => void;
  onReview: (id: string, status: string, notes: string) => void;
  busy: boolean;
}) {
  if (message.role === "user")
    return (
      <article className="ai-user-message">
        <span>Bạn · {stamp(message.created_at)}</span>
        <p>{message.content}</p>
      </article>
    );
  const analysis = message.data.analysis;
  const running = ["queued", "running"].includes(message.status);
  return (
    <article className="ai-answer" data-ai-message={message.id}>
      <div className="ai-answer-heading">
        <strong>
          {message.data.provider !== "local_report"
            ? (message.data.provider === "chatgpt"
                ? "ChatGPT Plan Usage · "
                : "OpenAI · ") + message.data.model
            : "Báo cáo theo quy tắc · không gọi AI"}
        </strong>
        <span className="badge badge-neutral">{textLabel(message.status)}</span>
      </div>
      <p className="ai-period">
        Kỳ GSC ưu tiên: {message.data.window.days} ngày ·{" "}
        {message.data.window.end_date || "đến ngày dữ liệu đã lưu gần nhất"}
      </p>
      {running && (
        <p role="status" className="ai-processing">
          {message.data.provider === "chatgpt"
            ? `Đang nhận stream ChatGPT · ${message.data.streaming_characters_received || 0} ký tự. Chỉ hiển thị phân tích sau response.completed và kiểm tra bằng chứng.`
            : "Đang đọc nguồn và phân tích…"}
        </p>
      )}
      {message.data.error && (
        <p role="alert" className="report-warning action-error">
          {message.data.error}
        </p>
      )}
      {message.metrics.map((m, i) => (
        <div className="ai-grounded-metrics" key={i}>
          <p>
            Số liệu do backend trả · {m.source_type} · {m.period.start} →{" "}
            {m.period.end}
          </p>
          <div>
            {[
              ["clicks", "Clicks"],
              ["impressions", "Impressions"],
              ["ctr", "CTR (%)"],
              ["position", "GSC Position"],
            ].map(([key, label]) => (
              <section key={key}>
                <span>{label}</span>
                <strong>
                  {m.metrics[key] == null
                    ? "—"
                    : m.metrics[key].toLocaleString("vi-VN", {
                        maximumFractionDigits: 2,
                      })}
                </strong>
              </section>
            ))}
          </div>
          <EvidenceButtons
            ids={[m.evidence_id]}
            evidence={message.evidence}
            onOpen={onEvidence}
          />
        </div>
      ))}
      {analysis && (
        <>
          <p className="ai-summary">{analysis.summary}</p>
          {message.data.provider !== "local_report" && (
            <p className="ai-inference-note">
              Diễn giải AI cần được kiểm tra với nguồn; citation hợp lệ không tự
              chứng minh kết luận đúng.
            </p>
          )}
          {analysis.findings.map((f, i) => (
            <section key={i} className="ai-finding">
              <div>
                <h3>{f.title}</h3>
                <span>
                  {f.kind === "hypothesis" ? "Giả thuyết" : "Diễn giải"} · tin
                  cậy {textLabel(f.confidence)}
                </span>
              </div>
              <p>{f.interpretation}</p>
              <EvidenceButtons
                ids={f.evidence_ids}
                evidence={message.evidence}
                onOpen={onEvidence}
              />
            </section>
          ))}
          {message.recommendations.length > 0 && (
            <h3>Đề xuất để bạn rà soát</h3>
          )}
          {message.recommendations.map((r) => (
            <RecommendationCard
              key={r.id + r.approval_status + r.user_notes}
              row={r}
              onSave={onReview}
              busy={busy}
              onEvidence={onEvidence}
              message={message}
            />
          ))}
          <details className="ai-limitations">
            <summary>
              Giới hạn và dữ liệu còn thiếu ({analysis.limitations.length})
            </summary>
            <ul>
              {analysis.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </details>
          <div className="ai-next-step">
            <strong>Bước tiếp theo</strong>
            <p>{analysis.next_step}</p>
          </div>
        </>
      )}
      {message.tools.length > 0 && (
        <details className="ai-tools">
          <summary>Đã dùng {message.tools.length} tool chỉ đọc</summary>
          {message.tools.map((t) => (
            <div key={t.id}>
              <code>{t.tool_name}</code>
              <span>
                {textLabel(t.status)} · {t.duration_ms} ms
              </span>
              {t.status === "failed" && (
                <p>
                  {String(t.output_summary.detail || "Không đọc được nguồn.")}
                </p>
              )}
            </div>
          ))}
        </details>
      )}
      {message.evidence.length > 0 && (
        <details className="ai-tools">
          <summary>Tất cả bằng chứng ({message.evidence.length})</summary>
          <EvidenceButtons
            ids={message.evidence.map((e) => e.evidence_id)}
            evidence={message.evidence}
            onOpen={onEvidence}
          />
        </details>
      )}
    </article>
  );
}
