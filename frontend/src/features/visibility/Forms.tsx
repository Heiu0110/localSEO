import { useState, type ReactNode } from "react";
import { Button } from "../../components/ui/button";
import type { AIProject } from "../../types/ai";
import type {
  VisibilityProject,
  VisibilityEntity,
  VisibilityPrompt,
  VisibilityObservation,
  VisibilityReferences,
  VisibilityDocument,
} from "../../types/visibility";
import { Field, text, lines, categories } from "./shared";
import { intents, Options } from "../research/shared";
type Save = (value: Record<string, unknown>) => Promise<void>;
function Form({
  save,
  busy,
  children,
  label = "Lưu",
}: {
  save: (f: FormData) => Promise<void>;
  busy: boolean;
  children: ReactNode;
  label?: string;
}) {
  const [error, setError] = useState("");
  return (
    <form
      className="visibility-form"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        setError("");
        void save(f).catch((err) =>
          setError(
            err instanceof SyntaxError
              ? "JSON chưa hợp lệ; kiểm tra cấu trúc và dấu ngoặc."
              : err instanceof Error
                ? err.message
                : "Không thể lưu.",
          ),
        );
      }}
    >
      {children}
      {error && (
        <p role="alert" className="action-error">
          {error}
        </p>
      )}
      <Button type="submit" disabled={busy}>
        {busy ? "Đang lưu…" : label}
      </Button>
    </form>
  );
}
export function ProjectForm({
  sites,
  busy,
  onSave,
  initial,
}: {
  sites: AIProject[];
  busy: boolean;
  onSave: Save;
  initial?: VisibilityProject;
}) {
  return (
    <Form
      busy={busy}
      save={async (f) =>
        onSave(
          initial
            ? {
                name: text(f, "name"),
                description: text(f, "description"),
                research_goal: text(f, "goal"),
                status: text(f, "status"),
              }
            : {
                local_project_id: text(f, "site"),
                name: text(f, "name"),
                country: text(f, "country"),
                language: text(f, "language"),
                description: text(f, "description"),
                research_goal: text(f, "goal"),
              },
        )
      }
    >
      {!initial && (
        <Field label="Website hiện có">
          <select name="site" aria-label="Website Visibility" required>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                [{s.source_type}] {s.name}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field label="Tên dự án">
        <input
          name="name"
          required
          maxLength={200}
          defaultValue={initial?.name}
        />
      </Field>
      {!initial && (
        <div className="visibility-form-grid">
          <Field label="Quốc gia dự án">
            <input
              name="country"
              defaultValue="VN"
              required
              pattern="[A-Z]{2}"
            />
          </Field>
          <Field label="Ngôn ngữ dự án">
            <input name="language" defaultValue="vi" required />
          </Field>
        </div>
      )}
      <Field label="Mô tả">
        <textarea
          name="description"
          maxLength={2000}
          defaultValue={initial?.description}
        />
      </Field>
      <Field label="Mục tiêu nghiên cứu">
        <textarea
          name="goal"
          maxLength={2000}
          defaultValue={initial?.research_goal}
        />
      </Field>
      {initial && (
        <Field label="Trạng thái dự án">
          <select name="status" defaultValue={initial.status}>
            <option value="active">Đang dùng</option>
            <option value="archived">Lưu trữ</option>
          </select>
        </Field>
      )}
    </Form>
  );
}
export function EntityForm({
  initial,
  kind,
  busy,
  onSave,
}: {
  initial?: VisibilityEntity;
  kind: "brand" | "competitor";
  busy: boolean;
  onSave: Save;
}) {
  const config = initial?.config;
  const [advanced, setAdvanced] = useState(!!initial);
  const [domains, setDomains] = useState(
    config?.domains.length
      ? config.domains
      : [{ domain: "", include_subdomains: false }],
  );
  return (
    <Form
      busy={busy}
      save={async (f) =>
        onSave({
          kind: initial?.kind || kind,
          name: text(f, "name"),
          ambiguous: f.has("ambiguous"),
          aliases: advanced
            ? JSON.parse(text(f, "advanced") || "[]")
            : lines(f, "aliases").map((name) => ({
                name,
                ambiguous: f.has("alias_ambiguous"),
                context_terms: lines(f, "context"),
                negative_terms: lines(f, "negative"),
              })),
          domains: domains
            .filter((d) => d.domain.trim())
            .map((d) => ({ ...d, domain: d.domain.trim() })),
          social_profiles: lines(f, "social"),
          category: text(f, "category"),
          competitor_type: text(f, "type") || "direct",
          notes: text(f, "notes"),
        })
      }
    >
      <p>
        Chỉ khai báo tên/alias và domain đã xác nhận. Domain khác phần đuôi hoặc
        subdomain không tự có cùng ownership.
      </p>
      <Field label={kind === "brand" ? "Tên brand chính" : "Tên đối thủ"}>
        <input
          name="name"
          required
          maxLength={160}
          defaultValue={initial?.name}
        />
      </Field>
      <label className="visibility-check">
        <input
          type="checkbox"
          name="ambiguous"
          defaultChecked={config?.ambiguous}
        />
        Tên chính là từ chung, cần review ngữ cảnh
      </label>
      <label className="visibility-check">
        <input
          type="checkbox"
          checked={advanced}
          onChange={(e) => setAdvanced(e.target.checked)}
        />
        Dùng cấu hình alias JSON nâng cao (giữ kind/ngữ cảnh riêng)
      </label>
      {!advanced && (
        <>
          <Field label="Aliases / tên cũ / tên sản phẩm (mỗi dòng một tên)">
            <textarea
              name="aliases"
              defaultValue={config?.aliases.map((a) => a.name).join("\n")}
            />
          </Field>
          <label className="visibility-check">
            <input type="checkbox" name="alias_ambiguous" />
            Các alias mới có thể mơ hồ
          </label>
          <div className="visibility-form-grid">
            <Field label="Ngữ cảnh xác nhận alias (mỗi dòng)">
              <textarea name="context" />
            </Field>
            <Field label="Ngữ cảnh loại trừ alias (mỗi dòng)">
              <textarea name="negative" />
            </Field>
          </div>
        </>
      )}
      {advanced && (
        <Field label="Alias JSON">
          <textarea
            name="advanced"
            rows={7}
            defaultValue={
              config ? JSON.stringify(config.aliases, null, 2) : "[]"
            }
          />
        </Field>
      )}
      <fieldset>
        <legend>Domain sở hữu đã xác nhận</legend>
        {domains.map((d, i) => (
          <div className="visibility-domain" key={i}>
            <input
              aria-label={`Domain ${i + 1}`}
              value={d.domain}
              placeholder="example.com"
              onChange={(e) =>
                setDomains((rows) =>
                  rows.map((row, n) =>
                    n === i ? { ...row, domain: e.target.value } : row,
                  ),
                )
              }
            />
            <label className="visibility-check">
              <input
                type="checkbox"
                checked={d.include_subdomains}
                onChange={(e) =>
                  setDomains((rows) =>
                    rows.map((row, n) =>
                      n === i
                        ? { ...row, include_subdomains: e.target.checked }
                        : row,
                    ),
                  )
                }
              />
              Bao gồm subdomain
            </label>
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                setDomains((rows) => rows.filter((_, n) => n !== i))
              }
            >
              Xóa dòng
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={domains.length >= 20}
          onClick={() =>
            setDomains((rows) => [
              ...rows,
              { domain: "", include_subdomains: false },
            ])
          }
        >
          Thêm domain
        </Button>
      </fieldset>
      <Field label="Profile xã hội đã xác nhận (URL đầy đủ, mỗi dòng)">
        <textarea
          name="social"
          defaultValue={config?.social_profiles.join("\n")}
        />
      </Field>
      <div className="visibility-form-grid">
        <Field label="Nhóm thương hiệu">
          <input name="category" defaultValue={config?.category} />
        </Field>
        <Field label="Loại đối thủ">
          <input
            name="type"
            defaultValue={config?.competitor_type || "direct"}
          />
        </Field>
      </div>
      <Field label="Ghi chú entity">
        <textarea name="notes" maxLength={2000} defaultValue={config?.notes} />
      </Field>
      {initial && (
        <p>
          Thay cấu hình không âm thầm đổi lịch sử. Mở quan sát và tạo revision
          nhận diện mới khi cần.
        </p>
      )}
    </Form>
  );
}
export function PromptForm({
  initial,
  refs,
  busy,
  onSave,
}: {
  initial?: VisibilityPrompt;
  refs: VisibilityReferences;
  busy: boolean;
  onSave: Save;
}) {
  return (
    <Form
      busy={busy}
      save={async (f) =>
        onSave({
          text: text(f, "text"),
          topic: text(f, "topic"),
          category: text(f, "category"),
          intent: text(f, "intent"),
          cohort_type: text(f, "cohort_type"),
          priority: Number(text(f, "priority")),
          status: text(f, "status"),
          country: text(f, "country"),
          language: text(f, "language"),
          location: text(f, "location") || null,
          buyer_stage: text(f, "buyer_stage"),
          source: text(f, "source"),
          research_keyword_ids: f.getAll("keywords").map(String),
          research_cluster_id: text(f, "cluster") || null,
          tracking_keyword_id: text(f, "tracking") || null,
          target_url: text(f, "url") || null,
          notes: text(f, "notes"),
        })
      }
    >
      <Field label="Nội dung prompt">
        <textarea
          name="text"
          required
          maxLength={2000}
          defaultValue={initial?.text}
        />
      </Field>
      <div className="visibility-form-grid">
        <Field label="Chủ đề">
          <input name="topic" defaultValue={initial?.topic} />
        </Field>
        <Field label="Danh mục prompt">
          <select
            name="category"
            defaultValue={initial?.category || categories[0]}
          >
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label="Search Intent">
          <select name="intent" defaultValue={initial?.intent || "unknown"}>
            <Options values={intents} />
          </select>
        </Field>
        <Field label="Loại cohort">
          <select
            name="cohort_type"
            defaultValue={initial?.cohort_type || "neutral"}
          >
            <option value="neutral">Khám phá trung lập</option>
            <option value="commercial_discovery">Khám phá thương mại</option>
            <option value="brand_specific">Có brand trong prompt</option>
          </select>
        </Field>
        <Field label="Ưu tiên prompt">
          <select name="priority" defaultValue={initial?.priority ?? 1}>
            <option value="0">0 · thấp</option>
            <option value="1">1 · thường</option>
            <option value="2">2 · ưu tiên</option>
            <option value="3">3 · business critical</option>
          </select>
        </Field>
        <Field label="Trạng thái prompt">
          <select name="status" defaultValue={initial?.status || "active"}>
            <option value="draft">Bản nháp</option>
            <option value="active">Đang dùng</option>
            <option value="archived">Lưu trữ</option>
          </select>
        </Field>
        <Field label="Ngôn ngữ prompt">
          <input
            name="language"
            defaultValue={initial?.language || "vi"}
            required
          />
        </Field>
        <Field label="Quốc gia prompt">
          <input
            name="country"
            defaultValue={initial?.country || "VN"}
            required
          />
        </Field>
        <Field label="Địa điểm prompt">
          <input name="location" defaultValue={initial?.location || ""} />
        </Field>
        <Field label="Giai đoạn hành trình">
          <input
            name="buyer_stage"
            defaultValue={initial?.buyer_stage || "unknown"}
          />
        </Field>
      </div>
      <Field label="Nguồn prompt">
        <select name="source" defaultValue={initial?.source || "manual"}>
          <option value="manual">Nhập thủ công</option>
          <option value="import">Tệp nhập</option>
          <option value="research">Research đã lưu</option>
          <option value="tracking">Tracking đã lưu</option>
          <option value="ai_generated_candidate">
            Ứng viên do AI đề xuất · không phải demand quan sát
          </option>
        </select>
      </Field>
      <Field label="Research keywords liên quan">
        <select
          multiple
          name="keywords"
          defaultValue={initial?.research_keyword_ids || []}
        >
          {refs.research_keywords.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Research cluster liên quan">
        <select
          name="cluster"
          defaultValue={initial?.research_cluster_id || ""}
        >
          <option value="">Chưa liên kết</option>
          {refs.research_clusters.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Tracked keyword liên quan">
        <select
          name="tracking"
          defaultValue={initial?.tracking_keyword_id || ""}
        >
          <option value="">Chưa liên kết</option>
          {refs.tracking.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="URL đích được khai báo">
        <input type="url" name="url" defaultValue={initial?.target_url || ""} />
      </Field>
      <Field label="Ghi chú prompt">
        <textarea name="notes" defaultValue={initial?.notes} />
      </Field>
    </Form>
  );
}
export function ObservationForm({
  initial,
  prompts,
  busy,
  onSave,
}: {
  initial?: VisibilityObservation;
  prompts: VisibilityPrompt[];
  busy: boolean;
  onSave: Save;
}) {
  const initialTime = initial?.observed_at
    ? new Date(
        new Date(initial.observed_at).getTime() -
          new Date(initial.observed_at).getTimezoneOffset() * 60000,
      )
        .toISOString()
        .slice(0, 16)
    : "";
  return (
    <Form
      busy={busy}
      label={initial ? "Lưu bản sửa mới" : "Lưu quan sát"}
      save={async (f) => {
        const raw = text(f, "raw").trim();
        const citationsText = text(f, "citations").trim();
        const observation = {
          prompt_id: text(f, "prompt"),
          provider: text(f, "provider"),
          model: text(f, "model") || null,
          collection_method: text(f, "method"),
          response_text: text(f, "response"),
          grounding: text(f, "grounding"),
          country: text(f, "country") || null,
          language: text(f, "language") || null,
          location: text(f, "location") || null,
          observed_at:
            initial && text(f, "time") === initialTime
              ? initial.observed_at
              : text(f, "time")
                ? new Date(text(f, "time")).toISOString()
                : null,
          citation_capability: text(f, "capability"),
          citation_metadata: text(f, "metadata"),
          completeness: text(f, "complete"),
          citations: citationsText ? JSON.parse(citationsText) : [],
          raw_annotations: raw ? JSON.parse(raw) : {},
          source_metadata: initial?.original.source_metadata || {},
          notes: text(f, "notes"),
          ...(initial ? { prompt_snapshot: initial.prompt_snapshot } : {}),
        };
        await onSave(
          initial ? { observation, reason: text(f, "reason") } : observation,
        );
      }}
    >
      <p>
        Metadata không được nguồn cung cấp cần để trống/Unknown. Không nhập
        token hoặc HTML cần thực thi. Văn bản phản hồi được lưu nguyên văn.
      </p>
      <Field label="Prompt của quan sát">
        <select name="prompt" required defaultValue={initial?.prompt_id || ""}>
          <option value="">Chọn prompt đã lưu</option>
          {prompts.map((p) => (
            <option key={p.id} value={p.id}>
              {p.text}
            </option>
          ))}
        </select>
      </Field>
      <div className="visibility-form-grid">
        <Field label="Provider quan sát">
          <input
            name="provider"
            required
            maxLength={100}
            defaultValue={initial?.provider}
          />
        </Field>
        <Field label="Model (nếu biết)">
          <input name="model" defaultValue={initial?.model || ""} />
        </Field>
        <Field label="Phương pháp thu thập">
          <select
            name="method"
            defaultValue={initial?.collection_method || "MANUAL_ENTRY"}
          >
            <option value="MANUAL_ENTRY">Nhập từ giao diện consumer</option>
            <option value="IMPORTED_RESPONSE">Phản hồi được nhập</option>
            <option value="THIRD_PARTY_REPORT">Báo cáo bên thứ ba</option>
            <option value="PROVIDER_API">
              Nguồn bên ngoài khai báo API · app không gọi live
            </option>
          </select>
        </Field>
        <Field label="Thời điểm quan sát (để trống nếu không biết)">
          <input type="datetime-local" name="time" defaultValue={initialTime} />
        </Field>
        <Field label="Country của quan sát">
          <input
            name="country"
            placeholder="Unknown"
            defaultValue={initial?.original.country || ""}
          />
        </Field>
        <Field label="Language của quan sát">
          <input
            name="language"
            placeholder="Unknown"
            defaultValue={initial?.original.language || ""}
          />
        </Field>
        <Field label="Location của quan sát">
          <input
            name="location"
            defaultValue={initial?.original.location || ""}
          />
        </Field>
        <Field label="Search / grounding">
          <select
            name="grounding"
            defaultValue={initial?.original.grounding || "unknown"}
          >
            <option value="unknown">Unknown</option>
            <option value="enabled">Có bật</option>
            <option value="disabled">Không bật</option>
          </select>
        </Field>
      </div>
      <Field label="Toàn bộ phản hồi gốc">
        <textarea
          name="response"
          required
          maxLength={30000}
          rows={10}
          defaultValue={initial?.response_text}
        />
      </Field>
      <div className="visibility-form-grid">
        <Field label="Khả năng citation">
          <select
            name="capability"
            defaultValue={initial?.citation_capability || "unknown"}
          >
            <option value="unknown">Unknown</option>
            <option value="capable">Có hỗ trợ citation</option>
            <option value="not_supported">Không hỗ trợ citation</option>
          </select>
        </Field>
        <Field label="Độ đầy đủ metadata citation">
          <select
            name="metadata"
            defaultValue={initial?.citation_metadata || "missing"}
          >
            <option value="missing">Không có / đã mất metadata</option>
            <option value="partial">Chỉ có một phần</option>
            <option value="complete">Đầy đủ, kể cả zero citation</option>
          </select>
        </Field>
        <Field label="Độ đầy đủ phản hồi">
          <select
            name="complete"
            defaultValue={initial?.completeness || "complete"}
          >
            <option value="complete">Đầy đủ</option>
            <option value="partial">Một phần</option>
            <option value="invalid">Không hợp lệ</option>
          </select>
        </Field>
      </div>
      <Field label="Citation tường minh (JSON)">
        <textarea
          name="citations"
          rows={5}
          defaultValue={
            initial
              ? JSON.stringify(initial.original.citations || [], null, 2)
              : "[]"
          }
        />
      </Field>
      <p className="muted-copy">
        Ví dụ cấu trúc:{" "}
        {'[{"url":"https://example.com/page","source_type":"user_supplied"}]'}.
        Đây là citation bạn khai báo, không tự xác minh HTTP/nội dung URL.
      </p>
      <Field label="Annotations / grounding gốc (JSON)">
        <textarea
          name="raw"
          rows={5}
          defaultValue={
            initial
              ? JSON.stringify(initial.original.raw_annotations || {}, null, 2)
              : "{}"
          }
        />
      </Field>
      <Field label="Ghi chú quan sát">
        <textarea name="notes" defaultValue={initial?.original.notes} />
      </Field>
      {initial && (
        <Field label="Lý do sửa (giữ nguyên bản gốc)">
          <textarea name="reason" required minLength={5} />
        </Field>
      )}
    </Form>
  );
}
export function DocumentForm({
  entities,
  prompts,
  busy,
  onSave,
}: {
  entities: VisibilityEntity[];
  prompts: VisibilityPrompt[];
  busy: boolean;
  onSave: Save;
}) {
  return (
    <Form
      busy={busy}
      save={async (f) =>
        onSave({
          kind: text(f, "kind"),
          url: text(f, "url"),
          content: text(f, "content"),
          approved: f.has("approved"),
          source_name: text(f, "source"),
          verification: f.has("verified") ? "user_verified" : "unverified",
          entity_id: text(f, "entity") || null,
          prompt_ids: f.getAll("prompts").map(String),
          business_fields: Object.fromEntries(
            ["company_name", "address", "phone", "website"]
              .filter((k) => text(f, k))
              .map((k) => [k, text(f, k)]),
          ),
          notes: text(f, "notes"),
        })
      }
    >
      <Field label="Loại nguồn nội dung">
        <select name="kind">
          <option value="page_content">Nội dung trang đã nhập</option>
          <option value="topic_requirement">Yêu cầu chủ đề đã duyệt</option>
          <option value="business_identity">Thông tin doanh nghiệp</option>
        </select>
      </Field>
      <Field label="Tên nguồn">
        <input name="source" required maxLength={200} />
      </Field>
      <Field label="URL nguồn">
        <input type="url" name="url" />
      </Field>
      <Field label="Nội dung nguồn thực tế">
        <textarea name="content" required rows={9} maxLength={30000} />
      </Field>
      <Field label="Entity liên quan">
        <select name="entity">
          <option value="">Không gán</option>
          {entities.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Prompt liên quan">
        <select name="prompts" multiple>
          {prompts.map((p) => (
            <option key={p.id} value={p.id}>
              {p.text}
            </option>
          ))}
        </select>
      </Field>
      <details>
        <summary>
          Thông tin business đã đối chiếu nguyên văn trong nguồn
        </summary>
        <Field label="Tên công ty">
          <input name="company_name" />
        </Field>
        <Field label="Địa chỉ">
          <input name="address" />
        </Field>
        <Field label="Điện thoại">
          <input name="phone" />
        </Field>
        <Field label="Website chính thức">
          <input name="website" />
        </Field>
      </details>
      <label className="visibility-check">
        <input name="verified" type="checkbox" />
        Tôi đã đối chiếu nguồn (user verified, không phải app fetch tự động)
      </label>
      <label className="visibility-check">
        <input name="approved" type="checkbox" />
        Duyệt nguồn này cho phân tích
      </label>
      <Field label="Ghi chú nguồn">
        <textarea name="notes" />
      </Field>
    </Form>
  );
}
export function CoverageForm({
  documents,
  busy,
  onSave,
}: {
  documents: VisibilityDocument[];
  busy: boolean;
  onSave: Save;
}) {
  return (
    <Form
      busy={busy}
      label="Lưu coverage review"
      save={async (f) =>
        onSave({
          requirement_id: text(f, "requirement"),
          page_id: text(f, "page"),
          decision: text(f, "decision"),
          reason: text(f, "reason"),
        })
      }
    >
      <p>
        Đọc toàn bộ trang và requirement. Không kết luận thiếu độ phủ chỉ vì
        không thấy một cụm từ.
      </p>
      <Field label="Requirement đã duyệt">
        <select name="requirement" required>
          <option value="">Chọn requirement</option>
          {documents
            .filter((d) => d.approved && d.kind === "topic_requirement")
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.content.slice(0, 100)}
              </option>
            ))}
        </select>
      </Field>
      <Field label="Nội dung trang đã duyệt">
        <select name="page" required>
          <option value="">Chọn trang</option>
          {documents
            .filter((d) => d.approved && d.kind === "page_content")
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.url}
              </option>
            ))}
        </select>
      </Field>
      <Field label="Kết quả coverage">
        <select name="decision">
          <option value="uncertain">Chưa đủ bằng chứng</option>
          <option value="covered">Đã đáp ứng</option>
          <option value="missing">
            Có khả năng thiếu · cần human verification
          </option>
        </select>
      </Field>
      <Field label="Lý do và phần nội dung đã đối chiếu">
        <textarea name="reason" required minLength={10} maxLength={2000} />
      </Field>
    </Form>
  );
}
