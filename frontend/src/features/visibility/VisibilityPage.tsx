import { LiveResearchPanel } from "./LiveResearchPanel";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Plus, RefreshCw, Download, SearchCheck } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Sheet } from "../../components/ui/sheet";
import { ErrorState, EmptyState } from "../../components/ui/states";
import { api } from "../../services/apiClient";
import { visibilityQuery, visibilityWrite } from "../../services/visibilityApi";
import type { AIProject } from "../../types/ai";
import type {
  VisibilityProject,
  VisibilityEntity,
  VisibilityPrompt,
  VisibilityObservation,
  VisibilityOverview,
  VisibilityGroup,
  VisibilityPage as Page,
  VisibilityReferences,
  VisibilityCitation,
  GEOOpportunity,
  VisibilityDocument,
  VisibilityJob,
  VisibilityRun,
} from "../../types/visibility";
import {
  ProjectForm,
  EntityForm,
  PromptForm,
  ObservationForm,
  DocumentForm,
  CoverageForm,
} from "./Forms";
import { ObservationDrawer, OpportunityDrawer } from "./Drawers";
import { labels, RateValue, stamp, Field, text } from "./shared";
import { DataView } from "../ai/shared";
import { intents, Options } from "../research/shared";
const tabs = {
  overview: "Tổng quan",
  prompts: "Prompt Library",
  live: "AI Search",
  observations: "Quan sát",
  citations: "Citations",
  competitors: "Đối thủ",
  opportunities: "GEO Opportunities",
  sources: "Ngữ cảnh & nguồn",
  imports: "Nhập / Xuất",
  settings: "Cấu hình",
};
type Tab = keyof typeof tabs;
const emptyRefs: VisibilityReferences = {
  research_keywords: [],
  research_clusters: [],
  tracking: [],
};
function Table({
  headers,
  children,
}: {
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="visibility-table-scroll">
      <table className="visibility-table">
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
function Pager({
  page,
  total,
  size = 20,
  onChange,
}: {
  page: number;
  total: number;
  size?: number;
  onChange: (p: number) => void;
}) {
  return (
    <div className="visibility-pagination">
      <Button
        variant="outline"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Trước
      </Button>
      <span>
        Trang {page} · {total} bản ghi
      </span>
      <Button
        variant="outline"
        disabled={page * size >= total}
        onClick={() => onChange(page + 1)}
      >
        Sau
      </Button>
    </div>
  );
}
function GroupCard({
  group,
  competitors = false,
}: {
  group: VisibilityGroup;
  competitors?: boolean;
}) {
  return (
    <section className="card visibility-panel">
      <div className="visibility-cohort">
        <strong>
          {group.cohort.provider} · {group.cohort.model || "Unknown model"}
        </strong>
        <span>
          {group.cohort.country || "Unknown"} /{" "}
          {group.cohort.language || "Unknown"} /{" "}
          {group.cohort.location || "Unknown location"} ·{" "}
          {group.cohort.grounding} · {labels[group.cohort.cohort_type || ""]}
        </span>
        <span>
          {labels[group.cohort.collection_method || ""]} ·{" "}
          {stamp(group.collection_start)} — {stamp(group.collection_end)}
        </span>
        {group.cohort.measurement_profile && (
          <span>
            Measurement profile: {group.cohort.measurement_profile} · locale là
            context yêu cầu, không xác minh vị trí vật lý
          </span>
        )}
      </div>
      <div className="visibility-stats">
        <div>
          <span>Brand Mention Rate</span>
          <RateValue value={group.brand_mention_rate} />
        </div>
        <div>
          <span>Brand Citation Rate</span>
          <RateValue value={group.brand_citation_rate} />
        </div>
        <div>
          <span>Quy mô cohort</span>
          <strong>{group.observation_count}</strong>
          <small>
            {group.unique_prompt_count} prompt khác nhau · không phải nguồn độc
            lập
          </small>
        </div>
      </div>
      {group.coverage_notes.map((note, i) => (
        <p className="muted-copy" key={i}>
          {note}
        </p>
      ))}
      <p className="muted-copy">
        Thiếu metadata citation: {group.missing_citation_metadata} · Unknown
        capability: {group.unknown_citation_capability} · Citation denominator:{" "}
        {group.citation_eligible_observations}
      </p>
      {competitors && (
        <Table
          headers={[
            "Thực thể",
            "Mention: tử / mẫu",
            "Citation: tử / mẫu",
            "Citation occurrences",
            "Domain cite",
            "Prompt trùng brand",
            "Quan sát đối thủ có / brand chưa xác nhận",
          ]}
        >
          {group.entities.map((e) => (
            <tr key={e.entity_id}>
              <td>
                {e.name} · {e.kind}
              </td>
              <td>
                {e.mention_rate.numerator}/{e.mention_rate.denominator} ·{" "}
                {e.mention_rate.percent ?? "Unknown"}%
              </td>
              <td>
                {e.citation_rate.numerator}/{e.citation_rate.denominator} ·{" "}
                {e.citation_rate.percent === null
                  ? "Unknown"
                  : `${e.citation_rate.percent}%`}
              </td>
              <td>{e.citation_occurrences}</td>
              <td>{e.unique_cited_domains.join(", ") || "—"}</td>
              <td>{e.overlapping_prompt_ids.length}</td>
              <td>{e.competitor_without_brand_observation_ids.length}</td>
            </tr>
          ))}
        </Table>
      )}
      {!competitors && group.citation_domain_distribution.length > 0 && (
        <Table
          headers={[
            "Domain",
            "Citation occurrences",
            "URL cite duy nhất",
            "Quan sát chứa domain",
          ]}
        >
          {group.citation_domain_distribution.map((d) => (
            <tr key={d.domain}>
              <td>{d.domain}</td>
              <td>{d.citation_occurrences}</td>
              <td>{d.unique_cited_urls}</td>
              <td>{d.observations_containing_domain}</td>
            </tr>
          ))}
        </Table>
      )}
    </section>
  );
}
export function VisibilityPage() {
  const client = useQueryClient(),
    [params, setParams] = useSearchParams();
  const projects = useQuery(visibilityQuery<VisibilityProject[]>("/projects"));
  const sites = useQuery({
    queryKey: ["visibility-sites"],
    queryFn: () => api<AIProject[]>("/ai/projects"),
  });
  const requested = params.get("visibility");
  const legacy = params.get("project");
  const project = requested
    ? projects.data?.find((p) => p.id === requested)
    : projects.data?.find((p) => p.id === legacy) ||
      projects.data?.find(
        (p) => p.local_project_id === (params.get("site") || legacy),
      ) ||
      projects.data?.[0];
  const pid = project?.id || "",
    q = `project_id=${encodeURIComponent(pid)}`;
  const tab: Tab = Object.hasOwn(tabs, params.get("tab") || "")
    ? (params.get("tab") as Tab)
    : "overview";
  const [modal, setModal] = useState(""),
    [entity, setEntity] = useState<VisibilityEntity | undefined>(),
    [prompt, setPrompt] = useState<VisibilityPrompt | undefined>(),
    [correction, setCorrection] = useState<VisibilityObservation | undefined>();
  const [obs, setObs] = useState(params.get("observation") || ""),
    [op, setOp] = useState(""),
    [page, setPage] = useState(1),
    [groupsPage, setGroupsPage] = useState(1);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [search, setSearch] = useState(""),
    [choiceSearch, setChoiceSearch] = useState("");
  const [provider, setProvider] = useState(""),
    [model, setModel] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [category, setCategory] = useState(""),
    [intent, setIntent] = useState(""),
    [cohort, setCohort] = useState("neutral"),
    [method, setMethod] = useState(""),
    [competitor, setCompetitor] = useState(""),
    [reviewedOnly, setReviewedOnly] = useState(false);
  const [job, setJob] = useState<VisibilityJob | null>(null),
    [kind, setKind] = useState<"prompts" | "observations">("observations"),
    [run, setRun] = useState<VisibilityRun | null>(null),
    [runID, setRunID] = useState(""),
    [status, setStatus] = useState(""),
    [source, setSource] =
      useState<keyof VisibilityReferences>("research_keywords");
  const scope = {
    ...(provider ? { provider } : {}),
    ...(model ? { model } : {}),
    ...(start ? { start } : {}),
    ...(end ? { end } : {}),
    ...(category ? { category } : {}),
    ...(intent ? { intent } : {}),
    cohort_type: cohort,
    ...(reviewedOnly ? { require_human_review: "true" } : {}),
    ...(method ? { collection_method: method } : {}),
    ...(competitor ? { competitor_id: competitor } : {}),
  };
  const filters = new URLSearchParams(scope).toString();
  const entities = useQuery(
    visibilityQuery<VisibilityEntity[]>(`/entities?${q}`, !!pid),
  );
  const prompts = useQuery(
    visibilityQuery<Page<VisibilityPrompt>>(
      `/prompts?${q}&search=${encodeURIComponent(tab === "prompts" ? search : "")}&page=${tab === "prompts" ? page : 1}&page_size=100`,
      !!pid,
    ),
  );
  const choices = useQuery(
    visibilityQuery<Page<VisibilityPrompt>>(
      `/prompts?${q}&search=${encodeURIComponent(choiceSearch)}&page_size=100`,
      !!pid && ["observation", "correction"].includes(modal),
    ),
  );
  const refs = useQuery(
    visibilityQuery<VisibilityReferences>(`/references?${q}`, !!pid),
  );
  const overview = useQuery(
    visibilityQuery<VisibilityOverview>(`/overview?${q}&${filters}`, !!pid),
  );
  const observations = useQuery(
    visibilityQuery<Page<VisibilityObservation>>(
      `/observations?${q}&${filters}&page=${page}`,
      !!pid && tab === "observations",
    ),
  );
  const citations = useQuery(
    visibilityQuery<Page<VisibilityCitation>>(
      `/citations?${q}&${filters}&page=${page}&page_size=20`,
      !!pid && tab === "citations",
    ),
  );
  const opportunities = useQuery(
    visibilityQuery<Page<GEOOpportunity>>(
      `/opportunities?${q}&page=${page}&status=${encodeURIComponent(status)}${runID ? `&run_id=${runID}` : ""}`,
      !!pid && tab === "opportunities",
    ),
  );
  const documents = useQuery(
    visibilityQuery<VisibilityDocument[]>(
      `/documents?${q}`,
      !!pid &&
        (["sources", "opportunities"].includes(tab) ||
          ["document", "coverage"].includes(modal)),
    ),
  );
  const runs = useQuery(
    visibilityQuery<VisibilityRun[]>(
      `/detection-runs?${q}`,
      !!pid && tab === "opportunities",
    ),
  );
  useEffect(() => {
    setPage(1);
    setGroupsPage(1);
    setJob(null);
    setRun(null);
    setRunID("");
    setModal((current) => (current === "project" ? current : ""));
    setObs(params.get("observation") || "");
    setOp("");
    setError("");
    setMessage("");
    setCompetitor("");
  }, [pid]);
  useEffect(() => {
    setPage(1);
    setGroupsPage(1);
  }, [tab, filters, search, status]);
  function navigate(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    next.delete("project");
    for (const [k, v] of Object.entries(values))
      v ? next.set(k, v) : next.delete(k);
    setParams(next);
  }
  async function perform(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await client.invalidateQueries({ queryKey: ["visibility"] });
      setMessage(
        "Đã lưu dữ liệu cục bộ. Không gửi request AI/provider hoặc sửa website.",
      );
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setBusy(false);
    }
  }
  function act(fn: () => Promise<void>) {
    void perform(fn).catch(() => {});
  }
  const open = (type: string) => {
    setModal(type);
    setError("");
    setChoiceSearch("");
    if (type !== "entity") setEntity(undefined);
    if (type !== "prompt") setPrompt(undefined);
    if (type !== "correction") setCorrection(undefined);
  };
  async function download(f: FormData) {
    const format = text(f, "format"),
      kind = text(f, "export_kind");
    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL || "/api"}/visibility/export?${q}&${filters}&kind=${kind}&format=${format}`,
    );
    if (!response.ok) throw new Error("Không thể xuất dữ liệu Visibility.");
    const blob = await response.blob();
    const a = document.createElement("a");
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = `visibility-${kind}.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const data = overview.data;
  const registry = entities.data || [];
  const knownPrompts = prompts.data?.rows || [];
  const queryError = [
    projects,
    sites,
    entities,
    prompts,
    refs,
    overview,
    observations,
    citations,
    opportunities,
    documents,
    runs,
  ].find((q) => q.isError);
  return (
    <div className="visibility-page">
      <div className="page-title-row">
        <div>
          <div className="eyebrow">
            QUAN SÁT CÓ NGUỒN · ĐỀ XUẤT CÓ BẰNG CHỨNG
          </div>
          <h1>
            <Eye size={28} />
            AI Visibility<span className="badge badge-neutral">v0.8.1</span>
          </h1>
          <p>
            Brand mentions, citations và GEO Opportunity Finder trên tập mẫu xác
            định.
          </p>
        </div>
        <Button onClick={() => open("project")}>
          <Plus size={15} />
          Dự án Visibility mới
        </Button>
      </div>
      <div className="card visibility-project-picker">
        <Field label="Dự án AI Visibility">
          <select
            aria-label="Dự án AI Visibility"
            value={pid}
            onChange={(e) => {
              const selected = projects.data?.find(
                (p) => p.id === e.target.value,
              );
              navigate({
                visibility: e.target.value,
                site: selected?.local_project_id || "",
                observation: "",
              });
            }}
          >
            <option value="">Chọn dự án</option>
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.status === "archived" ? " · Lưu trữ" : ""}
              </option>
            ))}
          </select>
        </Field>
        <div>
          <strong>
            {project?.name || "Tạo dự án gắn với website hiện có"}
          </strong>
          <p>
            {project
              ? `${project.country} / ${project.language} · ${project.research_goal || "Chưa ghi mục tiêu nghiên cứu"}`
              : "Nhập quan sát thực tế để bắt đầu; không cần API key hoặc ChatGPT login."}
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="report-warning">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="visibility-notice">
          {message}
        </p>
      )}
      {queryError && (
        <ErrorState
          message={queryError.error!.message}
          onRetry={() =>
            void client.invalidateQueries({ queryKey: ["visibility"] })
          }
        />
      )}
      {projects.isPending && <p role="status">Đang đọc dự án…</p>}
      {!pid && !projects.isPending && (
        <EmptyState
          title="Chưa có dự án AI Visibility"
          detail="Tạo dự án, khai báo brand/domain và nhập phản hồi AI có provenance. Những module SEO hiện tại vẫn dùng bình thường."
        />
      )}
      {project && (
        <>
          <nav
            className="analytics-tabs visibility-tabs"
            aria-label="Phân hệ AI Visibility"
          >
            {Object.entries(tabs).map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() =>
                  navigate({
                    tab: id,
                    visibility: pid,
                    site: project.local_project_id,
                  })
                }
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="visibility-scope-note">
            <SearchCheck size={17} />
            <p>
              Chỉ đo mẫu quan sát đã lưu. Mention ≠ citation ≠ recommendation;
              không phải traffic, search volume hoặc thị phần AI. Web Search chỉ
              chạy sau preflight và xác nhận từng lượt.
            </p>
          </div>
          {[
            "overview",
            "observations",
            "citations",
            "competitors",
            "opportunities",
          ].includes(tab) && (
            <div className="visibility-filters">
              <Field label="Provider">
                <input
                  aria-label="Lọc provider Visibility"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  placeholder="Tất cả · tách cohort"
                />
              </Field>
              <Field label="Model">
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="Tất cả · tách cohort"
                />
              </Field>
              <Field label="Từ ngày">
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </Field>
              <Field label="Đến ngày">
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </Field>
              <Field label="Loại prompt">
                <select
                  value={cohort}
                  onChange={(e) => setCohort(e.target.value)}
                >
                  <option value="neutral">Khám phá trung lập</option>
                  <option value="commercial_discovery">
                    Khám phá thương mại
                  </option>
                  <option value="brand_specific">Có brand trong prompt</option>
                  <option value="all">Tất cả · giữ riêng từng cohort</option>
                </select>
              </Field>
              <Field label="Danh mục">
                <input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="Tất cả"
                />
              </Field>
              <Field label="Intent">
                <select
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                >
                  <option value="">Tất cả</option>
                  <Options values={intents} />
                </select>
              </Field>
              <Field label="Phương pháp">
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  <option value="">Tất cả · tách cohort</option>
                  {[
                    "MANUAL_ENTRY",
                    "IMPORTED_RESPONSE",
                    "PROVIDER_API",
                    "THIRD_PARTY_REPORT",
                  ].map((m) => (
                    <option key={m} value={m}>
                      {labels[m]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Đối thủ lọc báo cáo">
                <select
                  value={competitor}
                  onChange={(e) => setCompetitor(e.target.value)}
                >
                  <option value="">Tất cả đối thủ đã cấu hình</option>
                  {registry
                    .filter((e) => e.kind === "competitor")
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name}
                      </option>
                    ))}
                </select>
              </Field>
            </div>
          )}
          {[
            "overview",
            "observations",
            "opportunities",
            "competitors",
            "citations",
          ].includes(tab) && (
            <label className="visibility-check">
              <input
                type="checkbox"
                checked={reviewedOnly}
                onChange={(e) => setReviewedOnly(e.target.checked)}
              />
              Chỉ dùng extraction được xác nhận trong QA review
            </label>
          )}
          {tab === "overview" && (
            <>
              <div className="visibility-stats">
                <div className="card">
                  <span>Quan sát đủ điều kiện</span>
                  <strong>{data?.eligible_observations ?? 0}</strong>
                  <small>
                    trên {data?.stored_observations ?? 0} bản ghi đã lưu; có lý
                    do loại trừ
                  </small>
                </div>
                <div className="card">
                  <span>Prompt khác nhau được quan sát</span>
                  <strong>{data?.unique_prompts_observed ?? 0}</strong>
                  <small>Không đồng nghĩa số nguồn độc lập</small>
                </div>
                <div className="card">
                  <span>Prompt coverage</span>
                  {data && <RateValue value={data.prompt_coverage} />}
                  <small>Prompt đang dùng trong cohort</small>
                </div>
                <div className="card">
                  <span>Chờ review</span>
                  <strong>{data?.pending_review ?? 0}</strong>
                  <small>
                    {data?.needs_review_mentions ?? 0} mention mơ hồ ·{" "}
                    {data?.opportunities ?? 0} cơ hội trong lịch sử
                  </small>
                </div>
              </div>
              {!data?.groups.length && (
                <EmptyState
                  title="Chưa có quan sát đủ điều kiện trong cohort"
                  detail="Kiểm tra bộ lọc hoặc nhập dữ liệu thực. Unknown citation không được đổi thành 0%."
                />
              )}
              {data?.groups
                .slice((groupsPage - 1) * 10, groupsPage * 10)
                .map((g, i) => (
                  <GroupCard key={i} group={g} />
                ))}
              {data && data.groups.length > 10 && (
                <Pager
                  page={groupsPage}
                  total={data.groups.length}
                  size={10}
                  onChange={setGroupsPage}
                />
              )}
              <details className="card visibility-panel">
                <summary>Độ phủ và lý do loại trừ</summary>
                <DataView data={data?.exclusion_counts} />
                {data?.limitations.map((v, i) => (
                  <p key={i}>{v}</p>
                ))}
              </details>
            </>
          )}
          {tab === "prompts" && (
            <section className="card visibility-panel">
              <div className="visibility-actions">
                <h2>Prompt Library</h2>
                <Button
                  onClick={() => {
                    setPrompt(undefined);
                    open("prompt");
                  }}
                >
                  <Plus size={14} />
                  Thêm prompt
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate({ tab: "imports" })}
                >
                  Nhập từ tệp / Research / Tracking
                </Button>
              </div>
              <Field label="Tìm prompt">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </Field>
              <Table
                headers={[
                  "Prompt",
                  "Danh mục / Intent",
                  "Cohort",
                  "Chủ đề / nguồn",
                  "Ưu tiên / trạng thái",
                  "Review",
                ]}
              >
                {knownPrompts.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.text}
                      <small>ID: {p.id}</small>
                    </td>
                    <td>
                      {p.category}
                      <small>{intents[p.intent]}</small>
                    </td>
                    <td>{labels[p.cohort_type]}</td>
                    <td>
                      {p.topic}
                      <small>
                        {p.source === "ai_generated_candidate"
                          ? "AI draft · không phải demand"
                          : p.source}
                      </small>
                    </td>
                    <td>
                      {p.priority} · {labels[p.status]}
                    </td>
                    <td>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setPrompt(p);
                          open("prompt");
                        }}
                      >
                        Sửa prompt
                      </Button>
                      <Button
                        variant="outline"
                        disabled={p.status !== "active"}
                        onClick={() =>
                          navigate({
                            tab: "live",
                            live_prompt: p.id,
                            collection: "",
                          })
                        }
                      >
                        Kiểm tra với AI Search
                      </Button>
                    </td>
                  </tr>
                ))}
              </Table>
              <Pager
                page={page}
                size={100}
                total={prompts.data?.total || 0}
                onChange={setPage}
              />
            </section>
          )}
          {tab === "live" && (
            <LiveResearchPanel
              key={pid}
              project={project}
              openObservation={setObs}
            />
          )}
          {tab === "observations" && (
            <section className="card visibility-panel">
              <div className="visibility-actions">
                <h2>Quan sát AI đã lưu</h2>
                <Button
                  disabled={!knownPrompts.length}
                  onClick={() => open("observation")}
                >
                  Nhập phản hồi AI
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setKind("observations");
                    navigate({ tab: "imports" });
                  }}
                >
                  Import quan sát
                </Button>
              </div>
              <Table
                headers={[
                  "Prompt / phản hồi",
                  "Provider / model",
                  "Thu thập",
                  "Citation / đầy đủ",
                  "Mentions",
                  "Chi tiết",
                ]}
              >
                {observations.data?.rows.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <strong>{o.prompt_snapshot}</strong>
                      <small>{o.response_text.slice(0, 160)}</small>
                    </td>
                    <td>
                      {o.provider}
                      <small>{o.model || "Unknown"}</small>
                    </td>
                    <td>
                      {stamp(o.observed_at)}
                      <small>{labels[o.collection_method]}</small>
                    </td>
                    <td>
                      {labels[o.citation_capability]}
                      <small>
                        Metadata: {labels[o.citation_metadata]} ·{" "}
                        {labels[o.completeness]}
                      </small>
                    </td>
                    <td>
                      {
                        o.mentions.filter((m) => m.status === "CONFIRMED_MATCH")
                          .length
                      }{" "}
                      span xác nhận
                      <small>
                        {o.citations.length} citation records · không phải
                        recommendation
                      </small>
                    </td>
                    <td>
                      <Button variant="outline" onClick={() => setObs(o.id)}>
                        Xem quan sát
                      </Button>
                    </td>
                  </tr>
                ))}
              </Table>
              <Pager
                page={page}
                total={observations.data?.total || 0}
                onChange={setPage}
              />
            </section>
          )}
          {tab === "citations" && (
            <section className="card visibility-panel">
              <h2>Citation Intelligence</h2>
              <p>
                Chỉ các citation records tường minh; URL thường chỉ xuất hiện
                trong chi tiết quan sát. Ownership không chứng minh nội dung URL
                hỗ trợ claim.
              </p>
              <Table
                headers={[
                  "URL / domain",
                  "Nguồn citation",
                  "Ownership",
                  "Attribution / kiểm chứng",
                  "Quan sát",
                ]}
              >
                {citations.data?.rows.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <a
                        className="visibility-link"
                        href={c.normalized_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {c.normalized_url}
                      </a>
                      <small>{c.domain}</small>
                    </td>
                    <td>{labels[c.source_type]}</td>
                    <td>{labels[c.ownership]}</td>
                    <td>
                      {labels[c.attribution_status] || c.attribution_status}
                      <small>HTTP / content: chưa xác minh độc lập</small>
                    </td>
                    <td>
                      <Button
                        variant="outline"
                        onClick={() => setObs(c.observation_id || "")}
                      >
                        Mở evidence gốc
                      </Button>
                    </td>
                  </tr>
                ))}
              </Table>
              <Pager
                page={page}
                total={citations.data?.total || 0}
                onChange={setPage}
              />
            </section>
          )}
          {tab === "competitors" && (
            <>
              {data?.groups
                .slice((groupsPage - 1) * 10, groupsPage * 10)
                .map((g, i) => (
                  <GroupCard key={i} group={g} competitors />
                ))}
              {!data?.groups.length && (
                <EmptyState
                  title="Chưa có cohort để so sánh"
                  detail="Cần khai báo đối thủ và nhập quan sát có context rõ ràng. Các provider/model được giữ riêng."
                />
              )}
              {data && data.groups.length > 10 && (
                <Pager
                  page={groupsPage}
                  total={data.groups.length}
                  size={10}
                  onChange={setGroupsPage}
                />
              )}
            </>
          )}
          {tab === "opportunities" && (
            <>
              <div className="card visibility-panel">
                <div className="visibility-actions">
                  <h2>GEO Opportunity Finder</h2>
                  <Button
                    disabled={busy || !registry.some((e) => e.kind === "brand")}
                    onClick={() =>
                      act(async () => {
                        const value = await visibilityWrite<VisibilityRun>(
                          `/opportunities/detect?${q}`,
                          scope,
                        );
                        setRun(value);
                        setRunID(value.id);
                      })
                    }
                  >
                    <RefreshCw size={15} />
                    Phát hiện cơ hội từ evidence
                  </Button>
                </div>
                <p>
                  Rule engine hoạt động ngoại tuyến. Không tự gọi AI, crawl,
                  chạy prompt mới hoặc chỉnh website. Mỗi đề xuất phải có
                  evidence và có thể abstain.
                </p>
                <div className="visibility-form-grid">
                  <Field label="Lượt phát hiện">
                    <select
                      value={runID}
                      onChange={(e) => {
                        setRunID(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">
                        Tất cả lịch sử (không gộp thành metric)
                      </option>
                      {runs.data?.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.id.slice(0, 8)} · {r.data.opportunity_ids.length}{" "}
                          cơ hội
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Trạng thái review">
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      <option value="">Tất cả</option>
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
                </div>
                {(run || runs.data?.find((r) => r.id === runID)) && (
                  <p role="status" className="visibility-notice">
                    {
                      (run?.id === runID
                        ? run
                        : runs.data?.find((r) => r.id === runID)
                      )?.data.summary
                    }
                  </p>
                )}
                <Table
                  headers={[
                    "Cơ hội / rule",
                    "Chủ đề / URL",
                    "Quan sát",
                    "Evidence / diễn giải / hành động",
                    "Ưu tiên",
                    "Đề xuất / review",
                  ]}
                >
                  {opportunities.data?.rows.map((o) => (
                    <tr key={o.id}>
                      <td>
                        <button
                          className="visibility-text-button"
                          onClick={() => setOp(o.id)}
                        >
                          {o.title}
                        </button>
                        <small>{o.rule_id}</small>
                      </td>
                      <td>
                        {o.affected_topic || "Chưa rõ"}
                        <small>
                          {o.affected_url_ids.join(", ") ||
                            "Chưa có URL phù hợp được xác nhận"}
                        </small>
                      </td>
                      <td>{o.observation_count}</td>
                      <td>
                        {o.evidence_confidence} / {o.interpretation_confidence}{" "}
                        / {o.action_confidence}
                      </td>
                      <td>
                        {o.priority}
                        <small>{o.priority_reason}</small>
                      </td>
                      <td>
                        {o.action_type}
                        <small>{labels[o.review_status]}</small>
                        <Button variant="outline" onClick={() => setOp(o.id)}>
                          Evidence & review
                        </Button>
                      </td>
                    </tr>
                  ))}
                </Table>
                <Pager
                  page={page}
                  total={opportunities.data?.total || 0}
                  onChange={setPage}
                />
                <details>
                  <summary>Điều kiện thiếu bằng chứng / abstention</summary>
                  <DataView
                    data={
                      (run?.id === runID
                        ? run
                        : runs.data?.find((r) => r.id === runID)
                      )?.data.abstentions || "Chưa có lượt phát hiện được chọn."
                    }
                  />
                </details>
              </div>
            </>
          )}
          {tab === "sources" && (
            <section className="card visibility-panel">
              <div className="visibility-actions">
                <h2>Nguồn nội dung và identity đã nhập</h2>
                <Button onClick={() => open("document")}>
                  Thêm nguồn có provenance
                </Button>
                <Button variant="outline" onClick={() => open("coverage")}>
                  Đánh giá coverage
                </Button>
              </div>
              <p>
                Không fetch URL. Business conflict chỉ dùng thông tin nguyên văn
                trong nguồn được người dùng xác minh/duyệt. Content gap cần
                requirement, trang thực nhập và review có lý do.
              </p>
              {documents.data?.map((d) => (
                <article key={d.id} className="visibility-source">
                  <strong>{d.data.source_name}</strong>
                  <p>
                    {d.kind} · {d.approved ? "Đã duyệt" : "Chưa duyệt"} ·{" "}
                    {d.data.verification}
                  </p>
                  <p>{d.url || "Không có URL nguồn"}</p>
                  <details>
                    <summary>Đọc toàn bộ nội dung nguồn</summary>
                    <pre className="visibility-response">{d.content}</pre>
                    <DataView data={d.data} />
                  </details>
                  <form
                    className="visibility-inline-review"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const f = new FormData(e.currentTarget);
                      act(async () => {
                        await visibilityWrite(
                          `/documents/${d.id}/review?${q}`,
                          { approved: !d.approved, reason: text(f, "reason") },
                          "PATCH",
                        );
                      });
                    }}
                  >
                    <input
                      aria-label={`Lý do review nguồn ${d.data.source_name}`}
                      name="reason"
                      required
                      minLength={5}
                      placeholder="Lý do duyệt/rút approval"
                    />
                    <Button type="submit" variant="outline">
                      {d.approved ? "Rút approval nguồn" : "Duyệt nguồn"}
                    </Button>
                  </form>
                </article>
              ))}
              {!documents.data?.length && (
                <p>
                  Chưa có nội dung nguồn. Agent sẽ nêu thiếu bằng chứng, không
                  suy đoán nội dung trang đối thủ.
                </p>
              )}
            </section>
          )}
          {tab === "imports" && (
            <>
              <section className="card visibility-panel">
                <h2>Nhập có preview và xác nhận</h2>
                <p>
                  JSON/CSV tối đa 100 KiB, 100 dòng; Prompt hỗ trợ XLSX. Không
                  upload credentials. Observation cần prompt_id đã lưu và
                  provider; metadata thiếu để Unknown.
                </p>
                <Field label="Loại dữ liệu nhập">
                  <select
                    value={kind}
                    onChange={(e) => {
                      setKind(e.target.value as "prompts" | "observations");
                      setJob(null);
                    }}
                  >
                    <option value="observations">Quan sát AI</option>
                    <option value="prompts">Prompt Library</option>
                  </select>
                </Field>
                <form
                  className="visibility-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    act(async () => {
                      const rows = JSON.parse(text(f, "json"));
                      setJob(
                        await visibilityWrite(`/${kind}/import-preview?${q}`, {
                          rows,
                        }),
                      );
                    });
                  }}
                >
                  <Field label="Dán danh sách JSON">
                    <textarea name="json" required rows={8} placeholder="[]" />
                  </Field>
                  <Button type="submit" variant="outline" disabled={busy}>
                    Xem trước JSON
                  </Button>
                </form>
                <form
                  className="visibility-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    act(async () => {
                      setJob(
                        await visibilityWrite(`/${kind}/file-preview?${q}`, f),
                      );
                    });
                  }}
                >
                  <Field label="Tệp JSON / CSV / XLSX">
                    <input
                      name="file"
                      type="file"
                      required
                      accept={
                        kind === "prompts" ? ".json,.csv,.xlsx" : ".json,.csv"
                      }
                    />
                  </Field>
                  <Button type="submit" variant="outline" disabled={busy}>
                    Xem trước tệp
                  </Button>
                </form>
                {job && (
                  <div className="visibility-import-preview">
                    <h3>
                      Preview {job.data.validated_rows}/{job.data.input_rows}{" "}
                      dòng hợp lệ
                    </h3>
                    <DataView
                      data={
                        job.data.errors.length ? job.data.errors : job.data.rows
                      }
                    />
                    {job.status === "committed" ? (
                      <p role="status">
                        Đã nhập {job.data.created} dòng mới, bỏ qua{" "}
                        {job.data.duplicates} dòng trùng.
                      </p>
                    ) : (
                      <>
                        <p>
                          Preview chưa thêm quan sát/prompt. Commit có lỗi sẽ bị
                          chặn toàn bộ.
                        </p>
                        <Button
                          disabled={busy || !!job.data.errors.length}
                          onClick={() =>
                            act(async () =>
                              setJob(
                                await visibilityWrite(
                                  `/${job.kind}/import-commit?${q}`,
                                  { job_id: job.id, confirm: true },
                                ),
                              ),
                            )
                          }
                        >
                          Xác nhận nhập {job.data.validated_rows} dòng
                        </Button>
                      </>
                    )}
                  </div>
                )}
              </section>
              <section className="card visibility-panel">
                <h2>Prompt candidates từ Phase 7 / Tracking</h2>
                <p>
                  Chọn dữ liệu đã lưu của website hiện tại; kết quả là bản nháp,
                  không phải search demand được quan sát.
                </p>
                <Field label="Loại nguồn prompt">
                  <select
                    value={source}
                    onChange={(e) =>
                      setSource(e.target.value as keyof VisibilityReferences)
                    }
                  >
                    <option value="research_keywords">Research keywords</option>
                    <option value="research_clusters">Research clusters</option>
                    <option value="tracking">Tracked keywords</option>
                  </select>
                </Field>
                <form
                  className="visibility-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    act(async () => {
                      setKind("prompts");
                      setJob(
                        await visibilityWrite(
                          `/prompts/from-sources-preview?${q}`,
                          { source, ids: f.getAll("ids").map(String) },
                        ),
                      );
                    });
                  }}
                >
                  <Field label="Chọn nguồn đã lưu">
                    <select name="ids" multiple required key={source}>
                      {(refs.data?.[source] || []).map((row) => (
                        <option key={row.id} value={row.id}>
                          {row.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Button type="submit" variant="outline" disabled={busy}>
                    Xem trước prompt candidates
                  </Button>
                </form>
              </section>
              <section className="card visibility-panel">
                <h2>Xuất dữ liệu có scope</h2>
                <form
                  className="visibility-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    act(async () => download(f));
                  }}
                >
                  <div className="visibility-form-grid">
                    <Field label="Dữ liệu xuất">
                      <select name="export_kind">
                        <option value="observations">
                          Quan sát + provenance
                        </option>
                        <option value="prompts">Prompts</option>
                        <option value="citations">Citations</option>
                        <option value="opportunities">
                          GEO opportunities + review
                        </option>
                        <option value="overview">Cohort metrics</option>
                      </select>
                    </Field>
                    <Field label="Định dạng xuất">
                      <select name="format">
                        <option value="json">JSON</option>
                        <option value="csv">CSV</option>
                      </select>
                    </Field>
                  </div>
                  <p>
                    Quan sát/citation dùng các bộ lọc đang chọn ({cohort});
                    không tự gộp thành tỷ lệ toàn nền tảng. CSV được bảo vệ khỏi
                    formula injection.
                  </p>
                  <Button type="submit" variant="outline">
                    <Download size={15} />
                    Xuất Visibility
                  </Button>
                </form>
              </section>
            </>
          )}
          {tab === "settings" && (
            <>
              <section className="card visibility-panel">
                <div className="visibility-actions">
                  <h2>Brand và đối thủ</h2>
                  {!registry.some((e) => e.kind === "brand") && (
                    <Button onClick={() => open("brand")}>
                      Khai báo brand chính
                    </Button>
                  )}
                  <Button variant="outline" onClick={() => open("competitor")}>
                    Thêm đối thủ
                  </Button>
                </div>
                {registry.map((e) => (
                  <article className="visibility-source" key={e.id}>
                    <strong>
                      {e.name} ·{" "}
                      {e.kind === "brand" ? "Brand chính" : "Đối thủ"}
                    </strong>
                    <p>
                      Alias:{" "}
                      {e.config.aliases.map((a) => a.name).join(", ") ||
                        "Chưa có"}
                    </p>
                    <p>
                      Domain:{" "}
                      {e.config.domains
                        .map(
                          (d) =>
                            d.domain +
                            (d.include_subdomains
                              ? " (+ subdomains)"
                              : " (exact host)"),
                        )
                        .join(", ") || "Chưa xác nhận"}
                    </p>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setEntity(e);
                        open("entity");
                      }}
                    >
                      Sửa {e.name}
                    </Button>
                  </article>
                ))}
                {!registry.length && (
                  <p>Khai báo brand trước khi đo mention và chạy GEO Finder.</p>
                )}
              </section>
              <section className="card visibility-panel">
                <h2>Cấu hình dự án</h2>
                <ProjectForm
                  key={pid}
                  sites={sites.data || []}
                  initial={project}
                  busy={busy}
                  onSave={(data) =>
                    perform(async () => {
                      await visibilityWrite(`/projects/${pid}`, data, "PATCH");
                    })
                  }
                />
              </section>
            </>
          )}
        </>
      )}
      <Sheet
        open={!!modal}
        onOpenChange={(open) => {
          if (!open) setModal("");
        }}
        title={
          {
            project: "Tạo dự án AI Visibility",
            brand: "Khai báo brand chính",
            competitor: "Khai báo đối thủ",
            entity: "Sửa registry",
            prompt: "Prompt Library",
            observation: "Nhập quan sát AI",
            correction: "Bản sửa có lịch sử",
            document: "Nhập nguồn nội dung",
            coverage: "Coverage review",
          }[modal] || "Visibility"
        }
        description="Dữ liệu được lưu cục bộ. Tạo/sửa cấu hình không tự gửi dữ liệu đến AI hoặc thay đổi website."
      >
        {modal === "project" && (
          <ProjectForm
            sites={sites.data || []}
            busy={busy}
            onSave={(data) =>
              perform(async () => {
                const p = await visibilityWrite<VisibilityProject>(
                  "/projects",
                  data,
                );
                setModal("");
                navigate({
                  visibility: p.id,
                  site: p.local_project_id,
                  tab: "settings",
                });
              })
            }
          />
        )}
        {project && (
          <>
            {["brand", "competitor", "entity"].includes(modal) && (
              <EntityForm
                key={entity?.id || modal}
                initial={entity}
                kind={
                  modal === "competitor"
                    ? "competitor"
                    : entity?.kind || "brand"
                }
                busy={busy}
                onSave={(data) =>
                  perform(async () => {
                    await visibilityWrite(
                      `/entities${entity ? `/${entity.id}` : ""}?${q}`,
                      data,
                      entity ? "PATCH" : "POST",
                    );
                    setModal("");
                  })
                }
              />
            )}
            {modal === "prompt" && (
              <PromptForm
                key={prompt?.id || "new"}
                initial={prompt}
                refs={refs.data || emptyRefs}
                busy={busy}
                onSave={(data) =>
                  perform(async () => {
                    await visibilityWrite(
                      `/prompts${prompt ? `/${prompt.id}` : ""}?${q}`,
                      data,
                      prompt ? "PATCH" : "POST",
                    );
                    setModal("");
                  })
                }
              />
            )}
            {["observation", "correction"].includes(modal) && (
              <Field label="Tìm prompt của quan sát">
                <input
                  value={choiceSearch}
                  onChange={(e) => setChoiceSearch(e.target.value)}
                  placeholder="Tìm trong toàn bộ Prompt Library"
                />
              </Field>
            )}
            {["observation", "correction"].includes(modal) && (
              <ObservationForm
                key={correction?.id || "new"}
                initial={correction}
                prompts={choices.data?.rows || knownPrompts}
                busy={busy}
                onSave={(data) =>
                  perform(async () => {
                    await visibilityWrite(
                      `/observations${correction ? `/${correction.id}/corrections` : ""}?${q}`,
                      data,
                    );
                    setModal("");
                  })
                }
              />
            )}
            {modal === "document" && (
              <DocumentForm
                entities={registry}
                prompts={knownPrompts}
                busy={busy}
                onSave={(data) =>
                  perform(async () => {
                    await visibilityWrite(`/documents?${q}`, data);
                    setModal("");
                  })
                }
              />
            )}
            {modal === "coverage" && (
              <CoverageForm
                documents={documents.data || []}
                busy={busy}
                onSave={(data) =>
                  perform(async () => {
                    await visibilityWrite(`/coverage-reviews?${q}`, data);
                    setModal("");
                  })
                }
              />
            )}
          </>
        )}
      </Sheet>
      {project && obs && (
        <ObservationDrawer
          key={obs}
          id={obs}
          project={pid}
          entities={registry}
          close={() => {
            setObs("");
            if (params.has("observation")) navigate({ observation: "" });
          }}
          run={perform}
          onCorrect={(row) => {
            setObs("");
            setCorrection(row);
            setModal("correction");
          }}
        />
      )}
      {project && op && (
        <OpportunityDrawer
          key={op}
          id={op}
          project={project}
          close={() => setOp("")}
          run={perform}
          openObservation={(id) => {
            setOp("");
            setObs(id);
          }}
        />
      )}
    </div>
  );
}
