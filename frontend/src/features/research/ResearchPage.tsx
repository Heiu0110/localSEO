import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Plus, Download, RefreshCw } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Sheet } from "../../components/ui/sheet";
import { EmptyState, ErrorState } from "../../components/ui/states";
import { api } from "../../services/apiClient";
import {
  researchQuery,
  researchWrite,
  researchExport,
} from "../../services/researchApi";
import { DataView, stamp } from "../ai/shared";
import type {
  ResearchProject,
  ResearchKeyword,
  ResearchCluster,
  ResearchPageResult,
  ResearchJob,
  SerpSnapshot,
  ResearchOpportunity,
  ClusterProposal,
} from "../../types/research";
import { statuses, intents, mappings, kinds, Options, metric } from "./shared";
const tabs: Record<string, string> = {
  overview: "Tổng quan",
  keywords: "Keyword Explorer",
  clusters: "Clusters",
  serp: "SERP Explorer",
  competitors: "Đối thủ",
  opportunities: "Cơ hội",
  imports: "Nhập / Xuất",
  settings: "Dự án & cấu hình",
};
type Site = { id: string; name: string; site_url: string; source_type: string };
type SetInfo = {
  id: string;
  name: string;
  groups?: { id: string; name: string }[];
};
export function ResearchPage() {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const projects = useQuery(researchQuery<ResearchProject[]>("/projects"));
  const requested = params.get("research");
  const p =
    projects.data?.find((x) => x.id === requested) ||
    (!requested ? projects.data?.[0] : undefined);
  const pid = p?.id || "";
  const scope = `project_id=${encodeURIComponent(pid)}`;
  const tab = tabs[params.get("tab") || ""] ? params.get("tab")! : "overview";
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(false),
    [selected, setSelected] = useState<Set<string>>(new Set()),
    [detail, setDetail] = useState(""),
    [clusterEdit, setClusterEdit] = useState<ResearchCluster | null>(null);
  const [job, setJob] = useState<ResearchJob | null>(null),
    [suggestions, setSuggestions] = useState<ClusterProposal[]>([]);
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState(""),
    [intentFilter, setIntentFilter] = useState(""),
    [brandFilter, setBrandFilter] = useState(""),
    [sort, setSort] = useState("keyword"),
    [page, setPage] = useState(1),
    [oppPage, setOppPage] = useState(1),
    [serpPage, setSerpPage] = useState(1);
  const [visible, setVisible] = useState(
    new Set(["group", "intent", "gsc", "volume", "target", "cluster"]),
  );
  const sites = useQuery({
    queryKey: ["research-sites"],
    queryFn: () => api<Site[]>("/ai/projects"),
  });
  const keywords = useQuery(
    researchQuery<ResearchPageResult<ResearchKeyword>>(
      `/keywords?${scope}&search=${encodeURIComponent(search)}&page=${page}&sort=${sort}${filter ? "&status=" + filter : ""}${intentFilter ? "&intent=" + intentFilter : ""}&brand=${brandFilter}`,
      !!pid && tab === "keywords",
    ),
  );
  // Empty optional enum parameters are omitted by the backend query builder below.
  const clusters = useQuery(
    researchQuery<ResearchCluster[]>(
      `/clusters?${scope}`,
      !!pid && ["clusters", "keywords"].includes(tab),
    ),
  );
  const snaps = useQuery(
    researchQuery<ResearchPageResult<SerpSnapshot>>(
      `/serp/snapshots?${scope}&page=${serpPage}`,
      !!pid && tab === "serp",
    ),
  );
  const opportunities = useQuery(
    researchQuery<ResearchPageResult<ResearchOpportunity>>(
      `/opportunities?${scope}&page=${oppPage}`,
      !!pid && tab === "opportunities",
    ),
  );
  const competitors = useQuery(
    researchQuery<unknown>(
      `/competitors?${scope}`,
      !!pid && tab === "competitors",
    ),
  );
  const providers = useQuery(
    researchQuery<unknown>(
      "/providers",
      tab === "settings" || tab === "overview",
    ),
  );
  const sets = useQuery({
    queryKey: ["research-tracking-sets", p?.local_project_id],
    queryFn: () =>
      api<SetInfo[]>(
        `/keyword-tracking/sets?site_id=${encodeURIComponent(p?.local_project_id || "")}`,
      ),
    enabled: !!p?.local_project_id,
  });
  const keywordDetail = useQuery(
    researchQuery<ResearchKeyword>(
      `/keywords/${detail}?${scope}`,
      !!pid && !!detail,
    ),
  );
  const [snapshotID, setSnapshotID] = useState(""),
    [compareID, setCompareID] = useState(""),
    [comparison, setComparison] = useState<unknown>(null);
  const snapshot = useQuery(
    researchQuery<SerpSnapshot>(
      `/serp/snapshots/${snapshotID}?${scope}`,
      !!pid && !!snapshotID,
    ),
  );
  const [transferSet, setTransferSet] = useState("");
  const transferSetInfo = useQuery({
    queryKey: ["research-set-detail", transferSet],
    queryFn: () => api<SetInfo>(`/keyword-tracking/sets/${transferSet}`),
    enabled: !!transferSet,
  });
  useEffect(() => {
    setSelected(new Set());
    setDetail("");
    setJob(null);
    setSuggestions([]);
    setSnapshotID("");
    setComparison(null);
    setCompareID("");
    setPage(1);
    setOppPage(1);
    setSerpPage(1);
    setTransferSet("");
    setError("");
    setNotice("");
  }, [pid]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await client.invalidateQueries({ queryKey: ["research"] });
      await client.invalidateQueries({ queryKey: ["keywords"] });
      await client.invalidateQueries({ queryKey: ["ai"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xử lý được Research.");
    } finally {
      setBusy(false);
    }
  }
  function navigate(t: string, id = pid) {
    setParams({ ...Object.fromEntries(params), research: id, tab: t });
    setSelected(new Set());
  }
  function toggle(id: string) {
    setSelected((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  async function bulk(changes: Record<string, unknown>) {
    await researchWrite(`/keywords/bulk?${scope}`, {
      ids: [...selected],
      changes,
    });
    setSelected(new Set());
    setNotice("Đã lưu Research; chưa thay đổi Tracking.");
  }
  const reportError =
    keywords.error ||
    clusters.error ||
    snaps.error ||
    opportunities.error ||
    competitors.error ||
    providers.error ||
    keywordDetail.error ||
    snapshot.error;
  return (
    <div className="research-page">
      <div className="page-title-row">
        <div>
          <div className="eyebrow">
            NGHIÊN CỨU CÓ NGUỒN · REVIEW TRƯỚC KHI ÁP DỤNG
          </div>
          <h1>
            <FlaskConical size={26} /> Keyword Research
          </h1>
          <p className="page-description">
            Khám phá từ dữ liệu đã lưu, phân nhóm và phân tích SERP quan sát.
          </p>
        </div>
        <Link
          className="research-link"
          to={`/keyword-tracking${p?.local_project_id ? "?site=" + encodeURIComponent(p.local_project_id) : ""}`}
        >
          ← Bảng theo dõi tuần
        </Link>
      </div>
      <div className="card research-toolbar">
        <label>
          Dự án Research
          <select
            aria-label="Dự án Research"
            value={pid}
            onChange={(e) => navigate(tab, e.target.value)}
          >
            <option value="">Chọn dự án</option>
            {projects.data?.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
                {x.status === "archived" ? " · Lưu trữ" : ""}
              </option>
            ))}
          </select>
        </label>
        <div>
          <strong>
            {p
              ? sites.data?.find((x) => x.id === p.local_project_id)?.name ||
                "Không gắn website"
              : "Dữ liệu riêng cho từng dự án"}
          </strong>
          <p>
            {p
              ? `${p.country} / ${p.language} · ${p.keyword_count} keyword · ${p.snapshot_count} snapshot`
              : "Bắt đầu bằng dự án mới; không cần provider trả phí."}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus size={16} />
          Dự án mới
        </Button>
      </div>
      {error && (
        <div role="alert" className="research-error">
          {error}
        </div>
      )}
      {notice && (
        <p role="status" className="research-notice">
          {notice}
        </p>
      )}
      {projects.isError && (
        <ErrorState
          message={projects.error.message}
          onRetry={() => void projects.refetch()}
        />
      )}
      {projects.isLoading && <p role="status">Đang tải dự án…</p>}
      {!p && !projects.isLoading ? (
        <EmptyState
          title="Chưa chọn dự án Research"
          detail="Tạo dự án gắn website hoặc không gắn website để nhập seed, tệp và SERP."
        />
      ) : (
        <>
          <nav className="research-tabs" aria-label="Phân hệ Research">
            {Object.entries(tabs).map(([id, label]) => (
              <button
                key={id}
                className={tab === id ? "active" : ""}
                onClick={() => navigate(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          {p?.status === "archived" && (
            <p className="report-warning">
              Dự án đang lưu trữ. Mở lại trong Dự án & cấu hình trước khi chỉnh
              sửa.
            </p>
          )}
          {reportError && (
            <ErrorState
              message={reportError.message}
              onRetry={() =>
                void client.invalidateQueries({ queryKey: ["research"] })
              }
            />
          )}
          {tab === "overview" && p && (
            <>
              <div className="research-stats">
                <section className="card">
                  <span>Từ khóa đã lưu</span>
                  <strong>{p.keyword_count}</strong>
                </section>
                <section className="card">
                  <span>SERP snapshots đã nhập</span>
                  <strong>{p.snapshot_count}</strong>
                </section>
                <section className="card">
                  <span>Search locale</span>
                  <strong>
                    {p.country} / {p.language}
                  </strong>
                </section>
              </div>
              <section className="card research-panel">
                <h2>Bắt đầu nghiên cứu</h2>
                <p>
                  {p.research_goal ||
                    "Thêm seed hoặc nhập GSC/Tracking, rồi phân nhóm và rà soát các đề xuất."}
                </p>
                <div className="research-actions">
                  <Button onClick={() => navigate("imports")}>
                    Nhập dữ liệu
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate("keywords")}
                  >
                    Mở Keyword Explorer
                  </Button>
                  <Button variant="outline" onClick={() => navigate("serp")}>
                    Nhập SERP quan sát
                  </Button>
                </div>
                <p className="muted-copy">
                  Research không tự thu thập Google, không tạo search volume.
                  Topical Map chưa triển khai. Review chỉ lưu quyết định; chuyển
                  vào Tracking có bước xác nhận riêng.
                </p>
              </section>
            </>
          )}
          {tab === "keywords" && (
            <>
              <div className="card research-panel">
                <div className="research-filters">
                  <label>
                    Tìm từ khóa
                    <input
                      aria-label="Tìm từ khóa Research"
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setPage(1);
                      }}
                    />
                  </label>
                  <label>
                    Trạng thái
                    <select
                      value={filter}
                      onChange={(e) => {
                        setFilter(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">Tất cả</option>
                      <Options values={statuses} />
                    </select>
                  </label>
                  <label>
                    Intent
                    <select
                      value={intentFilter}
                      onChange={(e) => {
                        setIntentFilter(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">Tất cả</option>
                      <Options values={intents} />
                    </select>
                  </label>
                  <label>
                    Nhãn thương hiệu
                    <select
                      value={brandFilter}
                      onChange={(e) => {
                        setBrandFilter(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">Tất cả</option>
                      <option value="unknown">Chưa phân loại</option>
                      <option value="branded">Branded</option>
                      <option value="non_branded">Non-branded</option>
                    </select>
                  </label>
                  <label>
                    Sắp xếp
                    <select
                      value={sort}
                      onChange={(e) => {
                        setSort(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="keyword">Từ khóa A–Z</option>
                      <option value="updated">Cập nhật</option>
                      <option value="status">Trạng thái</option>
                    </select>
                  </label>
                </div>
                <details>
                  <summary>Cột hiển thị</summary>
                  <div className="research-actions">
                    {Object.entries({
                      group: "Nhóm",
                      intent: "Intent",
                      gsc: "GSC",
                      volume: "Volume/CPC/Difficulty",
                      target: "Target URL",
                      cluster: "Cluster",
                    }).map(([id, label]) => (
                      <label key={id}>
                        <input
                          type="checkbox"
                          checked={visible.has(id)}
                          onChange={() =>
                            setVisible((old) => {
                              const next = new Set(old);
                              if (next.has(id)) next.delete(id);
                              else next.add(id);
                              return next;
                            })
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </details>
              </div>
              <div className="research-table-wrap card">
                <table className="research-table">
                  <thead>
                    <tr>
                      <th>Chọn</th>
                      <th>Keyword / nguồn</th>
                      {visible.has("group") && <th>Nhóm</th>}
                      {visible.has("intent") && <th>Search Intent</th>}
                      {visible.has("gsc") && (
                        <>
                          <th>GSC Clicks / Impressions</th>
                          <th>GSC CTR / Average Position</th>
                        </>
                      )}
                      {visible.has("volume") && (
                        <th>Demand / paid / organic</th>
                      )}
                      {visible.has("target") && <th>Target URL</th>}
                      {visible.has("cluster") && <th>Cluster</th>}
                      <th>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keywords.data?.rows.map((k) => (
                      <tr key={k.id}>
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`Chọn ${k.keyword_text}`}
                            checked={selected.has(k.id)}
                            onChange={() => toggle(k.id)}
                          />
                        </td>
                        <td>
                          <button
                            className="research-text-button"
                            onClick={() => setDetail(k.id)}
                          >
                            {k.keyword_text}
                          </button>
                          <small>
                            {k.country}/{k.language} ·{" "}
                            {[
                              ...new Set(k.sources.map((x) => x.provider)),
                            ].join(", ")}
                          </small>
                        </td>
                        {visible.has("group") && (
                          <td>{k.group_name || "Chưa gán"}</td>
                        )}
                        {visible.has("intent") && <td>{intents[k.intent]}</td>}
                        {visible.has("gsc") && (
                          <>
                            <td>
                              {metric(k, "gsc_clicks")}
                              <small>{metric(k, "gsc_impressions")}</small>
                            </td>
                            <td>
                              {metric(k, "gsc_ctr")}
                              <small>{metric(k, "gsc_position")}</small>
                            </td>
                          </>
                        )}
                        {visible.has("volume") && (
                          <td>
                            {metric(k, "search_volume")}
                            <small>CPC: {metric(k, "cpc")}</small>
                            <small>
                              Paid competition: {metric(k, "paid_competition")}
                            </small>
                            <small>
                              Organic difficulty:{" "}
                              {metric(k, "organic_difficulty")}
                            </small>
                          </td>
                        )}
                        {visible.has("target") && (
                          <td>
                            {k.target_url || "Chưa quyết định"}
                            <small>{mappings[k.mapping_status]}</small>
                          </td>
                        )}
                        {visible.has("cluster") && (
                          <td>
                            {clusters.data?.find((c) => c.id === k.cluster_id)
                              ?.name || "Chưa gán"}
                          </td>
                        )}
                        <td>{statuses[k.status]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {keywords.isLoading && <p role="status">Đang tải từ khóa…</p>}
                {keywords.data?.total === 0 && (
                  <p className="research-empty">
                    Chưa có từ khóa phù hợp. Vào Nhập / Xuất để thêm dữ liệu.
                  </p>
                )}
              </div>
              <div className="research-pagination">
                <Button
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Trước
                </Button>
                <span>
                  Trang {page} · {keywords.data?.total || 0} từ khóa
                </span>
                <Button
                  variant="outline"
                  disabled={page * 25 >= (keywords.data?.total || 0)}
                  onClick={() => setPage(page + 1)}
                >
                  Sau
                </Button>
              </div>
              <section className="card research-panel">
                <h2>{selected.size} từ khóa đang chọn</h2>
                <div className="research-actions">
                  <Button
                    disabled={!selected.size}
                    variant="outline"
                    onClick={() =>
                      void action(() => bulk({ status: "approved" }))
                    }
                  >
                    Duyệt từ khóa đã chọn
                  </Button>
                  <Button
                    disabled={!selected.size}
                    variant="outline"
                    onClick={() =>
                      void action(() => bulk({ status: "needs_review" }))
                    }
                  >
                    Yêu cầu rà soát
                  </Button>
                  <Button
                    disabled={!selected.size}
                    variant="outline"
                    onClick={() => setDetail([...selected][0])}
                  >
                    Chi tiết từ khóa đầu tiên
                  </Button>
                </div>
                <form
                  className="research-actions"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void action(() =>
                      bulk({ group_name: String(f.get("group_name")) }),
                    );
                  }}
                >
                  <label>
                    Nhóm thủ công
                    <input name="group_name" maxLength={100} />
                  </label>
                  <Button disabled={!selected.size || busy}>Gán nhóm</Button>
                </form>
                <div className="research-actions">
                  <label>
                    Gán intent
                    <select
                      aria-label="Gán intent hàng loạt"
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value)
                          void action(() => bulk({ intent: e.target.value }));
                        e.target.value = "";
                      }}
                    >
                      <option value="">Chọn phân loại…</option>
                      <Options values={intents} />
                    </select>
                  </label>
                  <label>
                    Chuyển cluster
                    <select
                      aria-label="Gán cluster hàng loạt"
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value)
                          void action(() =>
                            bulk({
                              cluster_id:
                                e.target.value === "none"
                                  ? null
                                  : e.target.value,
                            }),
                          );
                        e.target.value = "";
                      }}
                    >
                      <option value="">Chọn cluster…</option>
                      <option value="none">Bỏ gán cluster</option>
                      {clusters.data?.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    disabled={selected.size < 2}
                    variant="outline"
                    onClick={() =>
                      void action(async () => {
                        const data = await Promise.all(
                          [...selected]
                            .slice(0, 10)
                            .map((id) =>
                              api(`/research/keywords/${id}?${scope}`),
                            ),
                        );
                        setComparison(data);
                      })
                    }
                  >
                    So sánh tối đa 10 từ khóa
                  </Button>
                </div>
                <form
                  className="research-actions"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void action(async () => {
                      await researchWrite(`/clusters?${scope}`, {
                        name: String(f.get("name")),
                        keyword_ids: [...selected],
                        primary_keyword_id: [...selected][0],
                      });
                      setSelected(new Set());
                      setNotice("Đã tạo cluster bản nháp.");
                    });
                  }}
                >
                  <label>
                    Tạo cluster từ lựa chọn
                    <input
                      name="name"
                      required
                      maxLength={200}
                      placeholder="Tên cluster"
                    />
                  </label>
                  <Button disabled={!selected.size || busy}>Tạo cluster</Button>
                </form>
                <form
                  className="research-actions"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void action(async () =>
                      setJob(
                        await researchWrite<ResearchJob>(
                          `/export/keyword-tracking-preview?${scope}`,
                          {
                            keyword_ids: [...selected],
                            set_id: transferSet,
                            group_id: f.get("group_id") || null,
                          },
                        ),
                      ),
                    );
                  }}
                >
                  <label>
                    Bộ Tracking đích
                    <select
                      aria-label="Bộ Tracking đích"
                      required
                      value={transferSet}
                      onChange={(e) => setTransferSet(e.target.value)}
                    >
                      <option value="">Chọn bộ cùng website</option>
                      {sets.data?.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Nhóm đích
                    <select name="group_id">
                      <option value="">Không gán nhóm</option>
                      {transferSetInfo.data?.groups?.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button disabled={!selected.size || !transferSet || busy}>
                    Xem trước chuyển sang Tracking
                  </Button>
                </form>
                <p className="muted-copy">
                  Chỉ nhận keyword đã duyệt. URL chỉ chuyển nếu mapping đã
                  duyệt; từ khóa trùng được bỏ qua, lịch sử rank giữ nguyên.
                </p>
              </section>
            </>
          )}
          {tab === "clusters" && (
            <>
              <section className="card research-panel">
                <h2>Phân nhóm có giải thích</h2>
                <div className="research-actions">
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        const r = await researchWrite<{
                          proposals: ClusterProposal[];
                          reason?: string;
                        }>(`/clusters/suggest?${scope}`, { method: "lexical" });
                        setSuggestions(r.proposals);
                        setNotice(
                          r.proposals.length
                            ? `${r.proposals.length} đề xuất bản nháp.`
                            : "Chưa có nhóm phù hợp trong 200 từ khóa chưa gán.",
                        );
                      })
                    }
                  >
                    Gợi ý lexical
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        const r = await researchWrite<{
                          proposals: ClusterProposal[];
                          reason?: string;
                        }>(`/clusters/suggest?${scope}`, {
                          method: "serp_overlap",
                        });
                        setSuggestions(r.proposals);
                        setNotice(
                          r.reason ||
                            `${r.proposals.length} đề xuất từ SERP tương thích.`,
                        );
                      })
                    }
                  >
                    Gợi ý SERP overlap
                  </Button>
                </div>
                <form
                  className="research-actions"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const name = new FormData(e.currentTarget).get("name");
                    void action(async () => {
                      await researchWrite(`/clusters?${scope}`, { name });
                      setNotice(
                        "Đã tạo cluster trống. Gán keyword tại Keyword Explorer.",
                      );
                    });
                  }}
                >
                  <label>
                    Cluster thủ công
                    <input name="name" required maxLength={200} />
                  </label>
                  <Button disabled={busy}>Tạo cluster trống</Button>
                </form>
                <p className="muted-copy">
                  Token overlap là heuristic, không chứng minh cùng ngữ nghĩa.
                  SERP overlap chỉ dùng cùng
                  provider/locale/device/location/depth và đủ Top N khai báo.
                </p>
              </section>
              {suggestions.map((s, i) => (
                <section className="card research-panel" key={i}>
                  <h3>{s.name}</h3>
                  <p>
                    {s.keyword_ids.length} keywords · {s.method} · confidence
                    thấp · chưa duyệt
                  </p>
                  <details>
                    <summary>Yếu tố & bằng chứng</summary>
                    <DataView data={s.factors} />
                  </details>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await researchWrite(`/clusters?${scope}`, {
                          name: s.name,
                          keyword_ids: s.keyword_ids,
                          primary_keyword_id: s.primary_keyword_id,
                          intent: s.intent,
                          notes: `${s.method}: ${JSON.stringify(s.factors).slice(0, 1200)}. Chưa duyệt.`,
                        });
                        setSuggestions((old) => old.filter((x) => x !== s));
                      })
                    }
                  >
                    Lưu đề xuất thành bản nháp
                  </Button>
                </section>
              ))}
              <div className="research-table-wrap card">
                <table className="research-table">
                  <thead>
                    <tr>
                      <th>Cluster</th>
                      <th>Số keyword</th>
                      <th>Primary keyword</th>
                      <th>Intent / URL</th>
                      <th>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clusters.data?.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <button
                            className="research-text-button"
                            onClick={() => setClusterEdit(c)}
                          >
                            {c.name}
                          </button>
                        </td>
                        <td>{c.keyword_count}</td>
                        <td>
                          {c.keywords.find((k) => k.id === c.primary_keyword_id)
                            ?.keyword_text || "Chưa chọn"}
                        </td>
                        <td>
                          {intents[c.intent]}
                          <small>{c.target_url || "Chưa quyết định URL"}</small>
                        </td>
                        <td>{statuses[c.status]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {tab === "serp" && (
            <>
              <SerpForm
                pid={pid}
                busy={busy}
                action={action}
                onPreview={setJob}
              />
              <div className="card research-panel">
                <h2>Snapshot đã lưu</h2>
                <p>
                  Ngày thu thập là thời điểm quan sát; import hôm nay không biến
                  SERP cũ thành hiện tại.
                </p>
                <div className="research-filters">
                  <label>
                    Snapshot A
                    <select
                      aria-label="Snapshot A"
                      value={snapshotID}
                      onChange={(e) => {
                        setSnapshotID(e.target.value);
                        setComparison(null);
                      }}
                    >
                      <option value="">Chọn snapshot</option>
                      {snaps.data?.rows.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.keyword_text} · {stamp(x.collected_at)} ·{" "}
                          {x.provider}/{x.device}/{x.location}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Snapshot B
                    <select
                      aria-label="Snapshot B"
                      value={compareID}
                      onChange={(e) => setCompareID(e.target.value)}
                    >
                      <option value="">Chọn để so sánh</option>
                      {snaps.data?.rows.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.keyword_text} · {stamp(x.collected_at)} ·{" "}
                          {x.provider}/{x.device}/{x.location}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    disabled={!snapshotID || !compareID || busy}
                    onClick={() =>
                      void action(async () =>
                        setComparison(
                          await api(
                            `/research/serp/compare?${scope}&a=${snapshotID}&b=${compareID}`,
                          ),
                        ),
                      )
                    }
                  >
                    So sánh snapshots
                  </Button>
                </div>
                <div className="research-pagination">
                  <Button
                    variant="outline"
                    disabled={serpPage <= 1}
                    onClick={() => setSerpPage(serpPage - 1)}
                  >
                    Trang snapshot trước
                  </Button>
                  <span>{snaps.data?.total || 0} snapshots</span>
                  <Button
                    variant="outline"
                    disabled={serpPage * 25 >= (snaps.data?.total || 0)}
                    onClick={() => setSerpPage(serpPage + 1)}
                  >
                    Trang snapshot sau
                  </Button>
                </div>
              </div>
              {snapshot.data && (
                <section className="card research-panel">
                  <h2>{snapshot.data.keyword_text}</h2>
                  <p>
                    {snapshot.data.provider} · {snapshot.data.country}/
                    {snapshot.data.language} · {snapshot.data.location} ·{" "}
                    {snapshot.data.device} · Top {snapshot.data.requested_depth}{" "}
                    · độ sâu trả về {snapshot.data.returned_depth}
                  </p>
                  <p>
                    {stamp(snapshot.data.collected_at)} ·{" "}
                    {snapshot.data.age_days} ngày tuổi ·{" "}
                    {snapshot.data.freshness === "stale"
                      ? "Dữ liệu cũ"
                      : "Gần đây"}{" "}
                    · {snapshot.data.completeness}
                  </p>
                  <div className="research-table-wrap">
                    <table className="research-table">
                      <thead>
                        <tr>
                          <th>Organic position</th>
                          <th>Provider label / loại</th>
                          <th>URL & title</th>
                          <th>Snippet / feature</th>
                        </tr>
                      </thead>
                      <tbody>
                        {snapshot.data.results?.map((r) => (
                          <tr key={r.id}>
                            <td>
                              {r.organic_position ?? "Không phải organic"}
                            </td>
                            <td>
                              {r.provider_position || "Không khai báo"} /{" "}
                              {r.result_type}
                            </td>
                            <td>
                              <a
                                href={r.url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {r.title || r.url}
                              </a>
                              <small>{r.url}</small>
                            </td>
                            <td>
                              {r.snippet}
                              <small>
                                {r.features.join(", ") ||
                                  "Không khai báo feature"}
                              </small>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <h3>Website được chọn trong snapshot</h3>
                  <DataView data={snapshot.data.selected_website_presence} />
                  {snapshot.data.limitations?.map((x) => (
                    <p className="muted-copy" key={x}>
                      {x}
                    </p>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() =>
                      void action(() =>
                        researchExport(pid, "serp", "json", snapshotID),
                      )
                    }
                  >
                    Xuất snapshot JSON
                  </Button>
                </section>
              )}
            </>
          )}
          {tab === "competitors" && (
            <section className="card research-panel">
              <h2>Domain trong SERP mẫu</h2>
              <p>
                Mẫu số là số SERP đã lấy mẫu trong cùng cohort, không phải thị
                phần hoặc traffic đối thủ. Không tự crawl URL ngoài.
              </p>
              <DataView data={competitors.data} />
            </section>
          )}
          {tab === "opportunities" && (
            <>
              <section className="card research-panel">
                <h2>Cơ hội cần điều tra</h2>
                <p>
                  Quy tắc minh bạch dùng bằng chứng đã lưu; không phải điểm
                  Google hoặc dự đoán thứ hạng.
                </p>
                <Button
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      const r = await researchWrite<{
                        evaluated_keywords: number;
                        active_rules: number;
                      }>(`/opportunities/refresh?${scope}`, { confirm: true });
                      setNotice(
                        `Đã phân tích ${r.evaluated_keywords} keyword, ${r.active_rules} tín hiệu cần điều tra; không gọi API ngoài.`,
                      );
                    })
                  }
                >
                  <RefreshCw size={16} />
                  Phân tích cơ hội
                </Button>
              </section>
              {opportunities.data?.rows.map((o) => (
                <section className="card research-panel" key={o.id}>
                  <h3>
                    {kinds[o.kind] || o.kind} · {o.keyword_text}
                  </h3>
                  <p>
                    Ưu tiên {o.priority} · confidence {o.confidence} ·{" "}
                    {statuses[o.status]}
                  </p>
                  <p>{o.proposed_action}</p>
                  <details>
                    <summary>Bằng chứng của đề xuất</summary>
                    <DataView data={o.evidence} />
                  </details>
                  <form
                    className="research-actions"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const f = new FormData(e.currentTarget);
                      void action(() =>
                        researchWrite(
                          `/opportunities/${o.id}?${scope}`,
                          Object.fromEntries(f),
                          "PATCH",
                        ),
                      );
                    }}
                  >
                    <label>
                      Review
                      <select
                        aria-label="Review"
                        name="status"
                        defaultValue={o.status}
                      >
                        <Options values={statuses} />
                      </select>
                    </label>
                    <label>
                      Ghi chú
                      <input
                        name="notes"
                        defaultValue={o.notes}
                        maxLength={2000}
                      />
                    </label>
                    <Button disabled={busy}>Lưu review cơ hội</Button>
                  </form>
                </section>
              ))}
              <div className="research-pagination">
                <Button
                  variant="outline"
                  disabled={oppPage <= 1}
                  onClick={() => setOppPage(oppPage - 1)}
                >
                  Cơ hội trước
                </Button>
                <span>{opportunities.data?.total || 0} đề xuất</span>
                <Button
                  variant="outline"
                  disabled={oppPage * 25 >= (opportunities.data?.total || 0)}
                  onClick={() => setOppPage(oppPage + 1)}
                >
                  Cơ hội sau
                </Button>
              </div>
            </>
          )}
          {tab === "imports" && p && (
            <>
              <ImportPanel
                project={p}
                sets={sets.data || []}
                busy={busy}
                action={action}
                onPreview={setJob}
              />
              <section className="card research-panel">
                <h2>Xuất nghiên cứu</h2>
                <form
                  className="research-actions"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void action(() =>
                      researchExport(
                        pid,
                        String(f.get("kind")),
                        String(f.get("format")),
                      ),
                    );
                  }}
                >
                  <label>
                    Báo cáo
                    <select name="kind">
                      <option value="keywords">Từ khóa + nguồn metrics</option>
                      <option value="clusters">Cluster map</option>
                      <option value="competitors">So sánh đối thủ</option>
                      <option value="opportunities">Backlog cơ hội</option>
                      <option value="topical_compatibility">
                        Mapping cho Topical Map tương lai
                      </option>
                    </select>
                  </label>
                  <label>
                    Định dạng
                    <select name="format">
                      <option>json</option>
                      <option>csv</option>
                      <option>xlsx</option>
                    </select>
                  </label>
                  <Button disabled={busy}>
                    <Download size={16} />
                    Xuất báo cáo
                  </Button>
                </form>
                <p className="muted-copy">
                  JSON keyword có thể nhập lại với provenance/metrics. CSV/XLSX
                  export là báo cáo có nguồn trong cột sources; nhập bảng đơn
                  dùng schema được mô tả trong tài liệu.
                </p>
              </section>
            </>
          )}
          {tab === "settings" && p && (
            <>
              <ProjectSettings
                p={p}
                busy={busy}
                action={action}
                onDeleted={() => setParams({})}
                onDuplicate={(id) => navigate("overview", id)}
              />
              <section className="card research-panel">
                <h2>Nguồn & provider</h2>
                <p>
                  v0.7 Core không có request provider trả phí. Google Ads cần
                  quyền/token riêng, không dùng token GSC. SERP API, Google
                  Trends và AI clustering nâng cao chưa kết nối.
                </p>
                <DataView data={providers.data} />
              </section>
            </>
          )}
        </>
      )}
      <Sheet
        open={creating}
        onOpenChange={setCreating}
        title="Tạo dự án Research"
        description="Chọn website để khóa phạm vi dữ liệu; có thể để độc lập."
      >
        {error && (
          <p role="alert" className="research-error">
            {error}
          </p>
        )}
        <form
          className="research-form"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const data = Object.fromEntries(f);
            void action(async () => {
              const r = await researchWrite<ResearchProject>("/projects", {
                ...data,
                local_project_id: data.local_project_id || null,
              });
              setCreating(false);
              navigate("imports", r.id);
            });
          }}
        >
          <label>
            Tên dự án
            <input name="name" required maxLength={200} />
          </label>
          <label>
            Website
            <select aria-label="Website" name="local_project_id">
              <option value="">Không gắn website</option>
              {sites.data?.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name} · {x.source_type}
                </option>
              ))}
            </select>
          </label>
          <label>
            Quốc gia
            <input
              name="country"
              defaultValue="VN"
              pattern="[A-Z]{2}"
              required
            />
          </label>
          <label>
            Ngôn ngữ
            <input name="language" defaultValue="vi" required />
          </label>
          <label>
            Bối cảnh doanh nghiệp
            <textarea name="business_context" maxLength={2000} />
          </label>
          <label>
            Mục tiêu nghiên cứu
            <textarea name="research_goal" maxLength={2000} />
          </label>
          <Button disabled={busy}>Tạo dự án</Button>
        </form>
      </Sheet>
      <Sheet
        open={!!job}
        onOpenChange={(open) => {
          if (!open) setJob(null);
        }}
        title={
          job?.kind === "tracking_transfer"
            ? "Xem trước chuyển sang Tracking"
            : "Xem trước nhập dữ liệu"
        }
        description="Kiểm tra nguồn, URL và trùng lặp trước khi xác nhận. Không thay đổi dữ liệu khi chỉ mở bản xem trước."
      >
        {error && (
          <p role="alert" className="research-error">
            {error}
          </p>
        )}
        {job && (
          <>
            <p>
              {job.data.rows.length} dòng · {job.data.duplicates || 0} dòng
              trùng
            </p>
            {job.data.limitations?.map((x) => (
              <p key={x} className="report-warning">
                {x}
              </p>
            ))}
            {job.data.rows.slice(0, 25).map((row, i) => (
              <details key={i} open={i === 0} className="research-preview-row">
                <summary>
                  {String(row.keyword_text || "SERP snapshot")} ·{" "}
                  {String(row.provider || row.action || "Nguồn đã chọn")}
                </summary>
                <DataView data={row} />
              </details>
            ))}
            {job.data.rows.length > 25 && (
              <p>
                Hiển thị 25 dòng đầu; xác nhận xử lý toàn bộ{" "}
                {job.data.rows.length} dòng.
              </p>
            )}
            <Button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  const r = await researchWrite(
                    `/import/${job.id}/commit?${scope}`,
                    { confirm: true },
                  );
                  setJob(null);
                  setNotice("Đã xác nhận: " + JSON.stringify(r));
                  setSelected(new Set());
                })
              }
            >
              Xác nhận nhập {job.data.rows.length} dòng
            </Button>
          </>
        )}
      </Sheet>
      <Sheet
        open={!!detail}
        onOpenChange={(open) => {
          if (!open) setDetail("");
        }}
        title={keywordDetail.data?.keyword_text || "Chi tiết từ khóa"}
        description="Phân biệt nguồn và kỳ metrics; suggestion cần được rà soát."
      >
        {error && (
          <p role="alert" className="research-error">
            {error}
          </p>
        )}
        {keywordDetail.data && (
          <KeywordEditor
            key={keywordDetail.data.id}
            k={keywordDetail.data}
            busy={busy}
            save={(data) =>
              void action(async () => {
                await researchWrite(
                  `/keywords/${detail}?${scope}`,
                  data,
                  "PATCH",
                );
                setDetail("");
                setNotice("Đã lưu từ khóa Research.");
              })
            }
          />
        )}
      </Sheet>
      <Sheet
        open={!!clusterEdit}
        onOpenChange={(open) => {
          if (!open) setClusterEdit(null);
        }}
        title="Chi tiết cluster"
        description="Manual/assisted cluster không tự cập nhật Keyword Tracking hoặc Topical Map."
      >
        {error && (
          <p role="alert" className="research-error">
            {error}
          </p>
        )}
        {clusterEdit && (
          <ClusterEditor
            key={clusterEdit.id}
            c={clusterEdit}
            all={clusters.data || []}
            busy={busy}
            save={(data) =>
              void action(async () => {
                await researchWrite(
                  `/clusters/${clusterEdit.id}?${scope}`,
                  data,
                  "PATCH",
                );
                setClusterEdit(null);
              })
            }
            operation={(data) =>
              void action(async () => {
                await researchWrite(
                  `/clusters/${clusterEdit.id}/operation?${scope}`,
                  data,
                );
                setClusterEdit(null);
              })
            }
          />
        )}
      </Sheet>
      <Sheet
        open={comparison !== null}
        onOpenChange={(open) => {
          if (!open) setComparison(null);
        }}
        title="Kết quả đối chiếu"
        description="Đọc scope, kỳ và giới hạn trước khi kết luận."
      >
        {Array.isArray(comparison) ? (
          comparison.map((row, i) => <DataView key={i} data={row} />)
        ) : (
          <DataView data={comparison} />
        )}
      </Sheet>
    </div>
  );
}

