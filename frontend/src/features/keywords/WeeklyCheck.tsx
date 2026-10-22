import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { Keyword, Profile, RankPayload } from "../../types/keywords";
import { Change, makeRank, rankError, rankText } from "./shared";
export function WeeklyCheck({
  rows,
  profile,
  week,
  onSave,
  weekOnly,
  checkedAt,
}: {
  rows: Keyword[];
  profile: Profile;
  week: number;
  onSave: (p: RankPayload) => Promise<void>;
  weekOnly: boolean;
  checkedAt: string;
}) {
  const [index, setIndex] = useState(0);
  const [value, setValue] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const row = rows[index];
  useEffect(() => {
    setValue(
      row ? (rankText(row.current) === "—" ? "" : rankText(row.current)) : "",
    );
    setNotes("");
    setError("");
  }, [row?.id, week]);
  async function save() {
    const e = rankError(value, profile.config.search_depth);
    if (e) {
      setError(e);
      return;
    }
    if (!row) return;
    setBusy(true);
    setError("");
    try {
      await onSave(
        makeRank(row.id, profile, week, value, weekOnly, checkedAt, notes),
      );
      if (index < rows.length - 1) setIndex((i) => i + 1);
      else
        setError("Đã lưu từ khóa cuối trang. Chuyển trang để kiểm tra tiếp.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!row)
    return (
      <section className="card kw-empty">
        Không có từ khóa phù hợp trên trang này.
      </section>
    );
  const search = new URL("https://www.google.com/search");
  search.searchParams.set("q", row.keyword_text);
  search.searchParams.set("hl", profile.config.language);
  search.searchParams.set("gl", profile.config.country.toLowerCase());
  return (
    <div className="kw-weekly">
      <section className="card kw-check-list">
        <h2>Checklist tuần {week}</h2>
        <p className="muted-copy">
          {rows.length} từ khóa trên trang · bộ lọc giữ nguyên
        </p>
        {rows.map((r, i) => (
          <button
            key={r.id}
            className={i === index ? "active" : ""}
            onClick={() => setIndex(i)}
          >
            <span>
              {r.keyword_text}
              <small>
                {r.match_mode === "exact_url" ? "Exact URL" : "Domain"}
              </small>
            </span>
            <strong>{rankText(r.current)}</strong>
          </button>
        ))}
      </section>
      <section className="card kw-form kw-check-form">
        <div className="eyebrow">
          KIỂM TRA THỦ CÔNG · {index + 1}/{rows.length}
        </div>
        <h2>{row.keyword_text}</h2>
        <p className="kw-long-url">{row.target_url || "Theo dõi domain"}</p>
        <p>
          Tuần trước: {rankText(row.previous)} · <Change value={row.change} />
        </p>
        <p className="muted-copy">
          {profile.name} · {profile.config.location_label} ·{" "}
          {profile.config.device} · top {profile.config.search_depth} ·{" "}
          {row.match_mode}
        </p>
        <Button variant="outline" asChild>
          <a href={search.href} target="_blank" rel="noopener noreferrer">
            <ExternalLink size={14} />
            Mở Google Search
          </a>
        </Button>
        <p className="muted-copy">
          Liên kết mở tab thường. Dùng cửa sổ riêng tư nếu cần; tham số quốc
          gia/ngôn ngữ không đảm bảo vị trí chính xác và chế độ riêng tư không
          loại bỏ mọi cá nhân hóa. Bạn tự quan sát kết quả organic trước khi
          lưu.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label>
            Rank tuần {week}
            <input
              aria-label="Rank kiểm tra tuần"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoComplete="off"
              placeholder={`1–${profile.config.search_depth}, NA hoặc trống`}
            />
          </label>
          <label>
            Ghi chú kiểm tra
            <textarea
              aria-label="Ghi chú kiểm tra"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={4000}
            />
          </label>
          {error && (
            <p role="status" className="action-error">
              {error}
            </p>
          )}
          <div className="technical-inline">
            <Button type="submit" disabled={busy}>
              Lưu và tiếp tục
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => setValue("NA")}
            >
              Đánh dấu NA
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={busy || index >= rows.length - 1}
              onClick={() => setIndex((i) => i + 1)}
            >
              Bỏ qua
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}
