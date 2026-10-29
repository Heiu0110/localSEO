import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  BrainCircuit,
  ChevronRight,
  Info,
  Plus,
  Send,
  ShieldCheck,
  Star,
  Trash2,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import {
  DashboardSkeleton,
  EmptyState,
  ErrorState,
} from "../../components/ui/states";
import { aiQuery, aiWrite } from "../../services/aiApi";
import type {
  AIContext,
  AIConversation,
  AIConversationDetail,
  AIEstimate,
  AIProject,
  AIProviderState,
  AISettings,
} from "../../types/ai";
import { AgentMessage } from "./AgentChat";
import { ContextDrawer, EvidenceDrawer } from "./EvidenceDrawer";
import { AISettingsPanel, UsageSummary } from "./AISettingsPanel";
import { chatGPTQuery } from "./ChatGPTConnectionPanel";
import { money, stamp } from "./shared";
const suggestions = [
  "Phân tích hiệu suất SEO 28 ngày gần nhất.",
  "Tìm các URL mất traffic nhiều nhất.",
  "Từ khóa nào có nhiều impressions nhưng CTR thấp?",
  "Những trang quan trọng có lỗi kỹ thuật nào?",
  "Keyword nào đang tụt hạng theo tracking?",
  "Chủ đề nào trong Topical Map chưa có URL phù hợp?",
];
export function AIWorkspacePage() {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const latest = useRef(params);
  useEffect(() => {
    latest.current = params;
  }, [params]);
  const projectList = useQuery(aiQuery<AIProject[]>("/projects"));
  const requestedProject = params.get("project") || params.get("site");
  const project =
    projectList.data?.find((p) => p.id === requestedProject) ||
    (!requestedProject ? projectList.data?.[0] : undefined);
  const [historyPage, setHistoryPage] = useState(1);
  const [messagePage, setMessagePage] = useState(1);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"local_report" | "openai" | "chatgpt">(
    "local_report",
  );
  const [days, setDays] = useState(28);
  const [end, setEnd] = useState("");
  const [consent, setConsent] = useState(false);
  const [estimate, setEstimate] = useState<AIEstimate | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [contextOpen, setContextOpen] = useState(false);
  const [evidenceID, setEvidenceID] = useState("");
  const endOfChat = useRef<HTMLDivElement>(null);
  const pendingRequest = useRef<{ signature: string; key: string } | null>(
    null,
  );
  const tab = ["settings", "usage"].includes(params.get("tab") || "")
    ? params.get("tab")!
    : "chat";
  const conversations = useQuery(
    aiQuery<{ rows: AIConversation[]; total: number }>(
      `/conversations?project_id=${encodeURIComponent(project?.id || "")}&page=${historyPage}`,
      !!project,
    ),
  );
  const id = params.get("conversation") || "";
  const detailPath = `/conversations/${id}?project_id=${encodeURIComponent(project?.id || "")}&page=${messagePage}`;
  const detail = useQuery({
    ...aiQuery<AIConversationDetail>(detailPath, !!id && !!project),
    refetchInterval: (q) => (q.state.data?.active_turn ? 800 : false),
  });
  const conversation =
    detail.data?.conversation.project_id === project?.id
      ? detail.data
      : undefined;
  const running = !!conversation?.active_turn;
  const context = useQuery(
    aiQuery<AIContext>(
      `/projects/${encodeURIComponent(project?.id || "")}/context`,
      !!project,
    ),
  );
  const provider = useQuery(aiQuery<AIProviderState>("/settings"));
  const chatgpt = useQuery(chatGPTQuery());
  function update(values: Record<string, string>) {
    const next = new URLSearchParams(latest.current);
    for (const [k, v] of Object.entries(values))
      v ? next.set(k, v) : next.delete(k);
    latest.current = next;
    setParams(next);
  }
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await client.invalidateQueries({ queryKey: ["ai"] });
    } catch (e) {
      setError((e as Error).message);
      await client.invalidateQueries({ queryKey: ["ai"] });
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    setQuestion("");
    setConsent(false);
    setEstimate(null);
    setEvidenceID("");
    setMessagePage(1);
    setHistoryPage(1);
  }, [project?.id]);
  const loaded = useRef("");
  useEffect(() => {
    if (!conversation || loaded.current === id) return;
    loaded.current = id;
    const last = [...conversation.messages]
      .reverse()
      .find((m) => m.role === "assistant");
    setMode(conversation.conversation.provider);
    if (last) {
      setDays(last.data.window.days);
      setEnd(last.data.window.end_date || "");
    }
    setEstimate(null);
    setConsent(false);
  }, [conversation, id]);
  const completed = useRef("");
  useEffect(() => {
    if (!conversation) return;
    const sig = conversation.messages.map((m) => m.id + m.status).join();
    if (sig !== completed.current) {
      completed.current = sig;
      if (!conversation.active_turn) {
        void client.invalidateQueries({
          queryKey: [
            "ai",
            `/conversations?project_id=${encodeURIComponent(project?.id || "")}&page=${historyPage}`,
          ],
        });
        void client.invalidateQueries({ queryKey: ["ai", "/usage?page=1"] });
      }
      if (messagePage === 1)
        endOfChat.current?.scrollTo({
          behavior: "smooth",
          top: endOfChat.current.scrollHeight,
        });
    }
  }, [conversation, client, project?.id, historyPage, messagePage]);
  async function createConversation(titleOverride?: string) {
    if (!project) throw new Error("Chọn website trước.");
    const conv = await aiWrite<AIConversation>("/conversations", {
      project_id: project.id,
      provider: mode,
      title: titleOverride ?? (question.slice(0, 90) || "Phiên phân tích mới"),
    });
    loaded.current = conv.id;
    update({ conversation: conv.id, project: project.id, tab: "chat" });
    setMessagePage(1);
    client.setQueryData(
      [
        "ai",
        `/conversations/${conv.id}?project_id=${encodeURIComponent(project.id)}&page=1`,
      ],
      {
        conversation: conv,
        messages: [],
        total_messages: 0,
        page: 1,
        active_turn: null,
      },
    );
    return conv.id;
  }
  function body() {
    const mentioned = question.match(/\b(7|28|90)\s*ngày\b/iu);
    return {
      content: question.trim(),
      days: mentioned ? Number(mentioned[1]) : days,
      end_date: end || null,
      provider: mode,
      acknowledge_external_processing: consent,
      approved_model: estimate?.model || null,
      approved_connection_id:
        mode === "chatgpt" ? estimate?.connection_id || null : null,
      approved_max_estimate_usd: estimate?.turn_upper_estimate_usd ?? null,
      request_key: String(crypto.randomUUID()),
    };
  }
  async function send() {
    if (!question.trim() || !project) return;
    await action(async () => {
      const conv = id || (await createConversation());
      const data = body();
      setDays(data.days);
      const signature = JSON.stringify([
        conv,
        project.id,
        data.content,
        data.days,
        data.end_date,
        data.provider,
      ]);
      if (pendingRequest.current?.signature !== signature)
        pendingRequest.current = { signature, key: crypto.randomUUID() };
      data.request_key = pendingRequest.current.key;
      await client.cancelQueries({
        queryKey: [
          "ai",
          `/conversations/${conv}?project_id=${encodeURIComponent(project.id)}&page=1`,
        ],
      });
      await aiWrite(
        `/conversations/${conv}/messages?project_id=${encodeURIComponent(project.id)}`,
        data,
      );
      pendingRequest.current = null;
      setQuestion("");
      setConsent(false);
      setEstimate(null);
      setMessagePage(1);
      await client.invalidateQueries({ queryKey: ["ai"] });
    });
  }
  async function estimateCost() {
    await action(async () => {
      const conv = id || (await createConversation());
      setEstimate(
        await aiWrite<AIEstimate>(
          `/conversations/${conv}/estimate?project_id=${encodeURIComponent(project!.id)}`,
          body(),
        ),
      );
      setConsent(false);
    });
  }
  function chooseProject(value: string) {
    update({ project: value, site: "", conversation: "", tab: "chat" });
    loaded.current = "";
    setNotice(
      "Đã đổi website. Hội thoại cũ giữ nguyên ngữ cảnh; tạo/chọn phiên riêng cho website này.",
    );
  }
  const title = (
    <div className="page-title-row">
      <div>
        <div className="eyebrow">PHÂN TÍCH CÓ NGUỒN · CON NGƯỜI QUYẾT ĐỊNH</div>
        <h1>
          <BrainCircuit size={25} />
          AI Workspace
          <span className="badge badge-neutral">Phase 6 · chỉ đọc</span>
        </h1>
        <p>
          Đọc dữ liệu LocalSEO, phân biệt bằng chứng với suy luận và rà soát đề
          xuất.
        </p>
      </div>
      <Button
        variant="outline"
        onClick={() => setContextOpen(true)}
        disabled={!context.data}
      >
        <Info size={14} />
        Ngữ cảnh & nguồn
      </Button>
    </div>
  );
  return (
    <div className="ai-workspace">
      {title}
      <div className="ai-readonly">
        <ShieldCheck size={16} />
        <p>
          Agent không sửa website hoặc dữ liệu SEO. Duyệt đề xuất chỉ lưu
          review; chưa có publishing hay tự động hóa.
        </p>
      </div>
      {error && (
        <div role="alert" className="report-warning action-error">
          {error}
        </div>
      )}
      {notice && (
        <p role="status" className="ai-notice">
          {notice}
        </p>
      )}
      <div className="ai-toolbar">
        <label>
          Website / dự án
          <select
            aria-label="Website AI Workspace"
            value={project?.id || requestedProject || ""}
            onChange={(e) => chooseProject(e.target.value)}
            disabled={busy || !projectList.data?.length}
          >
            {requestedProject && !project && (
              <option value={requestedProject}>Dự án không tồn tại</option>
            )}
            {projectList.data?.map((p) => (
              <option value={p.id} key={p.id}>
                [
                {p.source_type === "mock"
                  ? "DEMO"
                  : p.source_type === "fixture"
                    ? "THỬ NGHIỆM"
                    : "ĐÃ LƯU"}
                ] {p.name}
              </option>
            ))}
          </select>
        </label>
        <div
          className="analytics-tabs"
          role="tablist"
          aria-label="AI Workspace"
        >
          <button
            role="tab"
            aria-selected={tab === "chat"}
            onClick={() => update({ tab: "chat" })}
          >
            Hội thoại
          </button>
          <button
            role="tab"
            aria-selected={tab === "settings"}
            onClick={() => update({ tab: "settings" })}
          >
            AI Settings
          </button>
          <button
            role="tab"
            aria-selected={tab === "usage"}
            onClick={() => update({ tab: "usage" })}
          >
            Usage & chi phí
          </button>
        </div>
      </div>
      {projectList.isPending ? (
        <DashboardSkeleton />
      ) : projectList.isError ? (
        <ErrorState
          message={projectList.error.message}
          onRetry={() => void projectList.refetch()}
        />
      ) : !project ? (
        <EmptyState
          title="Chưa chọn website hợp lệ"
          detail="Chọn website demo, GSC property hoặc dự án Technical SEO đã có."
        />
      ) : tab === "settings" ? (
        provider.isError ? (
          <ErrorState
            message={provider.error.message}
            onRetry={() => void provider.refetch()}
          />
        ) : provider.data ? (
          <AISettingsPanel
            key={JSON.stringify(provider.data)}
            data={provider.data}
            busy={busy}
            onRefresh={() => void provider.refetch()}
            onSave={(value: AISettings) =>
              void action(async () => {
                await aiWrite("/settings", value, "PATCH");
                setNotice("Đã lưu AI Settings. Không gửi request phân tích.");
              })
            }
            onTest={() =>
              void action(async () => {
                await aiWrite("/provider/test");
                setNotice(
                  "Đã kiểm tra key/quyền model. Không gửi nội dung để sinh câu trả lời.",
                );
              })
            }
          />
        ) : (
          <DashboardSkeleton />
        )
      ) : tab === "usage" ? (
        <UsageSummary />
      ) : (
        <div className="ai-layout">
          <aside className="card ai-history" aria-label="Lịch sử hội thoại">
            <Button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  setQuestion("");
                  await createConversation("Phiên phân tích mới");
                })
              }
            >
              <Plus size={14} />
              Hội thoại mới
            </Button>
            <h2>{project.name}</h2>
            {conversations.isError ? (
              <p className="action-error">{conversations.error.message}</p>
            ) : conversations.isPending ? (
              <p>Đang đọc lịch sử…</p>
            ) : conversations.data?.rows.length ? (
              conversations.data.rows.map((c) => (
                <div
                  className={`ai-history-row ${c.id === id ? "active" : ""}`}
                  key={c.id}
                >
                  <button
                    className="ai-history-title"
                    onClick={() => {
                      loaded.current = "";
                      update({ conversation: c.id });
                      setMessagePage(1);
                      setConsent(false);
                      setEstimate(null);
                    }}
                  >
                    <strong>{c.title}</strong>
                    <span>{stamp(c.updated_at)}</span>
                  </button>
                  <div>
                    <button
                      aria-label={`${c.saved ? "Bỏ lưu" : "Lưu phiên"} ${c.title}`}
                      title={c.saved ? "Bỏ lưu phiên" : "Lưu phiên"}
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          aiWrite(
                            `/conversations/${c.id}?project_id=${encodeURIComponent(project.id)}`,
                            { saved: !c.saved },
                            "PATCH",
                          ),
                        )
                      }
                    >
                      <Star
                        size={13}
                        fill={c.saved ? "currentColor" : "none"}
                      />
                    </button>
                    <button
                      aria-label={`Xóa phiên ${c.title}`}
                      disabled={busy || (c.id === id && running)}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Xóa hội thoại, bằng chứng tham chiếu và đề xuất của phiên? Usage vẫn giữ để kiểm soát ngân sách. Dữ liệu SEO không bị xóa.",
                          )
                        )
                          void action(async () => {
                            await aiWrite(
                              `/conversations/${c.id}/delete?project_id=${encodeURIComponent(project.id)}`,
                              { confirm: true },
                            );
                            if (id === c.id) update({ conversation: "" });
                          });
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-copy">
                Chưa có hội thoại. Bắt đầu bằng một câu hỏi cụ thể.
              </p>
            )}
            <div className="technical-inline">
              <Button
                size="sm"
                variant="ghost"
                disabled={historyPage === 1}
                onClick={() => setHistoryPage((p) => p - 1)}
              >
                Trước
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={historyPage * 30 >= (conversations.data?.total || 0)}
                onClick={() => setHistoryPage((p) => p + 1)}
              >
                Sau
              </Button>
            </div>
          </aside>
          <section className="card ai-chat-panel">
            <div className="ai-chat-heading">
              <div>
                <h2>
                  {conversation?.conversation.title ||
                    "Bắt đầu từ dữ liệu của website"}
                </h2>
                <p>
                  {project.site_url} · website của cuộc hội thoại được giữ cố
                  định
                </p>
              </div>
              {conversation && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    const name = window.prompt(
                      "Tên phiên",
                      conversation.conversation.title,
                    );
                    if (name?.trim())
                      void action(() =>
                        aiWrite(
                          `/conversations/${id}?project_id=${encodeURIComponent(project.id)}`,
                          { title: name.trim() },
                          "PATCH",
                        ),
                      );
                  }}
                >
                  Đổi tên
                </Button>
              )}
            </div>
            <div
              className="ai-chat-stream"
              ref={endOfChat}
              aria-label="Nội dung hội thoại"
            >
              {id && detail.isError ? (
                <ErrorState
                  message={detail.error.message}
                  onRetry={() => void detail.refetch()}
                />
              ) : id && detail.isPending ? (
                <p role="status">Đang tải hội thoại…</p>
              ) : !conversation?.messages.length ? (
                <div className="ai-welcome">
                  <BrainCircuit size={32} />
                  <h2>Điều bạn muốn điều tra hôm nay?</h2>
                  <p>
                    Bắt đầu bằng báo cáo theo quy tắc ngoại tuyến hoặc cấu hình
                    OpenAI. Mở trang không tự gọi AI trả phí.
                  </p>
                  <div>
                    {suggestions.map((s) => (
                      <button key={s} onClick={() => setQuestion(s)}>
                        {s}
                        <ChevronRight size={14} />
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {conversation.messages.map((m) => (
                    <AgentMessage
                      key={m.id}
                      message={m}
                      onEvidence={setEvidenceID}
                      busy={busy}
                      onReview={(rec, status, notes) =>
                        void action(async () => {
                          await aiWrite(
                            `/recommendations/${rec}?project_id=${encodeURIComponent(project.id)}`,
                            { approval_status: status, user_notes: notes },
                            "PATCH",
                          );
                          setNotice(
                            "Đã lưu review. Không có hành động nào được thực thi.",
                          );
                        })
                      }
                    />
                  ))}
                </>
              )}
            </div>
            {conversation && conversation.total_messages > 20 && (
              <div className="ai-message-pages">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={messagePage * 20 >= conversation.total_messages}
                  onClick={() => setMessagePage((p) => p + 1)}
                >
                  Tin cũ hơn
                </Button>
                <span>Trang {messagePage}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={messagePage === 1}
                  onClick={() => setMessagePage((p) => p - 1)}
                >
                  Tin mới hơn
                </Button>
              </div>
            )}
            <form
              className="ai-composer"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <div className="ai-compose-options">
                <label>
                  Chế độ
                  <select
                    aria-label="Chế độ phân tích AI"
                    value={mode}
                    disabled={running}
                    onChange={(e) => {
                      setMode(e.target.value as typeof mode);
                      setEstimate(null);
                      setConsent(false);
                    }}
                  >
                    <option value="local_report">
                      Báo cáo ngoại tuyến · không gọi AI
                    </option>
                    <option value="chatgpt">
                      ChatGPT · Plan Usage, không fallback trả phí
                    </option>
                    <option value="openai">
                      OpenAI · gửi dữ liệu có xác nhận
                    </option>
                  </select>
                </label>
                <label>
                  Kỳ báo cáo
                  <select
                    aria-label="Kỳ báo cáo AI"
                    value={days}
                    disabled={running}
                    onChange={(e) => {
                      setDays(Number(e.target.value));
                      setEstimate(null);
                      setConsent(false);
                    }}
                  >
                    {[7, 28, 90].map((n) => (
                      <option key={n} value={n}>
                        {n} ngày
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Ngày kết thúc (trống = dữ liệu mới nhất)
                  <input
                    type="date"
                    aria-label="Ngày kết thúc AI"
                    value={end}
                    disabled={running}
                    onChange={(e) => {
                      setEnd(e.target.value);
                      setEstimate(null);
                      setConsent(false);
                    }}
                  />
                </label>
              </div>
              <label className="sr-only" htmlFor="ai-question">
                Câu hỏi SEO
              </label>
              <textarea
                id="ai-question"
                aria-label="Câu hỏi SEO"
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setConsent(false);
                  setEstimate(null);
                }}
                maxLength={4000}
                disabled={running}
                placeholder="Hỏi về hiệu suất, URL, technical findings hoặc rank thủ công của website này…"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              {mode === "chatgpt" && (
                <div className="ai-cloud-consent">
                  <p>
                    ChatGPT Plan Usage ·{" "}
                    {chatgpt.data?.account?.name ||
                      chatgpt.data?.account?.email ||
                      "Chưa kết nối"}{" "}
                    · Model: {chatgpt.data?.selected_model || "Chưa chọn"}. Cấu
                    hình trong AI Settings. Hết hạn mức sẽ dừng, không dùng API
                    Key.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy || running || !question.trim()}
                    onClick={() => void estimateCost()}
                  >
                    Kiểm tra quyền và model ChatGPT cho lượt này
                  </Button>
                  {estimate?.provider === "chatgpt" && (
                    <>
                      <p role="status">
                        Model {estimate.model} · tối đa {estimate.max_calls}{" "}
                        request có giới hạn. Hạn mức ChatGPT còn lại chưa xác
                        định; không có ước tính USD hoặc tự chuyển sang API trả
                        phí.
                      </p>
                      <label className="ai-check">
                        <input
                          type="checkbox"
                          aria-label="Xác nhận gửi ChatGPT Plan Usage"
                          checked={consent}
                          onChange={(e) => setConsent(e.target.checked)}
                        />
                        Tôi đồng ý gửi câu hỏi, lịch sử ngắn và bằng chứng đến
                        OpenAI, sử dụng hạn mức ChatGPT của tài khoản/model đã
                        hiển thị cho lượt này.
                      </label>
                    </>
                  )}
                </div>
              )}
              {mode === "openai" && (
                <div className="ai-cloud-consent">
                  <p>
                    Chỉ gửi khi bạn đồng ý chuyển câu hỏi, lịch sử ngắn và bằng
                    chứng website đến OpenAI. Key không được gửi tới trình
                    duyệt.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy || running || !question.trim()}
                    onClick={() => void estimateCost()}
                  >
                    Xem ước tính lượt này
                  </Button>
                  {estimate && (
                    <>
                      <p role="status">
                        Model {estimate.model} · Dự phòng tối đa theo cấu hình:{" "}
                        <strong>
                          {money(estimate.turn_upper_estimate_usd)}
                        </strong>{" "}
                        · tối đa {estimate.max_calls} request. Ngày đã dùng{" "}
                        {money(estimate.daily_used_estimate_usd)} /{" "}
                        {money(estimate.daily_limit_usd)}. Đây không phải hóa
                        đơn hoặc billing cap.
                      </p>
                      {estimate.warning && (
                        <p className="action-error">
                          Lượt này vượt ngưỡng cảnh báo bạn cấu hình.
                        </p>
                      )}
                      <label className="ai-check">
                        <input
                          type="checkbox"
                          aria-label="Xác nhận gửi OpenAI"
                          checked={consent}
                          onChange={(e) => setConsent(e.target.checked)}
                        />
                        Tôi đồng ý gửi dữ liệu và chấp nhận ước tính cho lượt
                        này
                      </label>
                    </>
                  )}
                </div>
              )}
              <div className="ai-composer-footer">
                <span>
                  {running
                    ? "Lượt hiện tại đang phân tích…"
                    : mode === "local_report"
                      ? "Không dùng token, không cần Internet."
                      : "Cloud AI cần Internet và cấu hình riêng; không dùng tài khoản Codex."}
                </span>
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    running ||
                    !question.trim() ||
                    (mode === "openai" &&
                      (!consent || !estimate?.within_daily_limit)) ||
                    (mode === "chatgpt" &&
                      (!consent || estimate?.provider !== "chatgpt"))
                  }
                >
                  <Send size={14} />
                  {running ? "Đang phân tích…" : "Gửi phân tích"}
                </Button>
              </div>
            </form>
          </section>
        </div>
      )}
      <ContextDrawer
        open={contextOpen}
        context={context.data}
        onClose={() => setContextOpen(false)}
      />
      {evidenceID && project && (
        <EvidenceDrawer
          id={evidenceID}
          project={project.id}
          onClose={() => setEvidenceID("")}
        />
      )}
    </div>
  );
}