type Action = (fn: () => Promise<unknown>) => Promise<void>;
function ImportPanel({
  project: p,
  sets,
  busy,
  action,
  onPreview,
}: {
  project: ResearchProject;
  sets: SetInfo[];
  busy: boolean;
  action: Action;
  onPreview: (job: ResearchJob) => void;
}) {
  const [source, setSource] = useState("seed");
  const scope = `project_id=${p.id}`;
  return (
    <>
      <section className="card research-panel">
        <h2>Nhập ứng viên từ nguồn đã có</h2>
        <form
          className="research-form"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const data = {
              source,
              text: f.get("text") || "",
              set_id: f.get("set_id") || null,
              group_id: f.get("group_id") || null,
              days: Number(f.get("days") || 28),
              end_date: f.get("end_date") || null,
              search: f.get("search") || "",
              min_impressions: Number(f.get("min_impressions") || 0),
              min_clicks: Number(f.get("min_clicks") || 0),
              max_ctr: Number(f.get("max_ctr") || 1),
              min_position: Number(f.get("min_position") || 0),
              max_position: Number(f.get("max_position") || 1000),
              limit: 1000,
            };
            void action(async () =>
              onPreview(
                await researchWrite(`/discovery/preview?${scope}`, data),
              ),
            );
          }}
        >
          <label>
            Nguồn nhập
            <select
              aria-label="Nguồn nhập Research"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="seed">Seed thủ công</option>
              <option value="gsc">GSC queries đã lưu</option>
              <option value="tracking">Keyword Tracking đã lưu</option>
              <option value="crawl">Title từ crawl đã lưu (heuristic)</option>
            </select>
          </label>
          {source === "seed" && (
            <label>
              Seed keywords, mỗi dòng một từ khóa
              <textarea
                name="text"
                aria-label="Seed keywords"
                rows={7}
                maxLength={50000}
                required
                placeholder={"may balo học sinh\nxưởng may balo"}
              />
            </label>
          )}
          {source === "tracking" && (
            <>
              <label>
                Bộ Tracking nguồn
                <select name="set_id" required>
                  <option value="">Chọn bộ</option>
                  {sets.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                ID nhóm nguồn (để trống nhập cả bộ)
                <input name="group_id" maxLength={100} />
              </label>
            </>
          )}
          {source === "gsc" && (
            <div className="research-filters">
              <label>
                Kỳ GSC
                <select name="days">
                  <option value="28">28 ngày</option>
                  <option value="7">7 ngày</option>
                  <option value="90">90 ngày</option>
                </select>
              </label>
              <label>
                Ngày kết thúc
                <input name="end_date" type="date" />
              </label>
              <label>
                Query chứa
                <input name="search" maxLength={200} />
              </label>
              <label>
                Impressions tối thiểu
                <input
                  name="min_impressions"
                  type="number"
                  min={0}
                  defaultValue={0}
                />
              </label>
              <label>
                Clicks tối thiểu
                <input
                  name="min_clicks"
                  type="number"
                  min={0}
                  defaultValue={0}
                />
              </label>
              <label>
                CTR tối đa (0–1)
                <input
                  name="max_ctr"
                  type="number"
                  min={0}
                  max={1}
                  step="any"
                  defaultValue={1}
                />
              </label>
              <label>
                Average Position từ
                <input
                  name="min_position"
                  type="number"
                  min={0}
                  step="any"
                  defaultValue={0}
                />
              </label>
              <label>
                Average Position đến
                <input
                  name="max_position"
                  type="number"
                  min={0}
                  step="any"
                  defaultValue={1000}
                />
              </label>
            </div>
          )}
          <p className="muted-copy">
            Seed/crawl không có demand metrics. Nhập GSC tối đa 1.000 query đã
            lưu; impressions không phải search volume. Nhập Tracking không thay
            đổi weekly rank.
          </p>
          <Button disabled={busy}>Xem trước nguồn nhập</Button>
        </form>
      </section>
      <section className="card research-panel">
        <h2>Nhập tệp CSV / XLSX / JSON</h2>
        <p>
          Tối đa 100 KiB, 1.000 dòng; cần cột Keyword. Metrics cần Source; CPC
          cần cpc_currency, competition/difficulty cần metric_scale. Không chấp
          nhận công thức XLSX.
        </p>
        <form
          className="research-form"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            f.set("project_id", p.id);
            void action(async () =>
              onPreview(await researchWrite("/import/preview", f)),
            );
          }}
        >
          <label>
            Tệp nghiên cứu
            <input name="file" type="file" accept=".csv,.xlsx,.json" required />
          </label>
          <label>
            Loại dữ liệu
            <select name="kind">
              <option value="keywords">Keyword Research</option>
              <option value="serp">Một SERP snapshot</option>
            </select>
          </label>
          <label>
            Ánh xạ cột JSON (tùy chọn)
            <textarea
              name="mapping"
              defaultValue="{}"
              rows={3}
              placeholder={'{"keyword_text":"Từ khóa","provider":"Nguồn"}'}
            />
          </label>
          <Button disabled={busy}>Xem trước tệp</Button>
        </form>
        <details>
          <summary>Header mẫu cho keyword CSV/XLSX</summary>
          <pre>
            keyword_text,provider,country,language,group_name,intent,target_url,search_volume,cpc,cpc_currency,paid_competition,organic_difficulty,metric_scale
          </pre>
          <p>
            Giữ trống metrics chưa có; không điền 0 thay cho chưa biết. JSON
            dùng schema Candidate; xem docs/KEYWORD_RESEARCH_DATA_MODEL.md trong
            repo.
          </p>
        </details>
      </section>
    </>
  );
}
function KeywordEditor({
  k,
  busy,
  save,
}: {
  k: ResearchKeyword;
  busy: boolean;
  save: (data: unknown) => void;
}) {
  return (
    <>
      <form
        className="research-form"
        onSubmit={(e) => {
          e.preventDefault();
          save(Object.fromEntries(new FormData(e.currentTarget)));
        }}
      >
        <label>
          Nhóm
          <input
            name="group_name"
            defaultValue={k.group_name}
            maxLength={100}
          />
        </label>
        <label>
          Search Intent
          <select
            aria-label="Search Intent"
            name="intent"
            defaultValue={k.intent}
          >
            <Options values={intents} />
          </select>
        </label>
        <p className="muted-copy">
          Gợi ý heuristic: {intents[k.intent_suggestion?.intent || "unknown"]} ·{" "}
          {k.intent_suggestion?.reason}. Chưa tự áp dụng.
        </p>
        <label>
          Target URL
          <input
            name="target_url"
            defaultValue={k.target_url}
            maxLength={2048}
          />
        </label>
        <label>
          Trạng thái mapping
          <select name="mapping_status" defaultValue={k.mapping_status}>
            <Options values={mappings} />
          </select>
        </label>
        <label>
          Nhãn thương hiệu
          <select name="brand_label" defaultValue={k.brand_label}>
            <option value="unknown">Chưa rõ</option>
            <option value="branded">Branded</option>
            <option value="non_branded">Non-branded</option>
          </select>
        </label>
        <label>
          Review
          <select name="status" defaultValue={k.status}>
            <Options values={statuses} />
          </select>
        </label>
        <label>
          Ghi chú
          <textarea name="notes" defaultValue={k.notes} maxLength={4000} />
        </label>
        <Button disabled={busy}>Lưu từ khóa Research</Button>
      </form>
      <h3>Ứng viên URL · chưa duyệt</h3>
      <DataView data={k.target_suggestions} />
      <h3>Nguồn và metrics độc lập</h3>
      {k.sources.map((s) => (
        <details key={s.id}>
          <summary>
            {s.provider} · {s.method} · {stamp(s.collected_at)}
          </summary>
          <DataView data={s} />
        </details>
      ))}
      <h3>Lịch sử review</h3>
      <DataView data={k.reviews} />
    </>
  );
}
function ClusterEditor({
  c,
  all,
  busy,
  save,
  operation,
}: {
  c: ResearchCluster;
  all: ResearchCluster[];
  busy: boolean;
  save: (data: unknown) => void;
  operation: (data: unknown) => void;
}) {
  const [members, setMembers] = useState(new Set<string>());
  return (
    <>
      <form
        className="research-form"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          save({
            ...Object.fromEntries(f),
            primary_keyword_id: f.get("primary_keyword_id") || null,
          });
        }}
      >
        <label>
          Tên cluster
          <input name="name" defaultValue={c.name} required maxLength={200} />
        </label>
        <label>
          Primary keyword
          <select
            name="primary_keyword_id"
            defaultValue={c.primary_keyword_id || ""}
          >
            <option value="">Chưa chọn</option>
            {c.keywords.map((k) => (
              <option key={k.id} value={k.id}>
                {k.keyword_text}
              </option>
            ))}
          </select>
        </label>
        <label>
          Intent
          <select name="intent" defaultValue={c.intent}>
            <Options values={intents} />
          </select>
        </label>
        <label>
          Loại trang đề xuất
          <input name="page_type" defaultValue={c.page_type} maxLength={100} />
        </label>
        <label>
          Target URL cluster
          <input
            name="target_url"
            defaultValue={c.target_url}
            maxLength={2048}
          />
        </label>
        <label>
          Mapping
          <select name="mapping_status" defaultValue={c.mapping_status}>
            <Options values={mappings} />
          </select>
        </label>
        <label>
          Review cluster
          <select
            aria-label="Review cluster"
            name="status"
            defaultValue={c.status}
          >
            <Options values={statuses} />
          </select>
        </label>
        <label>
          Ghi chú & bằng chứng
          <textarea name="notes" defaultValue={c.notes} maxLength={2000} />
        </label>
        <Button disabled={busy}>Lưu review cluster</Button>
      </form>
      <h3>Thành viên</h3>
      {c.keywords.map((k) => (
        <label className="research-member" key={k.id}>
          <input
            type="checkbox"
            checked={members.has(k.id)}
            onChange={() =>
              setMembers((old) => {
                const next = new Set(old);
                if (next.has(k.id)) next.delete(k.id);
                else next.add(k.id);
                return next;
              })
            }
          />
          {k.keyword_text} · {intents[k.intent]} ·{" "}
          {k.target_url || "Chưa có URL"}
        </label>
      ))}
      <form
        className="research-actions"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          operation({
            operation: "split",
            keyword_ids: [...members],
            name: f.get("name"),
            confirm: true,
          });
        }}
      >
        <label>
          Tách keyword đã chọn sang cluster mới
          <input name="name" required maxLength={200} />
        </label>
        <Button disabled={busy || !members.size}>Xác nhận tách cluster</Button>
      </form>
      <form
        className="research-actions"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          operation({
            operation: "merge",
            destination_id: f.get("destination_id"),
            confirm: true,
          });
        }}
      >
        <label>
          Merge vào cluster đích
          <select name="destination_id" required>
            <option value="">Chọn cluster khác</option>
            {all
              .filter((x) => x.id !== c.id)
              .map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
          </select>
        </label>
        <Button disabled={busy}>Xác nhận merge cluster</Button>
      </form>
      <p>
        Merge xóa cluster nguồn, chuyển thành viên sang bản cần rà soát. Xóa
        cluster chỉ bỏ liên kết, giữ từ khóa và nguồn.
      </p>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => {
          if (window.confirm("Xóa cluster, giữ các từ khóa?"))
            operation({ operation: "delete", confirm: true });
        }}
      >
        Xóa cluster
      </Button>
      <h3>Bằng chứng gốc</h3>
      <DataView data={c.evidence} />
    </>
  );
}
function SerpForm({
  pid,
  busy,
  action,
  onPreview,
}: {
  pid: string;
  busy: boolean;
  action: Action;
  onPreview: (job: ResearchJob) => void;
}) {
  const [search, setSearch] = useState("");
  const candidates = useQuery(
    researchQuery<ResearchPageResult<ResearchKeyword>>(
      `/keywords?project_id=${pid}&search=${encodeURIComponent(search)}&page_size=100`,
      !!pid,
    ),
  );
  return (
    <section className="card research-panel">
      <h2>Nhập SERP đã quan sát</h2>
      <p>
        Không tự tìm Google. Chỉ nhập kết quả bạn có nguồn và thời điểm rõ ràng;
        quảng cáo không được có organic position.
      </p>
      <form
        className="research-form"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          void action(async () => {
            const raw = Object.fromEntries(f);
            const results = JSON.parse(String(f.get("results")));
            const { results: _, ...fields } = raw;
            onPreview(
              await researchWrite(`/serp/import?project_id=${pid}`, {
                ...fields,
                requested_depth: Number(fields.requested_depth),
                collected_at: new Date(
                  String(fields.collected_at),
                ).toISOString(),
                results,
              }),
            );
          });
        }}
      >
        <label>
          Lọc keyword cho snapshot
          <input value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <label>
          Keyword SERP
          <select aria-label="Keyword SERP" name="keyword_id" required>
            <option value="">Chọn keyword đã nhập</option>
            {candidates.data?.rows.map((k) => (
              <option key={k.id} value={k.id}>
                {k.keyword_text} · {k.country}/{k.language}
              </option>
            ))}
          </select>
        </label>
        <div className="research-filters">
          <label>
            Provider / nguồn
            <input
              name="provider"
              placeholder="Tên nguồn quan sát"
              required
              maxLength={100}
            />
          </label>
          <label>
            Search engine
            <select name="search_engine">
              <option>Google</option>
              <option>Bing</option>
              <option>Other</option>
            </select>
          </label>
          <label>
            Quốc gia
            <input
              name="country"
              defaultValue="VN"
              pattern="[A-Z]{2}"
              required
            />
          </label>
          <label>
            Ngôn ngữ
            <input name="language" defaultValue="vi" required />
          </label>
          <label>
            Địa điểm
            <input
              name="location"
              placeholder="Việt Nam / Hà Nội…"
              required
              maxLength={200}
            />
          </label>
          <label>
            Thiết bị
            <select name="device">
              <option value="desktop">Desktop</option>
              <option value="mobile">Mobile</option>
              <option value="tablet">Tablet</option>
            </select>
          </label>
          <label>
            Độ sâu yêu cầu
            <input
              name="requested_depth"
              type="number"
              min={1}
              max={100}
              defaultValue={10}
              required
            />
          </label>
          <label>
            Thời điểm quan sát (giờ máy)
            <input name="collected_at" type="datetime-local" required />
          </label>
          <label>
            Độ đầy đủ
            <select aria-label="Độ đầy đủ" name="completeness">
              <option value="unknown">Chưa rõ</option>
              <option value="partial">Một phần</option>
              <option value="complete_observed">Đủ Top N khai báo</option>
            </select>
          </label>
        </div>
        <label>
          Kết quả JSON (danh sách)
          <textarea
            name="results"
            rows={6}
            required
            placeholder={
              '[{"organic_position":1,"provider_position":"1","result_type":"organic","url":"URL quan sát thực tế","title":"Tiêu đề thực tế"}]'
            }
          />
        </label>
        <Button disabled={busy}>Xem trước SERP</Button>
      </form>
    </section>
  );
}
function ProjectSettings({
  p,
  busy,
  action,
  onDeleted,
  onDuplicate,
}: {
  p: ResearchProject;
  busy: boolean;
  action: Action;
  onDeleted: () => void;
  onDuplicate: (id: string) => void;
}) {
  return (
    <section className="card research-panel">
      <h2>Dự án & quy tắc cơ hội</h2>
      <form
        className="research-form"
        key={p.id}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const raw = Object.fromEntries(f);
          void action(async () => {
            await researchWrite(
              `/projects/${p.id}`,
              {
                ...raw,
                min_impressions: Number(raw.min_impressions),
                low_ctr: Number(raw.low_ctr),
                near_min: Number(raw.near_min),
                near_max: Number(raw.near_max),
              },
              "PATCH",
            );
          });
        }}
      >
        <label>
          Tên dự án
          <input name="name" defaultValue={p.name} required maxLength={200} />
        </label>
        <label>
          Mô tả
          <textarea
            name="description"
            defaultValue={p.description}
            maxLength={2000}
          />
        </label>
        <label>
          Bối cảnh doanh nghiệp
          <textarea
            name="business_context"
            defaultValue={p.business_context}
            maxLength={2000}
          />
        </label>
        <label>
          Mục tiêu nghiên cứu
          <textarea
            name="research_goal"
            defaultValue={p.research_goal}
            maxLength={2000}
          />
        </label>
        <div className="research-filters">
          <label>
            Impressions tối thiểu
            <input
              name="min_impressions"
              type="number"
              min={10}
              max={10000000}
              defaultValue={p.settings.min_impressions}
            />
          </label>
          <label>
            CTR ngưỡng (0–1)
            <input
              name="low_ctr"
              type="number"
              min={0}
              max={1}
              step="any"
              defaultValue={p.settings.low_ctr}
            />
          </label>
          <label>
            Average Position từ
            <input
              name="near_min"
              type="number"
              min={1}
              max={100}
              step="any"
              defaultValue={p.settings.near_min}
            />
          </label>
          <label>
            Average Position đến
            <input
              name="near_max"
              type="number"
              min={1}
              max={100}
              step="any"
              defaultValue={p.settings.near_max}
            />
          </label>
        </div>
        <Button disabled={busy}>Lưu cấu hình Research</Button>
      </form>
      <div className="research-actions">
        <Button
          variant="outline"
          disabled={busy}
          onClick={() =>
            void action(async () => {
              const r = await researchWrite<ResearchProject>(
                `/projects/${p.id}/duplicate`,
                { confirm: true },
              );
              onDuplicate(r.id);
            })
          }
        >
          Sao chép dự án thành bản nháp
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() =>
            void action(() =>
              researchWrite(
                `/projects/${p.id}`,
                { status: p.status === "active" ? "archived" : "active" },
                "PATCH",
              ),
            )
          }
        >
          {p.status === "active" ? "Lưu trữ dự án" : "Mở lại dự án"}
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            if (
              window.confirm(
                "Xóa toàn bộ dữ liệu Research của dự án này? Dữ liệu SEO nguồn vẫn được giữ.",
              )
            )
              void action(async () => {
                await researchWrite(`/projects/${p.id}/delete`, {
                  confirm: true,
                });
                onDeleted();
              });
          }}
        >
          Xóa dự án Research
        </Button>
      </div>
      <p className="muted-copy">
        Sao chép keywords, cluster và nguồn thành bản nháp; snapshot và lịch sử
        review giữ ở dự án gốc. Website/locale dự án cố định sau khi tạo.
      </p>
    </section>
  );
}
