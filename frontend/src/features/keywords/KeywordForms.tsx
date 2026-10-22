import { useState } from "react";
import { Button } from "../../components/ui/button";
import type { Keyword, KeywordSet, Profile } from "../../types/keywords";
import { monday } from "./shared";
export type Action = (fn: () => Promise<unknown>) => Promise<void>;
export function SetForm({
  site,
  initial,
  onSave,
  busy,
}: {
  site: string;
  initial?: KeywordSet;
  onSave: (body: unknown) => void;
  busy: boolean;
}) {
  return (
    <form
      aria-label={initial ? "Cấu hình bộ từ khóa" : "Tạo bộ từ khóa"}
      className="card kw-form"
      onSubmit={(e) => {
        e.preventDefault();
        const d = new FormData(e.currentTarget);
        const values = {
          name: d.get("name"),
          description: d.get("description"),
          start_date: d.get("start_date"),
          timezone: d.get("timezone"),
        };
        onSave(
          initial
            ? {
                ...values,
                min_impressions: Number(d.get("min_impressions")),
                low_ctr: Number(d.get("low_ctr")) / 100,
              }
            : { site_id: site, ...values },
        );
      }}
    >
      <h2>{initial ? "Cấu hình bộ từ khóa" : "Tạo bộ từ khóa"}</h2>
      <div className="kw-form-grid">
        <label>
          Tên bộ
          <input
            name="name"
            aria-label="Tên bộ từ khóa"
            defaultValue={initial?.name}
            required
            maxLength={200}
          />
        </label>
        <label>
          Tuần 1 bắt đầu
          <input
            name="start_date"
            aria-label="Ngày bắt đầu theo dõi"
            type="date"
            defaultValue={initial?.start_date || monday()}
            required
          />
        </label>
        <label>
          Múi giờ
          <input
            name="timezone"
            defaultValue={initial?.timezone || "Asia/Ho_Chi_Minh"}
            required
          />
        </label>
        <label>
          Mô tả
          <input
            name="description"
            defaultValue={initial?.description}
            maxLength={2000}
          />
        </label>
        {initial && (
          <>
            <label>
              Impression tối thiểu cho gợi ý CTR
              <input
                type="number"
                name="min_impressions"
                min="1"
                max="10000000"
                defaultValue={initial.settings.min_impressions}
              />
            </label>
            <label>
              Ngưỡng CTR thấp (%)
              <input
                type="number"
                name="low_ctr"
                min="0"
                max="100"
                step="0.1"
                defaultValue={initial.settings.low_ctr * 100}
              />
            </label>
          </>
        )}
      </div>
      <p className="muted-copy">
        Tuần 1 bắt đầu đúng ngày chọn, mỗi tuần 7 ngày. Lịch và múi giờ được
        khóa sau khi có quan sát; không đổi nhãn lịch sử.
      </p>
      <Button disabled={busy} type="submit">
        {initial ? "Lưu cấu hình bộ" : "Tạo bộ từ khóa"}
      </Button>
    </form>
  );
}
export function KeywordForm({
  set,
  keyword,
  onSave,
  busy,
  onDelete,
}: {
  set: KeywordSet;
  keyword?: Keyword;
  onSave: (body: unknown) => void;
  busy: boolean;
  onDelete?: () => void;
}) {
  const [target, setTarget] = useState(keyword?.target_url || "");
  const [mode, setMode] = useState(
    keyword?.match_mode || (target ? "exact_url" : "domain"),
  );
  return (
    <form
      className="kw-form"
      onSubmit={(e) => {
        e.preventDefault();
        const d = new FormData(e.currentTarget);
        onSave({
          keyword_set_id: String(d.get("keyword_set_id") || set.id),
          keyword_text: d.get("keyword_text"),
          group_id: d.get("group_id") || null,
          target_url: target,
          match_mode: mode,
          priority: d.get("priority"),
          status: d.get("status"),
          search_intent: d.get("search_intent"),
          notes: d.get("notes"),
        });
      }}
    >
      <div className="kw-form-grid">
        <label>
          Từ khóa
          <input
            name="keyword_text"
            aria-label="Từ khóa"
            defaultValue={keyword?.keyword_text}
            maxLength={500}
            required
          />
        </label>
        <label>
          Nhóm
          <select name="group_id" defaultValue={keyword?.group_id || ""}>
            <option value="">Chưa phân nhóm</option>
            {set.groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label className="kw-wide">
          URL đích
          <input
            type="url"
            aria-label="URL đích"
            value={target}
            onChange={(e) => {
              setTarget(e.target.value);
              if (!keyword) setMode(e.target.value ? "exact_url" : "domain");
            }}
            maxLength={2048}
          />
        </label>
        <label>
          Cách đo
          <select
            aria-label="Cách đo rank"
            value={mode}
            onChange={(e) => setMode(e.target.value as "exact_url" | "domain")}
          >
            <option value="exact_url">Exact Target URL</option>
            <option value="domain">Domain / Property</option>
          </select>
        </label>
        <label>
          Ưu tiên
          <select name="priority" defaultValue={keyword?.priority || "normal"}>
            <option value="normal">Bình thường</option>
            <option value="high">Cao</option>
            <option value="low">Thấp</option>
          </select>
        </label>
        <label>
          Trạng thái
          <select name="status" defaultValue={keyword?.status || "active"}>
            <option value="active">Đang theo dõi</option>
            <option value="paused">Tạm dừng</option>
            <option value="archived">Lưu trữ</option>
          </select>
        </label>
        <label>
          Search Intent
          <input
            name="search_intent"
            defaultValue={keyword?.search_intent}
            maxLength={100}
          />
        </label>
        <label className="kw-wide">
          Ghi chú
          <textarea
            name="notes"
            defaultValue={keyword?.notes}
            maxLength={4000}
          />
        </label>
      </div>
      <p className="muted-copy">
        Thay đổi từ khóa, URL hoặc cách đo sẽ bắt đầu một chuỗi so sánh mới; các
        quan sát cũ vẫn còn.
      </p>
      <div className="technical-inline">
        <Button type="submit" disabled={busy}>
          Lưu từ khóa
        </Button>
        {onDelete && (
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={onDelete}
          >
            Xóa từ khóa và lịch sử…
          </Button>
        )}
      </div>
    </form>
  );
}
export function ProfileForm({
  set,
  profile,
  onSave,
  busy,
}: {
  set: KeywordSet;
  profile?: Profile;
  onSave: (data: unknown) => void;
  busy: boolean;
}) {
  return (
    <form
      className="card kw-form"
      onSubmit={(e) => {
        e.preventDefault();
        const d = new FormData(e.currentTarget);
        onSave({
          keyword_set_id: set.id,
          name: d.get("name"),
          country: d.get("country"),
          language: d.get("language"),
          location_label: d.get("location_label"),
          device: d.get("device"),
          search_depth: Number(d.get("search_depth")),
        });
      }}
    >
      <h2>{profile ? "Search Profile đang chọn" : "Search Profile mới"}</h2>
      <div className="kw-form-grid">
        <label>
          Tên profile
          <input
            name="name"
            defaultValue={profile?.name || "Google Việt Nam · Desktop"}
            maxLength={100}
            required
          />
        </label>
        <label>
          Quốc gia (ISO 2)
          <input
            name="country"
            defaultValue={profile?.config.country || "VN"}
            pattern="[A-Z]{2}"
            required
          />
        </label>
        <label>
          Ngôn ngữ
          <input
            name="language"
            defaultValue={profile?.config.language || "vi"}
            required
          />
        </label>
        <label>
          Vị trí quan sát
          <input
            name="location_label"
            defaultValue={profile?.config.location_label || "Việt Nam"}
            maxLength={200}
          />
        </label>
        <label>
          Thiết bị
          <select
            name="device"
            defaultValue={profile?.config.device || "desktop"}
          >
            {["desktop", "mobile", "tablet"].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <label>
          Độ sâu tìm kiếm
          <input
            name="search_depth"
            type="number"
            min="1"
            max="1000"
            defaultValue={profile?.config.search_depth || 100}
            required
          />
        </label>
      </div>
      <p className="muted-copy">
        Google · Organic Web. Đếm kết quả web tự nhiên; loại quảng cáo, Local
        Pack, Shopping và bản thân AI Overview. Rank thủ công khác GSC Position.
        Thay profile sẽ không viết lại snapshot cũ.
      </p>
      <Button disabled={busy}>
        {profile ? "Lưu Search Profile" : "Thêm Search Profile"}
      </Button>
    </form>
  );
}
