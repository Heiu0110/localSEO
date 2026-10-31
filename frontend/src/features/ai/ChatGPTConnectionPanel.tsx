import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { ErrorState } from "../../components/ui/states";
import { aiQuery, aiWrite } from "../../services/aiApi";
import type { ChatGPTStatus } from "../../types/ai";
export const chatGPTQuery = () => ({
  ...aiQuery<ChatGPTStatus>("/chatgpt/status"),
  refetchInterval: (q: { state: { data?: ChatGPTStatus } }) =>
    q.state.data?.pending_authorization ? 1000 : 30000,
});
const labels: Record<string, string> = {
  not_connected: "Chưa kết nối",
  connected_authorized: "Đã kết nối · được cấp quyền Plan Usage",
  connected_not_authorized: "Connected — ChatGPT Plan Usage Not Authorized",
  token_expired_refresh_available:
    "Access token hết hạn · sẽ làm mới khi có yêu cầu",
  reauthorization_required: "Cần đăng nhập lại",
  waiting: "Đang chờ xác thực trên trình duyệt",
  exchanging: "Đang xác minh token",
  failed: "Đăng nhập chưa hoàn tất",
  completed: "Đã hoàn tất OAuth",
};
const stages: Record<string, string> = {
  callback_validation: "Kiểm tra callback",
  client_registration: "Xác nhận client đăng ký động",
  token_exchange: "Đổi authorization code lấy token",
  id_token_validation: "Xác minh ID token",
  credential_storage: "Lưu vào OS Credential Vault",
  model_listing: "Đọc model được cấp quyền",
};
export function ChatGPTConnectionPanel() {
  const localBrowser = ["127.0.0.1", "localhost"].includes(
    window.location.hostname,
  );
  const client = useQueryClient();
  const query = useQuery(chatGPTQuery());
  const data = query.data;
  const [eligibility, setEligibility] = useState(false),
    [localhost, setLocalhost] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [url, setURL] = useState(""),
    [message, setMessage] = useState(""),
    [model, setModel] = useState("");
  useEffect(() => {
    setModel(data?.selected_model || "");
  }, [data?.selected_model, data?.connection_id]);
  useEffect(() => {
    if (
      data?.authorization_status === "completed" ||
      data?.authorization_status === "failed"
    )
      setURL("");
  }, [data?.authorization_status]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Không hoàn tất kết nối ChatGPT.",
      );
    } finally {
      await client.invalidateQueries({ queryKey: ["ai"] });
      setBusy(false);
    }
  }
  if (query.isError)
    return (
      <ErrorState
        message={query.error.message}
        onRetry={() => void query.refetch()}
      />
    );
  if (!data) return <p>Đang đọc trạng thái ChatGPT…</p>;
  const modelListingFailed = data.model_listing_status === "failed" ||
    data.last_error?.stage === "model_listing";
  return (
    <section
      className="card ai-panel chatgpt-connection"
      aria-label="ChatGPT Connection"
    >
      <h2>ChatGPT Connection · Sign in with ChatGPT</h2>
      <p>
        Đăng nhập tài khoản đủ điều kiện để sử dụng ChatGPT Plan Usage. API Key
        Provider vẫn là phương thức riêng; không tự chuyển sang API trả phí khi
        hết hạn mức.
      </p>
      <div className="ai-badges">
        <span className="badge badge-neutral">
          {labels[data.status] || data.status}
        </span>
        {data.authorization_status === "failed" && (
          <span className="badge badge-neutral">Đăng nhập chưa hoàn tất</span>
        )}
        <span className="badge badge-neutral">
          {data.live_verification === "verified_for_this_session"
            ? "Đã nhận response.completed trong phiên này"
            : "Pending Live Verification"}
        </span>
      </div>
      {data.account && (
        <p>
          Tài khoản:{" "}
          <strong>
            {data.account.name || data.account.email || data.account.sub}
          </strong>
          {data.account.name && data.account.email
            ? " · " + data.account.email
            : ""}
        </p>
      )}
      {data.pending_authorization && (
        <p role="status">
          {labels[data.authorization_status] || "Đang xử lý OAuth…"} · mở trình
          duyệt trên cùng máy LocalSEO.
        </p>
      )}
      {(error || data.last_error) && (
        <div role="alert" className="report-warning">
          <div>
            <p>{error || data.last_error?.detail}</p>
            {modelListingFailed && data.plan_usage_authorized && (
              <p>Đã kết nối tài khoản; bước tải model chưa hoàn tất. Nhấn Lấy danh sách model ChatGPT để thử lại bằng phiên hiện tại.</p>
            )}
            {data.last_error && <p>Mã lỗi: <code>{data.last_error.code}</code>
              {data.last_error.stage && <> · Bước: {stages[data.last_error.stage] || "Xử lý kết nối ChatGPT"}</>}
            </p>}
            {data.last_error?.reason && <p>Chi tiết kiểm tra: <code>{data.last_error.reason}</code></p>}
          </div>
        </div>
      )}
      {message && <p role="status">{message}</p>}
      {!localBrowser && (
        <p className="report-warning">
          Đăng nhập loopback cần mở LocalSEO trên máy cá nhân tại localhost hoặc
          127.0.0.1; preview cloud không xác minh được callback này.
        </p>
      )}
      {!data.secure_storage_available && (
        <p className="report-warning">
          Chưa mở được OS Credential Vault. Kết nối ChatGPT cần kho khóa hệ điều
          hành; không có cách lưu token dạng văn bản.
        </p>
      )}
      <details>
        <summary>Điều kiện preview và localhost</summary>
        <p>{data.eligibility.note}</p>
        <p>
          Giấy phép ở thư mục gốc:{" "}
          {data.eligibility.repository_license_found
            ? "Có file, vẫn cần rà soát điều kiện"
            : "Chưa tìm thấy. Cần người sở hữu xác nhận tính phù hợp; ứng dụng không tự công bố giấy phép."}
        </p>
        {data.documentation.map((link, i) => (
          <p key={link}>
            <a href={link} target="_blank" rel="noopener noreferrer">
              {
                [
                  "SIWC Quickstart",
                  "Open-source / Locally hosted",
                  "Models & Inference",
                  "Preview Limitations",
                ][i]
              }
            </a>
          </p>
        ))}
        <p className="muted-copy">
          Contract triển khai theo bản handoff tài liệu ngày 29/10/2026. Danh
          sách giới hạn preview đầy đủ và eligibility thực tế vẫn cần đối chiếu;
          đăng ký động không yêu cầu client secret.
        </p>
      </details>
      <label className="ai-check">
        <input
          type="checkbox"
          aria-label="Xác nhận đã rà soát eligibility ChatGPT"
          checked={eligibility}
          onChange={(e) => setEligibility(e.target.checked)}
        />
        Tôi đã rà soát điều kiện OSS/locally hosted, quyền sử dụng mã nguồn và
        đủ điều kiện để thử kết nối.
      </label>
      <label className="ai-check">
        <input
          type="checkbox"
          aria-label="Trình duyệt cùng máy LocalSEO"
          checked={localhost}
          onChange={(e) => setLocalhost(e.target.checked)}
        />
        Tôi đang mở trình duyệt trên cùng máy chạy backend LocalSEO.
      </label>
      <div className="technical-inline">
        <Button
          disabled={
            busy ||
            data.pending_authorization ||
            !eligibility ||
            !localhost ||
            !data.secure_storage_available ||
            !localBrowser
          }
          onClick={() => {
            const popup = window.open("about:blank", "_blank");
            if (popup) popup.opener = null;
            void action(async () => {
              try {
                const r = await aiWrite<{ authorization_url: string }>(
                  "/chatgpt/connect",
                  {
                    eligibility_acknowledged: eligibility,
                    localhost_acknowledged: localhost,
                  },
                );
                setURL(r.authorization_url);
                if (popup) popup.location.replace(r.authorization_url);
              } catch (e) {
                popup?.close();
                throw e;
              }
            });
          }}
        >
          Continue with ChatGPT
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          aria-busy={busy || query.isFetching}
          onClick={() =>
            void action(async () => {
              const result = await query.refetch({ throwOnError: true });
              const current = result.data;
              if (current?.last_error?.stage === "model_listing" && current?.plan_usage_authorized)
                setMessage("Đã kiểm tra: tài khoản đã kết nối, nhưng chưa tải được danh sách model. Nhấn Lấy danh sách model ChatGPT để thử lại; không cần đăng nhập lại.");
              else if (current?.last_error || current?.authorization_status === "failed")
                setMessage("Đã kiểm tra: đăng nhập chưa hoàn tất. Xem mã lỗi và bước xử lý ở trên; dùng Continue with ChatGPT để bắt đầu lượt mới.");
              else if (current?.pending_authorization)
                setMessage("Đã kiểm tra: đang chờ đăng nhập. Hoàn tất ở tab OpenAI trên cùng máy LocalSEO.");
              else if (current?.account)
                setMessage(`Đã kiểm tra: ${labels[current.status] || "đã có kết nối ChatGPT"}.`);
              else
                setMessage("Đã kiểm tra: chưa có kết nối hoặc kết quả đăng nhập. Nếu backend đã khởi động lại, nhấn Continue with ChatGPT để tạo phiên mới; không tải lại callback cũ.");
            })
          }
        >
          Làm mới trạng thái ChatGPT
        </Button>
        <Button
          variant="outline"
          disabled={busy || (!data.account && !data.pending_authorization && !data.last_error && data.secure_storage_available)}
          onClick={() =>
            void action(async () => {
              const r = await aiWrite<{ message: string }>(
                "/chatgpt/disconnect",
                { confirm: true, revoke: true },
              );
              setURL("");
              setMessage(r.message);
            })
          }
        >
          Disconnect ChatGPT
        </Button>
      </div>
      {url && data.pending_authorization && (
        <p>
          <a href={url} target="_blank" rel="noopener noreferrer">
            Tiếp tục đến trang đăng nhập ChatGPT nếu trình duyệt chặn cửa sổ mới
          </a>
        </p>
      )}
      {data.status === "connected_not_authorized" && (
        <p className="report-warning">
          Đã xác minh tài khoản nhưng thiếu quyền{" "}
          <code>chatgpt.tokens.use.direct</code>. Không thể chạy inference bằng
          hạn mức ChatGPT.
        </p>
      )}
      <p className="muted-copy">{data.quota.note}</p>
      <div className="ai-form-grid">
        <label>
          Model ChatGPT của tài khoản
          <select
            aria-label="Model ChatGPT của tài khoản"
            value={model}
            disabled={busy || !data.plan_usage_authorized}
            onChange={(e) => setModel(e.target.value)}
          >
            <option value="">Chọn model khả dụng</option>
            {data.models.map((m) => (
              <option key={m.slug} value={m.slug}>
                {m.display_name} · {m.slug}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="technical-inline">
        <Button
          variant="outline"
          disabled={busy || !data.plan_usage_authorized}
          onClick={() =>
            void action(async () => {
              const refreshed = await aiWrite<ChatGPTStatus>("/chatgpt/models/refresh");
              client.setQueryData(["ai", "/chatgpt/status"], refreshed);
              setMessage(refreshed.models.length
                ? `Đã tải ${refreshed.models.length} model ChatGPT khả dụng. Chọn model và nhấn Lưu model ChatGPT; chưa gửi inference.`
                : "Đã tải danh sách model, nhưng OpenAI chưa trả model visibility=list cho tài khoản này.");
            })
          }
        >
          Lấy danh sách model ChatGPT
        </Button>
        <Button
          disabled={busy || !model || !data.plan_usage_authorized}
          onClick={() =>
            void action(async () => {
              await aiWrite("/chatgpt/model", { slug: model }, "PATCH");
              setMessage("Đã chọn model ChatGPT. Chưa gửi inference.");
            })
          }
        >
          Lưu model ChatGPT
        </Button>
      </div>
      {data.models.length === 0 && modelListingFailed && data.plan_usage_authorized ? (
        <p>Chưa tải được danh sách model; chưa thể kết luận tài khoản không có model khả dụng.</p>
      ) : data.models.length === 0 && data.plan_usage_authorized && data.model_listing_status !== "empty" ? (
        <p>Chưa tải danh sách model cho kết nối này. Nhấn Lấy danh sách model ChatGPT để đọc model được cấp quyền.</p>
      ) : data.models.length === 0 && (
        <p>
          Chưa có model <code>visibility=list</code> cho kết nối này. Không dùng
          mặc định model của API Key Provider.
        </p>
      )}
      <p className="muted-copy">
        Responses dùng streaming, chỉ hoàn tất sau{" "}
        <code>response.completed</code>. Giới hạn output tokens và giá USD phía
        dưới chỉ áp dụng API Key Provider; SIWC không gửi các tham số đó. Các
        giới hạn tools/ngữ cảnh chung vẫn được áp dụng.
      </p>
    </section>
  );
}
