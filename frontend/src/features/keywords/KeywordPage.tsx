import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Plus, RefreshCw, Download, Target } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Sheet } from "../../components/ui/sheet";
import {
  DashboardSkeleton,
  EmptyState,
  ErrorState,
} from "../../components/ui/states";
import { sitesQuery } from "../../services/dashboardApi";
import { api } from "../../services/apiClient";
import {
  keywordQuery,
  keywordWrite,
  keywordExport,
} from "../../services/keywordApi";
import type {
  KeywordSet,
  KeywordPageResult,
  KeywordOverview as Overview,
  KeywordJob,
  RankPayload,
} from "../../types/keywords";
import { sourceLabel } from "../../components/dashboard/SourceBadge";
import { SetForm, KeywordForm, ProfileForm } from "./KeywordForms";
import { TrackingTable, fixedColumns } from "./TrackingTable";
import { KeywordDetail } from "./KeywordDetail";
import { KeywordOverview } from "./KeywordOverview";
import { WeeklyCheck } from "./WeeklyCheck";
import { ImportExport } from "./ImportExport";
import { localToday, shiftDate, rankError, num } from "./shared";
const tabs: Record<string, string> = {
  overview: "Tổng quan",
  tracking: "Bảng theo dõi",
  weekly: "Kiểm tra tuần",
  sets: "Bộ từ khóa",
  import: "Nhập / Xuất",
  settings: "Cấu hình",
};
export function KeywordPage() {
  const client = useQueryClient();
  const sites = useQuery(sitesQuery);
  const [params, setParams] = useSearchParams();
  const latest = useRef(params);
  useEffect(() => {
    latest.current = params;
  }, [params]);
  const site = params.get("site") || sites.data?.[0]?.id || "";
  const selectedSite = sites.data?.find((s) => s.id === site);
  const sets = useQuery(
    keywordQuery<KeywordSet[]>(
      `/sets?site_id=${encodeURIComponent(site)}`,
      !!site,
    ),
  );
  const requested = params.get("set");
  const setID =
    sets.data?.find((s) => s.id === requested)?.id ||
    (!requested ? sets.data?.find((s) => s.status === "active")?.id : "") ||
    "";
  const detail = useQuery(keywordQuery<KeywordSet>(`/sets/${setID}`, !!setID));
  const set = detail.data;
  const profile =
    set?.profiles.find((p) => p.id === params.get("profile")) ||
    set?.profiles[0];
  const rawWeek = Number(params.get("week"));
  const currentWeek = set
    ? Math.max(
        1,
        Math.min(
          520,
          Math.floor(
            (Date.parse(localToday(set.timezone)) -
              Date.parse(set.start_date)) /
              604800000,
          ) + 1,
        ),
      )
    : 1;
  const week =
    Number.isInteger(rawWeek) && rawWeek >= 1 && rawWeek <= 520
      ? rawWeek
      : currentWeek;
  const tab =
    params.get("tab") && tabs[params.get("tab")!]
      ? params.get("tab")!
      : "tracking";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const [creating, setCreating] = useState(false);
  const [keywordID, setKeywordID] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batch, setBatch] = useState<RankPayload[] | null>(null);
  const [visible, setVisible] = useState(
    new Set(fixedColumns.map((c) => c[0] as string)),
  );
  const [weekOnly, setWeekOnly] = useState(false);
  const [checkedAt, setCheckedAt] = useState("");
  const [search, setSearch] = useState(params.get("search") || "");
  const debounced = useRef(search);
  const status = useQuery({
    queryKey: ["keyword-gsc-dates"],
    queryFn: ({ signal }) =>
      api<{ latest_final_date: string }>("/integrations/gsc/status", signal),
    staleTime: 60000,
  });
  const end =
    params.get("end") ||
    status.data?.latest_final_date ||
    shiftDate(new Date().toISOString().slice(0, 10), -3);
  const days = [7, 28, 90].includes(Number(params.get("days")))
    ? Number(params.get("days"))
    : 28;
  const start = params.get("start") || shiftDate(end, -days + 1);
  const scope = params.get("scope") === "page" ? "page" : "property";
  const query = new URLSearchParams({
    set_id: setID,
    profile_id: profile?.id || "",
    week: String(week),
    date_start: start,
    date_end: end,
    scope,
    page: params.get("page") || "1",
    page_size: params.get("size") || "25",
    search: params.get("search") || "",
    group_id: params.get("group") || "",
    status: params.get("status") || "active",
    rank_filter: params.get("rank") || "",
    sort: params.get("sort") || "keyword",
    direction: params.get("direction") || "asc",
  });
  for (const key of ["min_clicks", "min_impressions", "max_position"])
    if (params.get(key)) query.set(key, params.get(key)!);
  const valid = !!set && !!profile && start <= end;
  const table = useQuery(
    keywordQuery<KeywordPageResult>(`/keywords?${query}`, valid),
  );
  const overviewQuery = new URLSearchParams({
    set_id: setID,
    profile_id: profile?.id || "",
    week: String(week),
    date_start: start,
    date_end: end,
    scope,
  });
  const overview = useQuery(
    keywordQuery<Overview>(`/overview?${overviewQuery}`, valid),
  );
  const jobs = useQuery({
    ...keywordQuery<KeywordJob[]>(`/gsc-sync/status?set_id=${setID}`, !!setID),
    refetchInterval: (q) =>
      q.state.data?.some((j) => ["queued", "running"].includes(j.status))
        ? 1000
        : false,
  });
  const active = jobs.data?.find((j) =>
    ["queued", "running"].includes(j.status),
  );
  const update = useCallback(
    (values: Record<string, string>) => {
      const next = new URLSearchParams(latest.current);
      Object.entries(values).forEach(([k, v]) =>
        v ? next.set(k, v) : next.delete(k),
      );
      latest.current = next;
      setParams(next);
    },
    [setParams],
  );
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== debounced.current) {
        debounced.current = search;
        update({ search, page: "1" });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search, update]);
  useEffect(() => {
    setSearch(params.get("search") || "");
    debounced.current = params.get("search") || "";
  }, [params.get("search")]);
  useEffect(() => {
    setSelected(new Set());
    setKeywordID("");
    setAdding(false);
    setBatch(null);
  }, [
    setID,
    profile?.id,
    params.get("page"),
    params.get("search"),
    params.get("group"),
    params.get("status"),
    params.get("rank"),
  ]);
  const completed = useRef("");
  useEffect(() => {
    const key = jobs.data?.map((j) => j.id + j.status).join();
    if (key && key !== completed.current) {
      completed.current = key;
      void client.invalidateQueries({ queryKey: ["keywords"] });
    }
  }, [jobs.data, client]);
  const action = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true);
      setError("");
      setNotice("");
      try {
        await fn();
        await client.invalidateQueries({ queryKey: ["keywords"] });
        setNotice("Đã lưu thay đổi.");
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [client],
  );
  const saveRank = useCallback(
    async (payload: RankPayload) => {
      await keywordWrite("/ranks", payload);
      await client.invalidateQueries({ queryKey: ["keywords"] });
    },
    [client],
  );
  const onDetail = useCallback((id: string) => setKeywordID(id), []);
  const onSelect = useCallback(
    (id: string) =>
      setSelected((old) => {
        const next = new Set(old);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    [],
  );
  const onBatch = useCallback((rows: RankPayload[]) => setBatch(rows), []);
  function exportReport(format: "csv" | "xlsx") {
    void action(() => keywordExport(query, format));
  }
  async function startSync(refresh = false) {
    if (!set) return;
    await client.cancelQueries({
      queryKey: ["keywords", `/gsc-sync/status?set_id=${set.id}`],
    });
    const job = await keywordWrite<KeywordJob>("/gsc-sync", {
      keyword_set_id: set.id,
      date_start: start,
      date_end: end,
      scope,
      refresh,
    });
    client.setQueryData(
      ["keywords", `/gsc-sync/status?set_id=${set.id}`],
      (old: KeywordJob[] | undefined) => [
        job,
        ...(old || []).filter((j) => j.id !== job.id),
      ],
    );
  }
  const rows = table.data?.rows || [];
  const selectedWeek = set?.weeks.find((w) => w.week_number === week);
  const batchErrors =
    batch?.flatMap((r, i) => {
      const error = rankError(r.value, profile?.config.search_depth || 100);
      return error ? [`Ô ${i + 1}, tuần ${r.week_number}: ${error}`] : [];
    }) || [];
  return (
    <div className="keyword-page">
      <div className="page-title-row">
        <div>
          <div className="eyebrow">QUAN SÁT THỰC TẾ · LỊCH SỬ RÕ RÀNG</div>
          <h1>
            Theo dõi từ khóa{" "}
            {selectedSite && (
              <span className="badge badge-neutral">
                {selectedSite.source_type === "mock"
                  ? "Website demo"
                  : selectedSite.source_type === "fixture"
                    ? "Property thử nghiệm"
                    : "Property GSC"}
              </span>
            )}
          </h1>
          <p>
            GSC cho hiệu suất query. Rank thủ công cho từng tuần, URL và Search
            Profile.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={!selectedSite}
          onClick={() => {
            setCreating((v) => !v);
            update({ tab: "sets" });
          }}
        >
          <Plus size={14} />
          Bộ từ khóa mới
        </Button>
      </div>
      {error && (
        <div role="alert" className="report-warning action-error">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="kw-notice">
          {notice}
        </div>
      )}
      {sites.isError ? (
        <ErrorState
          message={sites.error.message}
          onRetry={() => void sites.refetch()}
        />
      ) : sites.isPending ? (
        <DashboardSkeleton />
      ) : (
        <>
          <div className="technical-selection kw-selection">
            <label>
              Website
              <select
                aria-label="Website theo dõi từ khóa"
                value={site}
                onChange={(e) => {
                  update({
                    site: e.target.value,
                    set: "",
                    profile: "",
                    week: "",
                    page: "1",
                    group: "",
                  });
                  setCreating(false);
                }}
              >
                {site && !selectedSite && (
                  <option value={site}>Website không tồn tại</option>
                )}
                {sites.data?.map((s) => (
                  <option value={s.id} key={s.id}>
                    [{sourceLabel(s.source_type)}] {s.domain}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Bộ từ khóa
              <select
                aria-label="Bộ từ khóa"
                disabled={!sets.data?.length}
                value={setID}
                onChange={(e) =>
                  update({
                    set: e.target.value,
                    profile: "",
                    week: "",
                    page: "1",
                    group: "",
                  })
                }
              >
                <option value="">Chọn bộ</option>
                {sets.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.status === "archived" ? " · Lưu trữ" : ""}
                  </option>
                ))}
              </select>
            </label>
            {set && (
              <>
                <label>
                  Search Profile
                  <select
                    aria-label="Search Profile"
                    value={profile?.id || ""}
                    onChange={(e) => update({ profile: e.target.value })}
                  >
                    {set.profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Tuần theo dõi
                  <select
                    aria-label="Tuần theo dõi"
                    value={week}
                    onChange={(e) => update({ week: e.target.value })}
                  >
                    {Array.from(
                      { length: Math.max(35, week) },
                      (_, i) => i + 1,
                    ).map((n) => (
                      <option key={n} value={n}>
                        Tuần {n}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
          </div>
          {!selectedSite ? (
            <EmptyState
              title="Chọn website hợp lệ"
              detail="Chọn website demo hoặc property đã thêm trong Cài đặt."
            />
          ) : sets.isError ? (
            <ErrorState
              message={sets.error.message}
              onRetry={() => void sets.refetch()}
            />
          ) : sets.isPending ? (
            <DashboardSkeleton />
          ) : (
            <>
              {(creating || !sets.data?.length) && (
                <SetForm
                  key={site}
                  site={site}
                  busy={busy}
                  onSave={(body) =>
                    void action(async () => {
                      const created = await keywordWrite<KeywordSet>(
                        "/sets",
                        body,
                      );
                      setCreating(false);
                      update({
                        set: created.id,
                        profile: created.profiles[0].id,
                        week: "",
                        tab: "tracking",
                      });
                    })
                  }
                />
              )}
              {set && profile ? (
                <>
                  <div
                    className="analytics-tabs"
                    role="tablist"
                    aria-label="Theo dõi từ khóa"
                  >
                    {Object.entries(tabs).map(([key, label]) => (
                      <button
                        key={key}
                        role="tab"
                        aria-selected={tab === key}
                        onClick={() => update({ tab: key })}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="kw-context">
                    <span>
                      <Target size={14} />
                      Tuần {week} ·{" "}
                      {selectedWeek
                        ? `${selectedWeek.start_date} – ${selectedWeek.end_date}`
                        : "Lịch tuần sẽ tạo khi lưu"}{" "}
                      · {set.timezone}
                    </span>
                    <span>
                      {profile.config.location_label} · {profile.config.device}{" "}
                      · organic top {profile.config.search_depth}
                    </span>
                  </div>
                  {!["sets", "settings"].includes(tab) && (
                    <section className="card kw-gsc-controls">
                      <div className="technical-inline">
                        <strong>GSC · kỳ độc lập với tuần rank</strong>
                        <label>
                          Kỳ nhanh
                          <select
                            aria-label="Kỳ GSC từ khóa"
                            value={days}
                            onChange={(e) =>
                              update({
                                days: e.target.value,
                                start: shiftDate(
                                  end,
                                  -Number(e.target.value) + 1,
                                ),
                              })
                            }
                          >
                            {[7, 28, 90].map((n) => (
                              <option key={n} value={n}>
                                {n} ngày đã hoàn tất
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Từ ngày
                          <input
                            type="date"
                            aria-label="GSC từ ngày"
                            value={start}
                            max={end}
                            onChange={(e) => update({ start: e.target.value })}
                          />
                        </label>
                        <label>
                          Đến ngày
                          <input
                            type="date"
                            aria-label="GSC đến ngày"
                            value={end}
                            min={start}
                            max={status.data?.latest_final_date}
                            onChange={(e) => update({ end: e.target.value })}
                          />
                        </label>
                        <label>
                          Phạm vi
                          <select
                            aria-label="Phạm vi GSC từ khóa"
                            value={scope}
                            onChange={(e) =>
                              update({ scope: e.target.value, page: "1" })
                            }
                          >
                            <option value="property">
                              Query toàn property
                            </option>
                            <option value="page">Query theo URL đích</option>
                          </select>
                        </label>
                        <Button
                          size="sm"
                          disabled={
                            busy || !!active || !set.property_id || !valid
                          }
                          onClick={() => void action(() => startSync())}
                        >
                          <RefreshCw size={13} />
                          Đồng bộ GSC
                        </Button>
                      </div>
                      <p className="muted-copy">
                        {set.property_id
                          ? "Đọc cache SQLite; mặc định 28 ngày hoàn tất. Không có row không có nghĩa là 0. Cache dùng lại trong 6 giờ."
                          : "Website demo chưa kết nối GSC. Quản lý từ khóa và rank thủ công vẫn hoạt động; không có số liệu GSC giả."}{" "}
                        · Cột URL luôn là URL đích do bạn quản lý.
                      </p>
                      {jobs.data?.[0] && (
                        <div
                          className="technical-inline"
                          data-keyword-job={jobs.data[0].id}
                        >
                          <span role="status">
                            Sync: {jobs.data[0].status} ·{" "}
                            {jobs.data[0].completed}/{jobs.data[0].total}
                          </span>
                          {jobs.data[0].error && (
                            <span className="action-error">
                              {jobs.data[0].error}
                            </span>
                          )}
                          {active ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                void action(() =>
                                  keywordWrite(`/gsc-sync/${active.id}/cancel`),
                                )
                              }
                            >
                              Hủy sync
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy || !set.property_id}
                              onClick={() => void action(() => startSync(true))}
                            >
                              Làm mới từ API
                            </Button>
                          )}
                        </div>
                      )}
                    </section>
                  )}
                  {["tracking", "weekly"].includes(tab) && (
                    <>
                      <div className="kw-filterbar">
                        <label className="kw-search">
                          Tìm từ khóa / URL
                          <input
                            aria-label="Tìm từ khóa hoặc URL"
                            value={search}
                            placeholder="Nhập từ khóa hoặc URL…"
                            onChange={(e) => setSearch(e.target.value)}
                          />
                        </label>
                        <label>
                          Nhóm
                          <select
                            aria-label="Lọc nhóm từ khóa"
                            value={params.get("group") || ""}
                            onChange={(e) =>
                              update({ group: e.target.value, page: "1" })
                            }
                          >
                            <option value="">Tất cả nhóm</option>
                            {set.groups.map((g) => (
                              <option key={g.id} value={g.id}>
                                {g.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Trạng thái
                          <select
                            aria-label="Trạng thái từ khóa"
                            value={params.get("status") || "active"}
                            onChange={(e) =>
                              update({ status: e.target.value, page: "1" })
                            }
                          >
                            <option value="active">Đang theo dõi</option>
                            <option value="paused">Tạm dừng</option>
                            <option value="archived">Lưu trữ</option>
                            <option value="all">Tất cả</option>
                          </select>
                        </label>
                        <label>
                          Rank tuần {week}
                          <select
                            aria-label="Lọc rank"
                            value={params.get("rank") || ""}
                            onChange={(e) =>
                              update({ rank: e.target.value, page: "1" })
                            }
                          >
                            {[
                              ["", "Tất cả rank"],
                              ["top3", "Top 3"],
                              ["top10", "Top 10"],
                              ["top20", "Top 20"],
                              ["found", "Đã tìm thấy"],
                              ["na", "NA"],
                              ["unchecked", "Chưa kiểm tra"],
                            ].map(([v, l]) => (
                              <option key={v} value={v}>
                                {l}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Sắp xếp
                          <select
                            aria-label="Sắp xếp từ khóa"
                            value={params.get("sort") || "keyword"}
                            onChange={(e) =>
                              update({ sort: e.target.value, page: "1" })
                            }
                          >
                            {[
                              ["keyword", "Từ khóa"],
                              ["clicks", "Click"],
                              ["impressions", "Impression"],
                              ["position", "GSC Position"],
                              ["rank", "Rank tuần"],
                              ["change", "Biến động rank"],
                            ].map(([v, l]) => (
                              <option key={v} value={v}>
                                {l}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Chiều
                          <select
                            aria-label="Chiều sắp xếp"
                            value={params.get("direction") || "asc"}
                            onChange={(e) =>
                              update({ direction: e.target.value })
                            }
                          >
                            <option value="asc">Tăng dần</option>
                            <option value="desc">Giảm dần</option>
                          </select>
                        </label>
                      </div>
                      <details className="kw-advanced">
                        <summary>
                          Bộ lọc GSC, cột hiển thị và thời điểm kiểm tra
                        </summary>
                        <div className="kw-filterbar">
                          {[
                            ["min_clicks", "Click tối thiểu"],
                            ["min_impressions", "Impression tối thiểu"],
                            ["max_position", "GSC Position tối đa"],
                          ].map(([key, label]) => (
                            <label key={key}>
                              {label}
                              <input
                                aria-label={label}
                                type="number"
                                min={key === "max_position" ? 1 : 0}
                                value={params.get(key) || ""}
                                onChange={(e) =>
                                  update({ [key]: e.target.value, page: "1" })
                                }
                              />
                            </label>
                          ))}
                          {fixedColumns.map(([key, label]) => (
                            <label className="compare-control" key={key}>
                              <input
                                type="checkbox"
                                checked={visible.has(key)}
                                disabled={key === "keyword"}
                                onChange={() =>
                                  setVisible((old) => {
                                    const n = new Set(old);
                                    if (n.has(key)) n.delete(key);
                                    else n.add(key);
                                    return n;
                                  })
                                }
                              />
                              {label}
                            </label>
                          ))}
                        </div>
                      </details>
                      <div className="kw-observed-controls">
                        <label className="compare-control">
                          <input
                            type="checkbox"
                            checked={weekOnly}
                            onChange={(e) => setWeekOnly(e.target.checked)}
                          />
                          Nhập lịch sử: chỉ biết tuần, không có ngày giờ chính
                          xác
                        </label>
                        <label>
                          Thời điểm kiểm tra (giờ máy; để trống = hiện tại)
                          <input
                            type="datetime-local"
                            aria-label="Thời điểm kiểm tra"
                            value={checkedAt}
                            disabled={weekOnly}
                            onChange={(e) => setCheckedAt(e.target.value)}
                          />
                        </label>
                      </div>
                      <div className="kw-table-toolbar">
                        <div className="technical-inline">
                          <strong>{num(table.data?.total)} từ khóa</strong>
                          <Button size="sm" onClick={() => setAdding(true)}>
                            <Plus size={13} />
                            Thêm từ khóa
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={!rows.length}
                            onClick={() =>
                              setSelected(new Set(rows.map((r) => r.id)))
                            }
                          >
                            Chọn trang
                          </Button>
                          {selected.size > 0 && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setSelected(new Set())}
                            >
                              Bỏ chọn ({selected.size})
                            </Button>
                          )}
                        </div>
                        <div className="technical-inline">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => exportReport("csv")}
                          >
                            <Download size={13} />
                            CSV
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => exportReport("xlsx")}
                          >
                            XLSX
                          </Button>
                        </div>
                      </div>
                      {selected.size > 0 && (
                        <BulkMetadata
                          set={set}
                          selected={selected}
                          busy={busy}
                          onSave={(changes) =>
                            void action(async () => {
                              await keywordWrite("/keywords/bulk", {
                                ids: [...selected],
                                changes,
                              });
                              setSelected(new Set());
                            })
                          }
                        />
                      )}
                      {table.isError ? (
                        <ErrorState
                          message={table.error.message}
                          onRetry={() => void table.refetch()}
                        />
                      ) : table.isPending ? (
                        <DashboardSkeleton />
                      ) : tab === "tracking" ? (
                        <TrackingTable
                          rows={rows}
                          set={set}
                          profile={profile}
                          week={week}
                          onDetail={onDetail}
                          onSave={saveRank}
                          onBatch={onBatch}
                          selected={selected}
                          onSelect={onSelect}
                          visible={visible}
                          weekOnly={weekOnly}
                          checkedAt={checkedAt}
                        />
                      ) : (
                        <WeeklyCheck
                          key={setID + profile.id + week + query.get("page")}
                          rows={rows}
                          profile={profile}
                          week={week}
                          onSave={saveRank}
                          weekOnly={weekOnly}
                          checkedAt={checkedAt}
                        />
                      )}
                      <div className="kw-pagination">
                        <span>
                          {num(table.data?.total)} kết quả · trang{" "}
                          {query.get("page")}
                        </span>
                        <label>
                          Dòng/trang
                          <select
                            aria-label="Số dòng từ khóa"
                            value={query.get("page_size")!}
                            onChange={(e) =>
                              update({ size: e.target.value, page: "1" })
                            }
                          >
                            {[25, 50, 100].map((n) => (
                              <option key={n}>{n}</option>
                            ))}
                          </select>
                        </label>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={Number(query.get("page")) <= 1}
                          onClick={() =>
                            update({
                              page: String(Number(query.get("page")) - 1),
                            })
                          }
                        >
                          Trước
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={
                            Number(query.get("page")) *
                              Number(query.get("page_size")) >=
                            (table.data?.total || 0)
                          }
                          onClick={() =>
                            update({
                              page: String(Number(query.get("page")) + 1),
                            })
                          }
                        >
                          Sau
                        </Button>
                      </div>
                    </>
                  )}
                  {tab === "overview" &&
                    (overview.isError ? (
                      <ErrorState
                        message={overview.error.message}
                        onRetry={() => void overview.refetch()}
                      />
                    ) : overview.data ? (
                      <KeywordOverview
                        data={overview.data}
                        set={set}
                        week={week}
                      />
                    ) : (
                      <DashboardSkeleton />
                    ))}
                  {tab === "import" && (
                    <ImportExport
                      key={set.id + profile.id}
                      set={set}
                      profile={profile}
                      action={action}
                      busy={busy}
                      onImported={(id) =>
                        update({
                          set: id,
                          profile: "",
                          tab: "tracking",
                          page: "1",
                        })
                      }
                      onExport={exportReport}
                    />
                  )}
                  {tab === "sets" && !creating && (
                    <>
                      <SetForm
                        key={set.id + set.start_date + set.name}
                        site={site}
                        initial={set}
                        busy={busy}
                        onSave={(body) =>
                          void action(() =>
                            keywordWrite(`/sets/${set.id}`, body, "PATCH"),
                          )
                        }
                      />
                      <section className="card kw-form">
                        <h2>Các bộ của website</h2>
                        {sets.data?.map((s) => (
                          <div className="kw-set-row" key={s.id}>
                            <strong>{s.name}</strong>
                            <span>
                              {s.start_date} · {s.status}
                            </span>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                update({
                                  set: s.id,
                                  profile: "",
                                  week: "",
                                  group: "",
                                  page: "1",
                                })
                              }
                            >
                              Chọn bộ
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              onClick={() =>
                                void action(() =>
                                  keywordWrite(
                                    `/sets/${s.id}`,
                                    {
                                      status:
                                        s.status === "active"
                                          ? "archived"
                                          : "active",
                                    },
                                    "PATCH",
                                  ),
                                )
                              }
                            >
                              {s.status === "active" ? "Lưu trữ" : "Khôi phục"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `Xóa bộ “${s.name}”, mọi từ khóa và lịch sử rank? Không thể hoàn tác. Backup SQLite trước khi xóa.`,
                                  )
                                )
                                  void action(async () => {
                                    await keywordWrite(`/sets/${s.id}/delete`, {
                                      confirm: true,
                                    });
                                    update({
                                      set: "",
                                      profile: "",
                                      week: "",
                                      group: "",
                                    });
                                  });
                              }}
                            >
                              Xóa…
                            </Button>
                          </div>
                        ))}
                      </section>
                    </>
                  )}
                  {tab === "settings" && (
                    <>
                      <Groups set={set} action={action} busy={busy} />
                      <ProfileForm
                        key={profile.id + JSON.stringify(profile.config)}
                        set={set}
                        profile={profile}
                        busy={busy}
                        onSave={(body) =>
                          void action(() =>
                            keywordWrite(
                              `/profiles/${profile.id}`,
                              body,
                              "PATCH",
                            ),
                          )
                        }
                      />
                      <ProfileForm
                        set={set}
                        busy={busy}
                        onSave={(body) =>
                          void action(() => keywordWrite("/profiles", body))
                        }
                      />
                    </>
                  )}
                  <Sheet
                    open={adding}
                    onOpenChange={setAdding}
                    title="Thêm từ khóa"
                    description="Nhập từ khóa và URL đích. Rank mới bắt đầu ở trạng thái chưa kiểm tra."
                  >
                    <>
                      {error && (
                        <p role="alert" className="action-error">
                          {error}
                        </p>
                      )}
                      <KeywordForm
                        set={set}
                        busy={busy}
                        onSave={(body) =>
                          void action(async () => {
                            await keywordWrite("/keywords", body);
                            setAdding(false);
                          })
                        }
                      />
                    </>
                  </Sheet>
                  {keywordID && (
                    <KeywordDetail
                      key={keywordID}
                      id={keywordID}
                      set={set}
                      profile={profile}
                      metricsRow={rows.find((r) => r.id === keywordID)}
                      reportPeriod={`${start} – ${end}`}
                      close={() => setKeywordID("")}
                      action={action}
                      busy={busy}
                      error={error}
                    />
                  )}
                  <Sheet
                    open={!!batch}
                    onOpenChange={(open) => {
                      if (!open) setBatch(null);
                    }}
                    title="Xem trước nhập rank hàng loạt"
                    description="Kiểm tra toàn bộ khối dán trước khi lưu. Có một ô lỗi sẽ không ghi bất kỳ ô nào."
                  >
                    {error && (
                      <p role="alert" className="action-error">
                        {error}
                      </p>
                    )}
                    <p>
                      {batch?.length || 0} ô · Search Profile {profile.name}
                    </p>
                    {batchErrors.map((e, i) => (
                      <p key={i} role="alert" className="action-error">
                        {e}
                      </p>
                    ))}
                    <div className="kw-observation-list">
                      {batch?.slice(0, 100).map((r, i) => (
                        <p key={i}>
                          {
                            rows.find((k) => k.id === r.keyword_id)
                              ?.keyword_text
                          }{" "}
                          · Tuần {r.week_number}:{" "}
                          <strong>{r.value || "Xóa → Chưa kiểm tra"}</strong>
                        </p>
                      ))}
                    </div>
                    {(batch?.length || 0) > 500 && (
                      <p role="alert">
                        Tối đa 500 ô mỗi batch; chia khối nhỏ hơn.
                      </p>
                    )}
                    <Button
                      disabled={
                        busy ||
                        !!batchErrors.length ||
                        !batch?.length ||
                        batch.length > 500
                      }
                      onClick={() =>
                        void action(async () => {
                          await keywordWrite("/ranks/bulk", { rows: batch });
                          setBatch(null);
                        })
                      }
                    >
                      Xác nhận lưu toàn bộ rank
                    </Button>
                  </Sheet>
                </>
              ) : detail.isError ? (
                <ErrorState
                  message={detail.error.message}
                  onRetry={() => void detail.refetch()}
                />
              ) : setID ? (
                <DashboardSkeleton />
              ) : requested ? (
                <EmptyState
                  title="Không tìm thấy bộ từ khóa"
                  detail="Chọn lại bộ từ khóa thuộc website này."
                />
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
function Groups({
  set,
  action,
  busy,
}: {
  set: KeywordSet;
  action: (fn: () => Promise<unknown>) => Promise<void>;
  busy: boolean;
}) {
  return (
    <section className="card kw-form">
      <h2>Nhóm từ khóa</h2>
      <form
        className="technical-inline"
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const d = new FormData(form);
          void action(async () => {
            await keywordWrite("/groups", {
              keyword_set_id: set.id,
              name: d.get("name"),
              color: d.get("color"),
            });
            form.reset();
          });
        }}
      >
        <label>
          Tên nhóm
          <input
            name="name"
            aria-label="Tên nhóm mới"
            required
            maxLength={100}
          />
        </label>
        <label>
          Màu nhãn
          <input
            name="color"
            aria-label="Màu nhóm"
            type="color"
            defaultValue="#946447"
          />
        </label>
        <Button disabled={busy}>Thêm nhóm</Button>
      </form>
      {set.groups.map((g) => (
        <form
          key={g.id + g.name + g.color}
          className="technical-inline kw-group-edit"
          onSubmit={(e) => {
            e.preventDefault();
            const d = new FormData(e.currentTarget);
            void action(() =>
              keywordWrite(
                `/groups/${g.id}`,
                {
                  keyword_set_id: set.id,
                  name: d.get("name"),
                  color: d.get("color"),
                  sort_order: g.sort_order,
                },
                "PATCH",
              ),
            );
          }}
        >
          <input
            name="name"
            aria-label={`Tên nhóm ${g.name}`}
            defaultValue={g.name}
            required
            maxLength={100}
          />
          <input
            name="color"
            aria-label={`Màu nhóm ${g.name}`}
            type="color"
            defaultValue={g.color}
          />
          <Button size="sm" variant="outline" disabled={busy}>
            Lưu nhóm
          </Button>
        </form>
      ))}
    </section>
  );
}
function BulkMetadata({
  set,
  selected,
  busy,
  onSave,
}: {
  set: KeywordSet;
  selected: Set<string>;
  busy: boolean;
  onSave: (body: unknown) => void;
}) {
  const [field, setField] = useState("group_id");
  return (
    <form
      className="kw-bulk-bar"
      onSubmit={(e) => {
        e.preventDefault();
        const d = new FormData(e.currentTarget);
        onSave({
          [field]:
            field === "group_id" ? d.get("value") || null : d.get("value"),
        });
      }}
    >
      <strong>{selected.size} từ khóa</strong>
      <select
        aria-label="Trường sửa hàng loạt"
        value={field}
        onChange={(e) => setField(e.target.value)}
      >
        <option value="group_id">Nhóm</option>
        <option value="status">Trạng thái</option>
        <option value="priority">Ưu tiên</option>
        <option value="target_url">URL đích</option>
      </select>
      {field === "group_id" ? (
        <select name="value">
          <option value="">Chưa phân nhóm</option>
          {set.groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      ) : field === "status" || field === "priority" ? (
        <select key={field} name="value">
          {(field === "status"
            ? [
                ["active", "Đang theo dõi"],
                ["paused", "Tạm dừng"],
                ["archived", "Lưu trữ"],
              ]
            : [
                ["normal", "Bình thường"],
                ["high", "Cao"],
                ["low", "Thấp"],
              ]
          ).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      ) : (
        <input name="value" type="url" required placeholder="https://…" />
      )}
      <Button size="sm" disabled={busy}>
        Áp dụng cho các dòng đã chọn
      </Button>
    </form>
  );
}
