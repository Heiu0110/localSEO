import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Sheet } from "../../components/ui/sheet";
import { visibilityQuery, visibilityWrite } from "../../services/visibilityApi";
import type {
  VisibilityProject,
  VisibilityPrompt,
  VisibilityPage,
} from "../../types/visibility";
import type {
  LiveProviderState,
  LiveSettings,
  CollectionRequest,
} from "../../types/visibilityLive";
import { activeCollection, collectionLabels } from "../../types/visibilityLive";
import { Field, text, stamp } from "./shared";
import { DataView } from "../ai/shared";

const money = (value: number | null | undefined) =>
  value == null ? "Chưa xác định" : `$${value.toFixed(6)} (ước tính)`;
const number = (f: FormData, key: string) =>
  text(f, key).trim() === "" ? null : Number(text(f, key));

export function LiveResearchPanel({
  project,
  openObservation,
}: {
  project: VisibilityProject;
  openObservation: (id: string) => void;
}) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [promptID, setPromptID] = useState(params.get("live_prompt") || ""),
    [preview, setPreview] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const id = params.get("collection") || "",
    q = `project_id=${encodeURIComponent(project.id)}`;
  const provider = useQuery(visibilityQuery<LiveProviderState>("/providers"));
  const choices = useQuery(
    visibilityQuery<VisibilityPage<VisibilityPrompt>>(
      `/prompts?${q}&search=${encodeURIComponent(search)}&page_size=100`,
    ),
  );
  const selected = useQuery(
    visibilityQuery<VisibilityPrompt>(`/prompts/${promptID}?${q}`, !!promptID),
  );
  const history = useQuery({
    ...visibilityQuery<VisibilityPage<CollectionRequest>>(
      `/collection/requests?${q}&page=${page}`,
    ),
    refetchInterval: (query) =>
      query.state.data?.rows.some((r) => activeCollection(r.status))
        ? 1500
        : false,
  });
  const detail = useQuery({
    ...visibilityQuery<CollectionRequest>(
      `/collection/requests/${id}?${q}`,
      !!id,
    ),
    refetchInterval: (query) =>
      query.state.data && activeCollection(query.state.data.status)
        ? 1000
        : false,
  });
  const row = detail.data;
  const cfg = provider.data?.settings;
  useEffect(() => {
    if (row && !activeCollection(row.status))
      void client.invalidateQueries({ queryKey: ["visibility"] });
  }, [row?.status, client]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await client.invalidateQueries({ queryKey: ["visibility"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      void client.invalidateQueries({ queryKey: ["visibility"] });
    }
  }
  function chooseRequest(request: CollectionRequest) {
    const next = new URLSearchParams(params);
    next.set("collection", request.id);
    setParams(next);
  }
  const errors = [provider, choices, selected, history, detail].find(
    (x) => x.isError,
  );
  return (
    <div className="visibility-live">
      <section className="card visibility-panel">
        <h2>OpenAI Web Search · kiểm tra từng prompt</h2>
        <p>
          API key dùng chung OS Credential Vault trong AI Settings. ChatGPT SIWC
          là kết nối riêng, không cấp mặc định quyền Web Search. Mở màn hình này
          không gửi API trả phí.
        </p>
        {error && (
          <p role="alert" className="action-error">
            {error}
          </p>
        )}
        {errors && <p role="alert">{errors.error?.message}</p>}
        {provider.data && (
          <>
            <div className="visibility-stats">
              <div>
                <span>OpenAI API</span>
                <strong className="visibility-live-status">
                  {provider.data.key_configured
                    ? "Đã có key trong OS Vault"
                    : "Chưa kết nối API key"}
                </strong>
              </div>
              <div>
                <span>Model / Web Search capability</span>
                <strong className="visibility-live-status">
                  {cfg?.model || "Chưa chọn model"}
                </strong>
                <small>
                  {provider.data.capability_status} ·{" "}
                  {provider.data.web_search_capability || "Live Check Pending"}
                </small>
              </div>
              <div>
                <span>Ngân sách API chung hôm nay</span>
                <strong className="visibility-live-status">
                  {money(provider.data.daily_used_estimate_usd)}
                </strong>
                <small>
                  Giới hạn nội bộ ${provider.data.effective_daily_limit_usd};
                  khoản chưa rõ giữ dự phòng.
                </small>
              </div>
            </div>
            <p>
              Schema đối chiếu SDK OpenAI chính thức; tài liệu live, giá và
              eligibility còn chờ xác minh. Citation chỉ là provider-reported,
              chưa kiểm chứng nội dung nguồn.
            </p>
            <p>
              Live verification: {provider.data.live_verification} · Model
              access không chứng minh Web Search. Giá:{" "}
              {provider.data.pricing_status}. Lần kiểm tra:{" "}
              {stamp(provider.data.last_validation)}.
            </p>
            {!provider.data.key_configured && (
              <p className="visibility-notice">
                Cần cấu hình OpenAI API key trong AI Settings. Manual/import và
                dữ liệu cũ tiếp tục hoạt động.
              </p>
            )}
            <div className="visibility-actions">
              <Button asChild variant="outline">
                <Link
                  to={`/ai-workspace?project=${project.local_project_id}&tab=settings`}
                >
                  Mở AI Settings để cấu hình API key
                </Link>
              </Button>
              <Button
                variant="outline"
                disabled={busy || !cfg?.model || !provider.data.key_configured}
                onClick={() =>
                  void act(async () => {
                    await visibilityWrite(
                      "/providers/openai-web-search/validate-model",
                      {},
                    );
                  })
                }
              >
                Kiểm tra model access · không chạy search
              </Button>
            </div>
          </>
        )}
        {cfg && (
          <details>
            <summary>
              Cấu hình model, Web Search và giá ước tính · dùng chung trên máy
            </summary>
            <form
              key={JSON.stringify(cfg)}
              className="visibility-form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                void act(async () => {
                  const data: LiveSettings = {
                    ...cfg,
                    enabled: f.has("enabled"),
                    model: text(f, "model") || null,
                    max_output_tokens: Number(text(f, "output")),
                    max_tool_calls: Number(text(f, "calls")),
                    search_context_size: text(
                      f,
                      "context",
                    ) as LiveSettings["search_context_size"],
                    daily_limit_usd: Number(text(f, "daily")),
                    input_usd_per_million: number(f, "input_price"),
                    output_usd_per_million: number(f, "output_price"),
                    tool_usd_per_thousand_calls: number(f, "tool_price"),
                    search_content_billing: text(
                      f,
                      "billing",
                    ) as LiveSettings["search_content_billing"],
                    search_content_tokens_per_call: Number(
                      text(f, "content_tokens"),
                    ),
                    pricing_reviewed_on: text(f, "date") || null,
                    pricing_notes: text(f, "notes"),
                  };
                  await visibilityWrite(
                    "/providers/openai-web-search/settings",
                    data,
                    "PATCH",
                  );
                });
              }}
            >
              <label className="visibility-check">
                <input
                  type="checkbox"
                  name="enabled"
                  defaultChecked={cfg.enabled}
                />
                Bật thao tác kiểm tra Web Search có xác nhận từng lượt
              </label>
              <Field label="Model cho AI Search">
                <input
                  name="model"
                  maxLength={100}
                  defaultValue={cfg.model || ""}
                  placeholder="Nhập model API cần kiểm tra Web Search"
                />
              </Field>
              <div className="visibility-form-grid">
                <Field label="Max output tokens">
                  <input
                    type="number"
                    name="output"
                    min={128}
                    max={4000}
                    required
                    defaultValue={cfg.max_output_tokens}
                  />
                </Field>
                <Field label="Max Web Search tool calls">
                  <input
                    name="calls"
                    type="number"
                    min={1}
                    max={3}
                    required
                    defaultValue={cfg.max_tool_calls}
                  />
                </Field>
                <Field label="Search context size">
                  <select name="context" defaultValue={cfg.search_context_size}>
                    <option>low</option>
                    <option>medium</option>
                    <option>high</option>
                  </select>
                </Field>
                <Field label="Giới hạn API/ngày USD">
                  <input
                    name="daily"
                    type="number"
                    step="any"
                    min="0.001"
                    max={100}
                    required
                    defaultValue={cfg.daily_limit_usd}
                  />
                </Field>
                <Field label="Input USD / 1M tokens">
                  <input
                    name="input_price"
                    type="number"
                    step="any"
                    min={0}
                    defaultValue={cfg.input_usd_per_million ?? ""}
                  />
                </Field>
                <Field label="Output USD / 1M tokens">
                  <input
                    name="output_price"
                    type="number"
                    step="any"
                    min={0}
                    defaultValue={cfg.output_usd_per_million ?? ""}
                  />
                </Field>
                <Field label="Web Search USD / 1000 calls">
                  <input
                    name="tool_price"
                    type="number"
                    step="any"
                    min={0}
                    defaultValue={cfg.tool_usd_per_thousand_calls ?? ""}
                  />
                </Field>
                <Field label="Ngày bạn kiểm tra giá">
                  <input
                    name="date"
                    type="date"
                    defaultValue={cfg.pricing_reviewed_on || ""}
                  />
                </Field>
                <Field label="Cách tính search content">
                  <select
                    name="billing"
                    defaultValue={cfg.search_content_billing}
                  >
                    <option value="unverified">
                      Chưa xác minh · chi phí chưa đủ thành phần
                    </option>
                    <option value="reported_input">
                      Giả định đã tính trong provider input tokens
                    </option>
                    <option value="additional_estimate">
                      Giả định tính thêm search content
                    </option>
                  </select>
                </Field>
                <Field label="Giả định search-content tokens / call">
                  <input
                    name="content_tokens"
                    type="number"
                    min={0}
                    max={128000}
                    defaultValue={cfg.search_content_tokens_per_call}
                  />
                </Field>
              </div>
              <p>
                Đây là giả định bạn cần kiểm tra theo model, không phải giá hiện
                hành đã được LocalSEO xác minh.{" "}
                <a
                  href={cfg.pricing_source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="visibility-link"
                >
                  Trang giá chính thức
                </a>
                . Giới hạn token/tool không phải USD billing cap.
              </p>
              <Field label="Nguồn/ghi chú giả định giá">
                <textarea name="notes" defaultValue={cfg.pricing_notes} />
              </Field>
              <Button type="submit" disabled={busy}>
                Lưu cấu hình AI Search
              </Button>
            </form>
          </details>
        )}
      </section>
      <section className="card visibility-panel">
        <h2>Kiểm tra với AI Search</h2>
        <Field label="Tìm prompt cho AI Search">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm trong toàn bộ Prompt Library"
          />
        </Field>
        <Field label="Chọn prompt AI Search">
          <select
            value={promptID}
            onChange={(e) => setPromptID(e.target.value)}
          >
            <option value="">Chọn một prompt đang hoạt động</option>
            {selected.data &&
              !choices.data?.rows.some((p) => p.id === selected.data.id) && (
                <option value={selected.data.id}>{selected.data.text}</option>
              )}
            {choices.data?.rows
              .filter((p) => p.status === "active")
              .map((p) => (
                <option value={p.id} key={p.id}>
                  {p.text}
                </option>
              ))}
          </select>
        </Field>
        {selected.data && (
          <p className="visibility-response">{selected.data.text}</p>
        )}
        <Button
          disabled={
            !selected.data ||
            !cfg?.enabled ||
            !provider.data?.key_configured ||
            busy
          }
          onClick={() => {
            setPreview(true);
            setError("");
          }}
        >
          Kiểm tra với AI Search · xem preflight
        </Button>
        <p>
          Không viết lại prompt hoặc thêm brand vào câu hỏi. Mỗi lần chạy chỉ
          gửi đúng một prompt; không có lịch/batch monitoring.
        </p>
      </section>
      {row && (
        <section
          className="card visibility-panel"
          aria-label="Kết quả AI Search"
        >
          <h2>{collectionLabels[row.status] || row.status}</h2>
          <p>
            Request {row.id} · {stamp(row.created_at)}
          </p>
          <p>{row.snapshot.binding.prompt_snapshot}</p>
          <p>
            Provider: OpenAI API · model yêu cầu:{" "}
            {row.snapshot.binding.settings.model} · model trả về:{" "}
            {row.result.actual_model || "Chưa rõ"}
          </p>
          <p>
            Search execution:{" "}
            {collectionLabels[row.result.search_execution || ""] ||
              "Chưa có kết quả"}{" "}
            · Answer citations: {row.result.citation_count ?? "Unknown"} ·
            Search sources: {row.result.source_count ?? "Unknown"}
          </p>
          {row.result.error_code && (
            <p role="alert">
              {row.result.error_code}: {row.result.detail}
            </p>
          )}
          {row.result.problems?.map((p) => (
            <p key={p}>{p}</p>
          ))}
          <p>
            Input / output tokens: {row.usage?.input_tokens ?? "Unknown"} /{" "}
            {row.usage?.output_tokens ?? "Unknown"} · chi phí:{" "}
            {money(row.usage?.estimated_cost_usd)} · dự phòng $
            {row.usage?.reserved_usd ?? row.snapshot.binding.authorized_max_usd}
          </p>
          {row.status === "UNKNOWN_REMOTE_OUTCOME" && (
            <p className="visibility-notice">
              Có thể đã tính phí. Không tự phát lại; một preflight mới là một
              yêu cầu có thể bị tính phí mới.
            </p>
          )}
          {row.observation_id && (
            <Button onClick={() => openObservation(row.observation_id!)}>
              Mở observation và kiểm tra citation
            </Button>
          )}
          {["PREFLIGHT_READY", "QUEUED"].includes(row.status) && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  await visibilityWrite(
                    `/collection/requests/${row.id}/cancel?${q}`,
                    {},
                  );
                })
              }
            >
              Hủy trước khi gửi
            </Button>
          )}
          {row.status === "PREFLIGHT_READY" && (
            <Consent
              key={row.id}
              request={row}
              busy={busy}
              submit={(data) =>
                act(async () => {
                  await visibilityWrite(
                    `/collection/requests/${row.id}/confirm?${q}`,
                    data,
                  );
                })
              }
            />
          )}
          <details>
            <summary>Original provider response và usage đã lưu</summary>
            <DataView
              data={row.result.provider_response || "Chưa có payload được lưu."}
            />
            <DataView data={row.usage} />
          </details>
        </section>
      )}
      <section className="card visibility-panel">
        <h2>Lịch sử collection của dự án</h2>
        <p>
          Lưu request/consent/usage kể cả khi lỗi. Không có nút tự retry trả
          phí.
        </p>
        {history.data?.rows.map((request) => (
          <article className="visibility-source" key={request.id}>
            <strong>
              {collectionLabels[request.status] || request.status}
            </strong>
            <p>{request.snapshot.binding.prompt_snapshot}</p>
            <p>
              {stamp(request.created_at)} ·{" "}
              {request.result.search_execution || "Chưa dispatch / chưa rõ"} ·{" "}
              {money(request.usage?.estimated_cost_usd)}
            </p>
            <Button variant="outline" onClick={() => chooseRequest(request)}>
              Xem request {request.id.slice(0, 8)}
            </Button>
          </article>
        ))}
        {!history.data?.rows.length && (
          <p>Chưa có lượt kiểm tra live. Manual/import không bị ảnh hưởng.</p>
        )}
        <div className="visibility-pagination">
          <Button
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Trang trước
          </Button>
          <span>
            Trang {page} · {history.data?.total || 0} requests
          </span>
          <Button
            variant="outline"
            disabled={page * 10 >= (history.data?.total || 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Trang sau
          </Button>
        </div>
      </section>
      <Sheet
        open={preview}
        onOpenChange={setPreview}
        title="Preflight AI Search"
        description="Đây là bước tính ước lượng cục bộ; chưa gọi API trả phí."
      >
        <form
          key={selected.data?.id}
          className="visibility-form"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void act(async () => {
              const request = await visibilityWrite<CollectionRequest>(
                `/collection/preflight?${q}`,
                {
                  prompt_id: promptID,
                  request_key: crypto.randomUUID(),
                  provider: "openai_web_search",
                  country: text(f, "country") || null,
                  language: text(f, "language") || null,
                  city: text(f, "city") || null,
                  region: text(f, "region") || null,
                  authorized_max_usd: Number(text(f, "cap")),
                },
              );
              chooseRequest(request);
              setPreview(false);
            });
          }}
        >
          <p className="visibility-response">{selected.data?.text}</p>
          <p>
            OpenAI API · {cfg?.model} · Web Search bắt buộc. Location
            approximate không chứng minh người dùng đang ở địa điểm đó. Không
            xác định device.
          </p>
          <div className="visibility-form-grid">
            <Field label="Country yêu cầu">
              <input
                name="country"
                pattern="[A-Z]{2}"
                defaultValue={selected.data?.country || project.country}
              />
            </Field>
            <Field label="Ngôn ngữ yêu cầu">
              <input
                name="language"
                defaultValue={selected.data?.language || project.language}
              />
            </Field>
            <Field label="City yêu cầu (nếu có)">
              <input name="city" maxLength={100} />
            </Field>
            <Field label="Region yêu cầu (nếu có)">
              <input name="region" maxLength={100} />
            </Field>
          </div>
          <Field label="Khoản dự phòng tối đa cho lượt này USD">
            <input
              name="cap"
              type="number"
              step="any"
              min="0.001"
              max={10}
              required
              defaultValue="0.1"
            />
          </Field>
          <p>
            Đây là reservation do app kiểm soát, không phải giới hạn thanh toán
            được OpenAI bảo đảm.
          </p>
          {error && <p role="alert">{error}</p>}
          <Button type="submit" disabled={busy}>
            Tính preflight · chưa gửi provider
          </Button>
        </form>
      </Sheet>
    </div>
  );
}

