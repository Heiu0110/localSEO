import { LiveObservationEvidence } from "./LiveObservationEvidence";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Sheet } from "../../components/ui/sheet";
import { Button } from "../../components/ui/button";
import { visibilityQuery, visibilityWrite } from "../../services/visibilityApi";
import { aiWrite } from "../../services/aiApi";
import type {
  VisibilityObservation,
  VisibilityEntity,
  GEOOpportunity,
  VisibilityProject,
  VisibilityEvidence,
} from "../../types/visibility";
import { DataView } from "../ai/shared";
import { Field, Highlighted, labels, stamp, text } from "./shared";
type Run = (fn: () => Promise<void>) => Promise<void>;
function Evidence({
  row,
  openObservation,
}: {
  row: VisibilityEvidence;
  openObservation: (id: string) => void;
}) {
  const value = row.data.value;
  const oid =
    row.source_type === "observation"
      ? row.source_id
      : typeof value.observation_id === "string"
        ? value.observation_id
        : null;
  return (
    <details className="visibility-evidence">
      <summary>
        {row.source_type} · {row.id.slice(0, 8)}
      </summary>
      {oid && (
        <Button variant="outline" onClick={() => openObservation(oid)}>
          Mở quan sát gốc
        </Button>
      )}
      {row.data.source_reference?.startsWith("/") &&
        !row.data.source_reference.startsWith("//") && (
          <Link className="visibility-link" to={row.data.source_reference}>
            Mở module nguồn
          </Link>
        )}
      <DataView data={value} />
    </details>
  );
}
export function ObservationDrawer({
  id,
  project,
  entities,
  close,
  run,
  onCorrect,
}: {
  id: string;
  project: string;
  entities: VisibilityEntity[];
  close: () => void;
  run: Run;
  onCorrect: (row: VisibilityObservation) => void;
}) {
  const query = useQuery(
    visibilityQuery<VisibilityObservation>(
      `/observations/${id}?project_id=${project}`,
      !!id,
    ),
  );
  const row = query.data;
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const name = (eid: string) => entities.find((e) => e.id === eid)?.name || eid;
  return (
    <Sheet
      open={!!id}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title="Quan sát AI · bằng chứng gốc"
      description="Văn bản gốc được giữ nguyên. Match/citation/review có provenance riêng; không có live fetch."
    >
      {query.isPending && <p role="status">Đang đọc quan sát…</p>}
      {query.isError && <p role="alert">{query.error.message}</p>}
      {error && <p role="alert">{error}</p>}
      {row && (
        <>
          <h3>Prompt</h3>
          <p>{row.prompt_snapshot}</p>
          <dl className="visibility-meta">
            <dt>Provider / model</dt>
            <dd>
              {row.provider} / {row.model || "Unknown"}
            </dd>
            <dt>Thu thập</dt>
            <dd>
              {labels[row.collection_method]} · {stamp(row.observed_at)}
            </dd>
            <dt>Locale / grounding</dt>
            <dd>
              {row.original.country || "Unknown"} /{" "}
              {row.original.language || "Unknown"} /{" "}
              {row.original.location || "Unknown"} · {row.original.grounding}
            </dd>
            <dt>Cohort</dt>
            <dd>
              {labels[row.original.prompt_context.cohort_type] ||
                row.original.prompt_context.cohort_type}
            </dd>
            <dt>Độ đầy đủ</dt>
            <dd>{labels[row.completeness]}</dd>
            <dt>Citation</dt>
            <dd>
              {labels[row.citation_capability]} · metadata{" "}
              {labels[row.citation_metadata]}
            </dd>
            <dt>Nhận diện</dt>
            <dd>Revision {row.extraction.revision}</dd>
          </dl>
          <h3>Toàn bộ phản hồi gốc</h3>
          <Highlighted text={row.response_text} mentions={row.mentions} />
          <h3>Mentions và review</h3>
          {!row.mentions.length && (
            <p>
              Không phát hiện tên/alias đã cấu hình; không suy ra
              recommendation.
            </p>
          )}
          {row.mentions.map((m) => (
            <section className="visibility-source" key={m.id}>
              <strong>
                {name(m.entity_id)} · “{m.matched_text}”
              </strong>
              <p>
                {labels[m.status]} · vị trí {m.start}–{m.end}
              </p>
              <p>{m.reason}</p>
              <form
                className="visibility-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  void run(async () => {
                    await visibilityWrite(
                      `/mentions/${m.id}/review?project_id=${project}`,
                      { status: text(f, "status"), reason: text(f, "reason") },
                      "PATCH",
                    );
                  }).catch((err) => setError(err.message));
                }}
              >
                <Field label={`Review mention ${m.alias}`}>
                  <select name="status" defaultValue={m.status}>
                    {[
                      "CONFIRMED_MATCH",
                      "POSSIBLE_MATCH",
                      "NEEDS_REVIEW",
                      "REJECTED_MATCH",
                    ].map((s) => (
                      <option key={s} value={s}>
                        {labels[s]}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Lý do review mention">
                  <input
                    name="reason"
                    required
                    minLength={5}
                    maxLength={2000}
                  />
                </Field>
                <Button type="submit" variant="outline">
                  Lưu review mention
                </Button>
              </form>
            </section>
          ))}
          <h3>Citations tường minh</h3>
          {!row.citations.length && (
            <p>
              {row.extraction.data.citation_complete
                ? "Nguồn hỗ trợ citation, metadata đầy đủ và zero citation được ghi nhận."
                : "Chưa có citation xác nhận hoặc metadata không đủ; đây không phải 0% citation."}
            </p>
          )}
          {row.citations.map((c) => (
            <section className="visibility-source" key={c.id}>
              <a
                className="visibility-link"
                href={c.normalized_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {c.normalized_url}
              </a>
              <p>
                {labels[c.ownership]} ·{" "}
                {labels[c.attribution_status] || c.attribution_status}
              </p>
              <p>
                {labels[c.source_type]} · {c.data.source_verification}
              </p>
              <p>HTTP chưa xác minh · nội dung/claim chưa so sánh độc lập.</p>
              {c.data.quote && <blockquote>{c.data.quote}</blockquote>}
              {c.data.problems.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </section>
          ))}
          <LiveObservationEvidence row={row} project={project} />
          <h3>URL xuất hiện trong văn bản · không phải citation</h3>
          <DataView data={row.extraction.data.url_mentions} />
          <h3>Metadata thiếu / cảnh báo</h3>
          <p>
            {row.missing_metadata.join(", ") ||
              "Các metadata chính đã có; chưa xác nhận nguồn độc lập."}
          </p>
          {row.extraction.data.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
          <details>
            <summary>Annotations và provenance gốc</summary>
            <DataView data={row.original} />
          </details>
          {row.supersedes_id && (
            <p>Bản sửa của {row.supersedes_id}. Bản gốc vẫn lưu nguyên vẹn.</p>
          )}
          {row.corrections.length > 0 && (
            <p>
              Quan sát đã có bản sửa: {row.corrections.join(", ")}. Bản cũ được
              loại khỏi mẫu số hiện tại.
            </p>
          )}
          <div className="visibility-actions">
            <Button
              variant="outline"
              disabled={
                !!row.corrections.length ||
                (row.collection_method === "PROVIDER_API" &&
                  !!(
                    row.original.source_metadata as
                      | { collection_request_id?: string }
                      | undefined
                  )?.collection_request_id)
              }
              onClick={() => onCorrect(row)}
            >
              Tạo bản sửa có lý do
            </Button>
          </div>
          <label className="visibility-check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Tạo revision nhận diện mới theo registry hiện tại, giữ các revision
            và review cũ
          </label>
          <Button
            variant="outline"
            disabled={!confirmed}
            onClick={() => {
              void run(async () => {
                await visibilityWrite(
                  `/observations/${row.id}/extract?project_id=${project}`,
                  { confirm: true },
                );
                setConfirmed(false);
              }).catch((err) => setError(err.message));
            }}
          >
            Phân tích lại nhận diện
          </Button>
        </>
      )}
    </Sheet>
  );
}
export function OpportunityDrawer({
  id,
  project,
  close,
  run,
  openObservation,
}: {
  id: string;
  project: VisibilityProject;
  close: () => void;
  run: Run;
  openObservation: (id: string) => void;
}) {
  const query = useQuery(
    visibilityQuery<GEOOpportunity>(
      `/opportunities/${id}?project_id=${project.id}`,
      !!id,
    ),
  );
  const row = query.data;
  const [error, setError] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [busy, setBusy] = useState(false);
  const workspaceLink = `/ai-workspace?project=${encodeURIComponent(project.local_project_id)}&visibility=${project.id}&geo=${id}`;
  return (
    <Sheet
      open={!!id}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title="GEO Opportunity · evidence & review"
      description="Fact theo rule và giả thuyết AI được phân biệt. Phê duyệt chỉ lưu review, không sửa website hay chứng minh nhân quả."
    >
      {query.isPending && <p role="status">Đang đọc cơ hội…</p>}
      {query.isError && <p role="alert">{query.error.message}</p>}
      {error && <p role="alert">{error}</p>}
      {row && (
        <>
          <h3>{row.title}</h3>
          <p>
            {row.rule_id} · {row.priority} ·{" "}
            {labels[row.review_status] || row.review_status}
          </p>
          <h3>Vấn đề quan sát được</h3>
          {row.observed_facts.map((f, i) => (
            <p key={i}>{f.explanation}</p>
          ))}
          <p>
            Chủ đề: {row.affected_topic || "Chưa rõ"} · {row.observation_count}{" "}
            quan sát
          </p>
          {row.affected_url_ids.map((url) => (
            <p key={url}>
              <a
                className="visibility-link"
                href={url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {url}
              </a>
            </p>
          ))}
          <h3>Bằng chứng gốc</h3>
          {row.evidence?.map((e) => (
            <Evidence key={e.id} row={e} openObservation={openObservation} />
          ))}
          <h3>Giải thích / giả thuyết</h3>
          {row.possible_explanations.map((v, i) => (
            <p key={i}>{v}</p>
          ))}
          <h3>Đề xuất và lý do ưu tiên</h3>
          <p>{row.recommended_action}</p>
          <p>{row.priority_reason}</p>
          <p>
            Evidence: {row.evidence_confidence} · Interpretation:{" "}
            {row.interpretation_confidence} · Action: {row.action_confidence}
          </p>
          <h3>Counterevidence và thông tin còn thiếu</h3>
          {[...row.counterevidence, ...row.missing_information].map((v, i) => (
            <p key={i}>{v}</p>
          ))}
          <h3>Kế hoạch xác minh</h3>
          <p>{row.verification_plan}</p>
          <p>{row.expected_benefit_hypothesis}</p>
          <h3>Phân tích bằng Agent hiện có</h3>
          <p>
            Báo cáo ngoại tuyến dùng rule. Phân tích sâu dùng provider, consent
            và ngân sách trong AI Workspace; mở Workspace chưa gửi dữ liệu ra
            ngoài.
          </p>
          <div className="visibility-actions">
            <Button asChild variant="outline">
              <Link to={workspaceLink}>Phân tích sâu trong AI Workspace</Link>
            </Button>
            <Button
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void run(async () => {
                  const conv = await aiWrite<{ id: string }>("/conversations", {
                    project_id: project.local_project_id,
                    title: `GEO · ${row.title}`.slice(0, 120),
                    provider: "local_report",
                  });
                  const result = await visibilityWrite<{
                    workspace_url: string;
                  }>(`/opportunities/${id}/analyze?project_id=${project.id}`, {
                    conversation_id: conv.id,
                    message: {
                      content:
                        "Phân tích cơ hội GEO theo evidence đã chọn; nêu thiếu dữ liệu và cho phép abstain.",
                      request_key: crypto.randomUUID(),
                      provider: "local_report",
                    },
                  });
                  setWorkspace(result.workspace_url);
                })
                  .catch((err) => setError(err.message))
                  .finally(() => setBusy(false));
              }}
            >
              Tạo phân tích ngoại tuyến
            </Button>
          </div>
          {workspace && (
            <Link className="visibility-link" to={workspace}>
              Mở kết quả và lịch sử trong AI Workspace
            </Link>
          )}
          {row.analyses.map((a) => (
            <details key={a.id} className="visibility-evidence">
              <summary>Phân tích đã lưu · cần human verification</summary>
              <DataView data={a.data} />
            </details>
          ))}
          <h3>Human Review</h3>
          <form
            className="visibility-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const ratings = Object.fromEntries(
                [
                  "observation",
                  "citation",
                  "entity",
                  "business_relevance",
                  "interpretation",
                  "feasibility",
                  "completeness",
                  "usefulness",
                ].map((k) => [k, text(f, k)]),
              );
              void run(async () => {
                await visibilityWrite(
                  `/opportunities/${id}/review?project_id=${project.id}`,
                  {
                    status: text(f, "status"),
                    notes: text(f, "notes"),
                    revised_action: text(f, "action") || null,
                    ratings,
                  },
                  "PATCH",
                );
              }).catch((err) => setError(err.message));
            }}
          >
            <Field label="Quyết định review">
              <select name="status" defaultValue={row.review_status}>
                {[
                  "proposed",
                  "under_review",
                  "approved",
                  "rejected",
                  "needs_more_evidence",
                  "investigation",
                ].map((s) => (
                  <option key={s} value={s}>
                    {labels[s]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Ghi chú review GEO">
              <textarea
                name="notes"
                maxLength={2000}
                defaultValue={row.human_review?.notes}
              />
            </Field>
            <Field label="Chỉnh đề xuất (lưu riêng, không thay fact)">
              <textarea
                name="action"
                maxLength={2000}
                defaultValue={row.human_review?.revised_action}
              />
            </Field>
            <details>
              <summary>Đánh giá chất lượng bằng rubric</summary>
              {Object.entries({
                observation: "Độ đúng quan sát",
                citation: "Độ đúng attribution",
                entity: "Độ đúng entity",
                business_relevance: "Liên quan kinh doanh",
                interpretation: "Diễn giải",
                feasibility: "Khả thi hành động",
                completeness: "Đủ bằng chứng",
                usefulness: "Tính hữu ích",
              }).map(([k, label]) => (
                <Field key={k} label={label}>
                  <select name={k} defaultValue="insufficient_evidence">
                    <option value="correct">Đúng</option>
                    <option value="partially_correct">Đúng một phần</option>
                    <option value="incorrect">Sai</option>
                    <option value="insufficient_evidence">
                      Chưa đủ bằng chứng
                    </option>
                  </select>
                </Field>
              ))}
            </details>
            <Button type="submit">Lưu review GEO</Button>
            <p>
              Không có publishing hoặc thực thi thay đổi. Approval không biến
              giả thuyết thành fact.
            </p>
          </form>
        </>
      )}
    </Sheet>
  );
}
