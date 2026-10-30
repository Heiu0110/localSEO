import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { visibilityQuery, visibilityWrite } from "../../services/visibilityApi";
import type { VisibilityObservation } from "../../types/visibility";
import type {
  CollectionRequest,
  LiveObservationMetadata,
  SearchSource,
} from "../../types/visibilityLive";
import { collectionLabels } from "../../types/visibilityLive";
import { DataView } from "../ai/shared";
import { Field, text } from "./shared";

interface Reviews {
  current_extraction_id: string;
  content_verified: false;
  reviews: {
    id: string;
    decision: string;
    data: { extraction_id: string; reason: string };
  }[];
}
export function LiveObservationEvidence({
  row,
  project,
}: {
  row: VisibilityObservation;
  project: string;
}) {
  const meta = row.original.source_metadata as
    | LiveObservationMetadata
    | undefined;
  const enabled = !!meta?.collection_request_id;
  const q = `project_id=${encodeURIComponent(project)}`;
  const sources = useQuery(
    visibilityQuery<SearchSource[]>(
      `/observations/${row.id}/search-sources?${q}`,
      enabled,
    ),
  );
  const request = useQuery(
    visibilityQuery<CollectionRequest>(
      `/collection/requests/${meta?.collection_request_id}?${q}`,
      enabled,
    ),
  );
  const reviews = useQuery(
    visibilityQuery<Reviews>(
      `/observations/${row.id}/collection-review?${q}`,
      enabled,
    ),
  );
  const client = useQueryClient();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  if (!enabled) return null;
  const reviewed = reviews.data?.reviews.find(
    (r) => r.data.extraction_id === reviews.data?.current_extraction_id,
  );
  return (
    <section className="visibility-live-evidence">
      <h3>Live collection · provenance và QA</h3>
      <p>
        Search execution:{" "}
        {collectionLabels[meta?.search_execution || ""] ||
          meta?.search_execution ||
          "Unknown"}
        . Provider response: {meta?.provider_response_id}.
      </p>
      <p>
        Provider Reported → Structurally Validated (URL/annotation) → Ownership
        Classified. Human Reviewed:{" "}
        {reviewed ? reviewed.decision : "Chưa review revision này"}. Source
        Content Verified: chưa xác minh.
      </p>
      <p>
        Citation offsets được giữ nguyên trong metadata. Đơn vị Unicode và quy
        ước end-index chưa được xác minh; citation hiển thị bằng reference
        riêng, không tô sai đoạn trả lời.
      </p>
      <h3>Answer citations từ native annotations</h3>
      {row.citations.map((c) => {
        const native = meta?.answer_citations?.find(
          (n) => n.annotation_id === c.data.annotation_id,
        );
        return (
          <p key={c.id}>
            <a
              className="visibility-link"
              href={c.normalized_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {native?.title || c.domain}
            </a>{" "}
            · {c.ownership} · span:{" "}
            {native?.span_mapping?.status || "không có mapping xác minh"}
          </p>
        );
      })}
      <h3>Search Sources · không đồng nghĩa được trích dẫn</h3>
      {sources.isError && <p role="alert">{sources.error.message}</p>}
      {sources.data?.map((source) => (
        <p key={source.id}>
          <a
            className="visibility-link"
            href={source.normalized_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {source.normalized_url}
          </a>{" "}
          · SEARCH_SOURCE · call {source.data.call_id}
        </p>
      ))}
      {!sources.data?.length && (
        <p>
          Không có danh sách source tùy chọn được lưu. Không suy ra zero answer
          citations từ trạng thái này.
        </p>
      )}
      <h3>Collection Metadata / usage</h3>
      <DataView
        data={{
          requested_context: meta?.requested_context,
          applied_location: meta?.applied_location ?? "Unknown",
          tool_configuration: meta?.tool_configuration,
          measurement_profile: meta?.measurement_profile,
        }}
      />
      {request.data?.usage && <DataView data={request.data.usage} />}
      {request.isError && <p role="alert">{request.error.message}</p>}
      <details>
        <summary>Original provider response đầy đủ đã lưu</summary>
        <DataView
          data={
            request.data?.result.provider_response || "Payload chưa khả dụng."
          }
        />
      </details>
      <h3>Review extraction hiện tại</h3>
      <p>
        Kiểm tra answer, mentions, citation attribution và ownership. Review
        không chứng minh nội dung nguồn chính xác; từ chối sẽ loại extraction
        khỏi metric/GEO hiện tại. Có thể review lại với lý do.
      </p>
      {error && <p role="alert">{error}</p>}
      <form
        className="visibility-form"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          setBusy(true);
          setError("");
          void visibilityWrite(
            `/observations/${row.id}/collection-review?${q}`,
            { decision: text(f, "decision"), reason: text(f, "reason") },
          )
            .then(() => client.invalidateQueries({ queryKey: ["visibility"] }))
            .catch((e) => setError(e.message))
            .finally(() => setBusy(false));
        }}
      >
        <Field label="QA extraction decision">
          <select name="decision" defaultValue="needs_review">
            <option value="needs_review">Cần review</option>
            <option value="confirmed">
              Xác nhận extraction của revision này
            </option>
            <option value="rejected">
              Từ chối extraction của revision này
            </option>
          </select>
        </Field>
        <Field label="Lý do QA extraction">
          <textarea name="reason" required minLength={5} />
        </Field>
        <Button type="submit" disabled={busy}>
          Lưu QA extraction
        </Button>
      </form>
      {reviewed && <p>Review đã lưu: {reviewed.data.reason}</p>}
    </section>
  );
}