function Consent({
  request,
  busy,
  submit,
}: {
  request: CollectionRequest;
  busy: boolean;
  submit: (data: unknown) => Promise<void>;
}) {
  const binding = request.snapshot.binding,
    estimate = request.snapshot.estimate;
  return (
    <form
      className="visibility-form visibility-consent"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        void submit({
          binding_hash: request.binding_hash,
          authorized_max_usd: binding.authorized_max_usd,
          acknowledge_external_processing: f.has("external"),
          confirm_exact_prompt: f.has("prompt"),
          acknowledge_not_billing_cap: f.has("cap"),
          acknowledge_capability_test: f.has("capability"),
          acknowledge_uncertain_cost: f.has("uncertain"),
        });
      }}
    >
      <h3>Xác nhận đúng một lượt trả phí</h3>
      <p>{binding.prompt_snapshot}</p>
      <p>
        Provider OpenAI API · model {binding.settings.model} · tools web_search
        (required), tối đa {binding.settings.max_tool_calls} call. Context:{" "}
        {JSON.stringify(binding.context)}.
      </p>
      <p>
        Model estimate: {money(estimate.model_estimate_usd)} · tool estimate:{" "}
        {money(estimate.tool_estimate_usd)} · total:{" "}
        {money(estimate.total_estimate_usd)} · known components:{" "}
        {money(estimate.known_component_estimate_usd)}.
      </p>
      <p>
        Giả định input {estimate.estimated_input_tokens} tokens; output tối đa{" "}
        {binding.settings.max_output_tokens}; search calls giả định{" "}
        {estimate.estimated_search_calls}. Giá được bạn kiểm tra{" "}
        {binding.settings.pricing_reviewed_on || "Unknown"}. Reservation $
        {binding.authorized_max_usd}. Hết hạn{" "}
        {stamp(request.snapshot.expires_at)}.
      </p>
      <p>
        Unknown components:{" "}
        {estimate.unknown_cost_components.join(", ") ||
          "Không xác định thêm ngoài giả định giá/cách tính đã chọn; tổng vẫn là ước tính."}
      </p>
      {estimate.limitations.map((note) => (
        <p key={note}>{note}</p>
      ))}
      <label className="visibility-check">
        <input type="checkbox" name="prompt" required />
        Tôi xác nhận đúng prompt, model và context ở trên
      </label>
      <label className="visibility-check">
        <input type="checkbox" name="external" required />
        Tôi đồng ý gửi prompt/context ra OpenAI để xử lý và tìm kiếm web
      </label>
      <label className="visibility-check">
        <input type="checkbox" name="cap" required />
        Tôi chấp thuận dự phòng ${binding.authorized_max_usd}; đây không phải
        provider billing cap
      </label>
      {request.snapshot.capability_status !== "Web Search Supported" && (
        <label className="visibility-check">
          <input name="capability" type="checkbox" required />
          Tôi đồng ý lượt này kiểm tra Web Search capability, có thể thất bại và
          vẫn phát sinh chi phí
        </label>
      )}
      {!!estimate.unknown_cost_components.length && (
        <label className="visibility-check">
          <input name="uncertain" type="checkbox" required />
          Tôi hiểu chi phí còn thành phần chưa xác định
        </label>
      )}
      <Button type="submit" disabled={busy}>
        Xác nhận và gửi một lượt trả phí
      </Button>
    </form>
  );
}
