import { ChatGPTConnectionPanel } from "./ChatGPTConnectionPanel";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { ErrorState } from "../../components/ui/states";
import { aiQuery } from "../../services/aiApi";
import type { AIProviderState, AISettings, AIUsage } from "../../types/ai";
import { money, stamp, textLabel } from "./shared";
export function AISettingsPanel({
  data,
  busy,
  onSave,
  onTest,
  onRefresh,
}: {
  data: AIProviderState;
  busy: boolean;
  onSave: (value: AISettings) => void;
  onTest: () => void;
  onRefresh: () => void;
}) {
  const cfg = data.settings;
  return (
    <div className="ai-settings">
      <ChatGPTConnectionPanel />
      <section className="card ai-panel">
        <h2>OpenAI API Key Provider · cấu hình tại localhost</h2>
        <div className="ai-badges">
          <span className="badge badge-neutral">
            {data.key_configured
              ? "Đã có key trong OS keyring"
              : "Chưa có API key"}
          </span>
          <span className="badge badge-neutral">
            {data.model_validated
              ? "Model đã kiểm tra quyền"
              : "Chưa kiểm tra model"}
          </span>
        </div>
        <Button variant="outline" size="sm" disabled={busy} onClick={onRefresh}>
          Làm mới trạng thái key
        </Button>
        <p>
          API key chỉ nhập tại terminal, không đi qua JavaScript/frontend, không
          lưu SQLite hoặc file văn bản.
        </p>
        <p className="muted-copy">
          Trong thư mục dự án, dùng Python của backend:
        </p>
        <pre className="ai-command">
          backend\.venv\Scripts\python.exe scripts\configure_ai_provider.py
        </pre>
        <p className="muted-copy">
          Linux/macOS:{" "}
          <code>backend/.venv/bin/python scripts/configure_ai_provider.py</code>
          . Xóa key bằng cùng lệnh thêm <code>--remove-key</code>.
        </p>
        {!data.secure_storage_available && (
          <p className="report-warning">
            Môi trường hiện chưa mở được kho khóa hệ điều hành. Chế độ báo cáo
            ngoại tuyến vẫn dùng được; không có fallback lưu key dạng văn bản.
          </p>
        )}
        <p>
          <a
            href={data.model_reference}
            target="_blank"
            rel="noopener noreferrer"
          >
            Model ID trong SDK OpenAI chính thức
          </a>{" "}
          ·{" "}
          <a
            href={data.pricing_reference}
            target="_blank"
            rel="noopener noreferrer"
          >
            Kiểm tra bảng giá chính thức
          </a>
        </p>
        <p className="report-warning">
          {data.pricing_note} Codex và model chạy trong ứng dụng là hai cấu hình
          khác nhau.
        </p>
      </section>
      <form
        className="card ai-panel"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const number = (key: string) => Number(form.get(key));
          onSave({
            enabled: form.get("enabled") === "on",
            model: String(form.get("model")),
            max_tool_calls: number("max_tool_calls"),
            max_context_bytes: number("max_context_bytes"),
            max_output_tokens: number("max_output_tokens"),
            daily_limit_usd: number("daily_limit_usd"),
            warning_usd: number("warning_usd"),
            input_usd_per_million: form.get("input_usd_per_million")
              ? number("input_usd_per_million")
              : null,
            output_usd_per_million: form.get("output_usd_per_million")
              ? number("output_usd_per_million")
              : null,
            pricing_reviewed_on:
              String(form.get("pricing_reviewed_on") || "") || null,
          });
        }}
      >
        <h2>Giới hạn và giá ước tính của model</h2>
        <div className="ai-form-grid">
          <label>
            Model ID
            <input
              name="model"
              aria-label="Model AI"
              defaultValue={cfg.model}
              required
              maxLength={100}
            />
          </label>
          <label>
            Số tool tối đa/lượt
            <input
              name="max_tool_calls"
              type="number"
              min="1"
              max="8"
              defaultValue={cfg.max_tool_calls}
              required
            />
          </label>
          <label>
            Ngữ cảnh tối đa (UTF-8 byte)
            <input
              name="max_context_bytes"
              type="number"
              min="16000"
              max="96000"
              defaultValue={cfg.max_context_bytes}
              required
            />
          </label>
          <label>
            Output tokens tối đa/request
            <input
              name="max_output_tokens"
              type="number"
              min="500"
              max="4000"
              defaultValue={cfg.max_output_tokens}
              required
            />
          </label>
          <label>
            Ngân sách ngày ước tính (USD)
            <input
              name="daily_limit_usd"
              type="number"
              step="0.01"
              min="0.01"
              max="100"
              defaultValue={cfg.daily_limit_usd}
              required
            />
          </label>
          <label>
            Ngưỡng cảnh báo/lượt (USD)
            <input
              name="warning_usd"
              type="number"
              step="0.001"
              min="0"
              max="10"
              defaultValue={cfg.warning_usd}
              required
            />
          </label>
          <label>
            USD / 1 triệu input tokens
            <input
              name="input_usd_per_million"
              aria-label="Giá input AI"
              type="number"
              step="any"
              min="0"
              max="1000"
              defaultValue={cfg.input_usd_per_million ?? ""}
            />
          </label>
          <label>
            USD / 1 triệu output tokens
            <input
              name="output_usd_per_million"
              aria-label="Giá output AI"
              type="number"
              step="any"
              min="0"
              max="10000"
              defaultValue={cfg.output_usd_per_million ?? ""}
            />
          </label>
          <label>
            Ngày bạn kiểm tra giá
            <input
              name="pricing_reviewed_on"
              type="date"
              defaultValue={cfg.pricing_reviewed_on || ""}
            />
          </label>
        </div>
        <label className="ai-check">
          <input
            type="checkbox"
            name="enabled"
            aria-label="Bật OpenAI"
            defaultChecked={cfg.enabled}
          />
          Bật API Key Provider cho các lượt gửi có xác nhận riêng
        </label>
        <p className="muted-copy">
          Giá vẫn là ước tính do bạn cấu hình, không phải giá/billing do
          provider xác nhận. Request chưa rõ usage giữ khoản dự phòng. Tắt
          OpenAI sẽ chặn request tiếp theo; không hoàn tác request đã gửi.
        </p>
        <div className="technical-inline">
          <Button disabled={busy}>Lưu AI Settings</Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy || !data.key_configured}
            onClick={onTest}
          >
            Kiểm tra key/model (không sinh nội dung)
          </Button>
        </div>
      </form>
      <section className="card ai-panel">
        <h2>Phạm vi Phase 6</h2>
        <p>
          Agent chỉ đọc dữ liệu theo website; chỉ ghi hội thoại, bằng chứng tham
          chiếu, usage và review. Không có CMS, social, Google Business Profile,
          SERP scraping, nghiên cứu web hoặc lịch chạy AI nền.
        </p>
        <p className="muted-copy">
          Topical Map hiện chưa triển khai trong repo. Báo cáo ngoại tuyến là
          quy tắc tính từ dữ liệu lưu, không phải LLM chạy offline.
        </p>
      </section>
    </div>
  );
}
export function UsageSummary() {
  const [page, setPage] = useState(1);
  const query = useQuery(aiQuery<AIUsage>(`/usage?page=${page}`));
  return query.isError ? (
    <ErrorState
      message={query.error.message}
      onRetry={() => void query.refetch()}
    />
  ) : !query.data ? (
    <p role="status">Đang đọc usage…</p>
  ) : (
    <section className="card ai-panel">
      <h2>Token và chi phí ước tính</h2>
      <p>
        Ngân sách USD chỉ áp dụng API Key Provider. ChatGPT Plan Usage dùng hạn
        mức tài khoản; ứng dụng chưa có số dư hạn mức hoặc giá USD cho phương
        thức này.
      </p>
      <p>
        Ngày ({query.data.day_timezone}):{" "}
        <strong>{money(query.data.daily_used_estimate_usd)}</strong> /{" "}
        {money(query.data.daily_limit_usd)}
      </p>
      <p className="report-warning">{query.data.note}</p>
      <div className="ai-data-scroll">
        <table>
          <thead>
            <tr>
              <th>Thời điểm</th>
              <th>Model</th>
              <th>Trạng thái</th>
              <th>Input tokens</th>
              <th>Output tokens</th>
              <th>USD ước tính/dự phòng</th>
            </tr>
          </thead>
          <tbody>
            {query.data.rows.map((u) => (
              <tr key={u.id}>
                <td>{stamp(u.created_at)}</td>
                <td>
                  {u.model}
                  <small>
                    {u.provider === "chatgpt"
                      ? "ChatGPT Plan Usage"
                      : u.provider}
                  </small>
                </td>
                <td>{textLabel(u.status)}</td>
                <td>{u.input_tokens ?? "—"}</td>
                <td>{u.output_tokens ?? "—"}</td>
                <td>
                  {u.provider === "chatgpt"
                    ? "Hạn mức ChatGPT · chưa có số dư"
                    : money(u.estimated_cost_usd ?? u.reserved_usd)}
                  {u.estimated_cost_usd == null ? " · dự phòng" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!query.data.rows.length && (
        <p className="muted-copy">
          Chưa có request cloud AI được ghi nhận. Báo cáo theo quy tắc không
          dùng token.
        </p>
      )}
      <div className="technical-inline">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Trước
        </Button>
        <span>Trang {page}</span>
        <Button
          variant="outline"
          size="sm"
          disabled={page * 20 >= query.data.total}
          onClick={() => setPage((p) => p + 1)}
        >
          Sau
        </Button>
      </div>
    </section>
  );
}
import { useState } from "react";
