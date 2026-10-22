import { memo, useCallback, useMemo, useRef, useState } from "react";
import type {
  Keyword,
  KeywordSet,
  Observation,
  Profile,
  RankPayload,
} from "../../types/keywords";
import {
  rankText,
  rankError,
  num,
  metricLabels,
  Change,
  makeRank,
} from "./shared";
const columns = [
  ["keyword", "Từ khóa", 220],
  ["group", "Nhóm", 100],
  ["url", "URL đích", 190],
  ["clicks", "Click", 75],
  ["impressions", "Impression", 100],
  ["position", "GSC Position", 105],
] as const;
interface Props {
  rows: Keyword[];
  set: KeywordSet;
  profile: Profile;
  week: number;
  onDetail: (id: string) => void;
  onSave: (payload: RankPayload) => Promise<void>;
  onBatch: (rows: RankPayload[]) => void;
  selected: Set<string>;
  onSelect: (id: string) => void;
  visible: Set<string>;
  weekOnly: boolean;
  checkedAt: string;
}
function focusCell(target: HTMLElement, rowDelta: number, colDelta: number) {
  const row = target.closest<HTMLTableRowElement>("tr");
  const table = target.closest("table");
  if (!row || !table) return;
  const r = Number(row.dataset.row) + rowDelta;
  const n = Number(target.dataset.week) + colDelta;
  table
    .querySelector<HTMLButtonElement>(
      `tr[data-row="${r}"] button[data-week="${n}"]`,
    )
    ?.focus();
}
const RankCell = memo(function RankCell({
  observation,
  keyword,
  keywordLabel,
  profile,
  week,
  onSave,
  onPaste,
  weekOnly,
  checkedAt,
}: {
  observation?: Observation;
  keyword: string;
  keywordLabel: string;
  profile: Profile;
  week: number;
  onSave: Props["onSave"];
  onPaste: (text: string, week: number) => void;
  weekOnly: boolean;
  checkedAt: string;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const button = useRef<HTMLButtonElement>(null);
  async function save(tab = 0) {
    const invalid = rankError(value, profile.config.search_depth);
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSave(
        makeRank(keyword, profile, week, value, weekOnly, checkedAt),
      );
      setEditing(false);
      setTimeout(() => {
        button.current?.focus();
        if (tab && button.current) focusCell(button.current, 0, tab);
      }, 0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <td
      className={`kw-rank ${observation?.rank_status === "NOT_FOUND" ? "kw-na" : ""}`}
    >
      {editing ? (
        <div className="kw-cell-editor">
          <input
            autoFocus
            aria-label={`Rank tuần ${week}`}
            value={value}
            disabled={busy}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void save();
              }
              if (e.key === "Escape") {
                setEditing(false);
                button.current?.focus();
              }
              if (e.key === "Tab") {
                e.preventDefault();
                void save(e.shiftKey ? -1 : 1);
              }
            }}
            onPaste={(e) => {
              const text = e.clipboardData.getData("text");
              if (/[\t\n]/.test(text)) {
                e.preventDefault();
                setEditing(false);
                onPaste(text, week);
              }
            }}
          />
          <div className="kw-cell-actions">
            <button type="button" disabled={busy} onClick={() => void save()}>
              Lưu
            </button>
            <button type="button" onClick={() => setValue("NA")}>
              NA
            </button>
            <button type="button" onClick={() => setValue("")}>
              Xóa
            </button>
            <button type="button" onClick={() => setEditing(false)}>
              Hủy
            </button>
          </div>
          {error && (
            <span className="kw-cell-error" role="alert">
              {error}
            </span>
          )}
        </div>
      ) : (
        <button
          type="button"
          className="kw-rank-button"
          ref={button}
          data-week={week}
          aria-label={`${keywordLabel}, tuần ${week}: ${rankText(observation)}`}
          title={`${rankText(observation)} · ${observation?.count || 0} quan sát · ${observation?.match_mode || "chưa kiểm tra"}. Enter để sửa; mở từ khóa để xem lịch sử.`}
          onClick={() => {
            setValue(
              rankText(observation) === "—" ? "" : rankText(observation),
            );
            setError("");
            setEditing(true);
          }}
          onPaste={(e) => {
            e.preventDefault();
            onPaste(e.clipboardData.getData("text"), week);
          }}
          onKeyDown={(e) => {
            if (e.key.startsWith("Arrow")) {
              e.preventDefault();
              focusCell(
                e.currentTarget,
                e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0,
                e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0,
              );
            }
          }}
        >
          {rankText(observation)}
          {(observation?.count || 0) > 1 && <sup>{observation?.count}</sup>}
        </button>
      )}
    </td>
  );
});
const TrackingRow = memo(
  function TrackingRow({
    row,
    index,
    props,
    offsets,
    onPaste,
  }: {
    row: Keyword;
    index: number;
    props: Omit<Props, "rows" | "selected" | "onBatch"> & { checked: boolean };
    offsets: Record<string, number>;
    onPaste: (id: string, text: string, week: number) => void;
  }) {
    const paste = useCallback(
      (text: string, week: number) => onPaste(row.id, text, week),
      [onPaste, row.id],
    );
    const group = props.set.groups.find((g) => g.id === row.group_id);
    const title = metricLabels[row.metrics.status] || row.metrics.status;
    const cells: Record<string, React.ReactNode> = {
      keyword: (
        <div className="kw-keyword">
          <input
            type="checkbox"
            aria-label={`Chọn ${row.keyword_text}`}
            checked={props.checked}
            onChange={() => props.onSelect(row.id)}
          />
          <button
            className="text-action"
            onClick={() => props.onDetail(row.id)}
          >
            {row.keyword_text}
          </button>
        </div>
      ),
      group: group ? (
        <span className="kw-group" style={{ borderLeftColor: group.color }}>
          {group.name}
        </span>
      ) : (
        "—"
      ),
      url: (
        <span title={row.target_url} className="kw-target">
          {row.target_url || "Chưa có URL"}
          <small>
            {row.match_mode === "exact_url" ? "Exact URL" : "Domain"}
          </small>
        </span>
      ),
      clicks: <span title={title}>{num(row.metrics.clicks)}</span>,
      impressions: <span title={title}>{num(row.metrics.impressions)}</span>,
      position: (
        <span title={title}>{num(row.metrics.average_position, 1)}</span>
      ),
    };
    return (
      <tr data-row={index} data-keyword-id={row.id}>
        {columns
          .filter(([key]) => props.visible.has(key))
          .map(([key, , width]) => (
            <td
              key={key}
              className={`kw-fixed kw-fixed-${key}`}
              style={{
                left: offsets[key],
                width,
                minWidth: width,
                maxWidth: width,
              }}
            >
              {cells[key]}
            </td>
          ))}
        {Array.from({ length: Math.max(35, props.week) }, (_, i) => i + 1).map(
          (n) => (
            <RankCell
              key={n}
              observation={row.weeks[String(n)]}
              keyword={row.id}
              keywordLabel={row.keyword_text}
              profile={props.profile}
              week={n}
              onSave={props.onSave}
              onPaste={paste}
              weekOnly={props.weekOnly}
              checkedAt={props.checkedAt}
            />
          ),
        )}
        <td className="kw-change-column">
          <Change value={row.change} />
          {row.indicators.includes("url_mismatch") && (
            <small>URL GSC khác URL đích</small>
          )}
          {row.indicators.includes("low_ctr") && (
            <small>Impression cao, CTR thấp</small>
          )}
        </td>
      </tr>
    );
  },
  (a, b) =>
    a.row === b.row &&
    a.index === b.index &&
    a.offsets === b.offsets &&
    a.onPaste === b.onPaste &&
    Object.keys(a.props).every(
      (key) =>
        a.props[key as keyof typeof a.props] ===
        b.props[key as keyof typeof b.props],
    ),
);
export function TrackingTable(props: Props) {
  const { rows, selected, onBatch, ...shared } = props;
  const pasteContext = useRef(props);
  pasteContext.current = props;
  const offsets = useMemo(() => {
    const out: Record<string, number> = {};
    let left = 0;
    columns.forEach(([key, , width]) => {
      if (props.visible.has(key)) {
        out[key] = left;
        left += width;
      }
    });
    return out;
  }, [props.visible]);
  const paste = useCallback(
    (id: string, text: string, start: number) => {
      const current = pasteContext.current;
      const rows = current.rows;
      const index = rows.findIndex((r) => r.id === id);
      const block = text
        .replace(/\r/g, "")
        .replace(/\n$/, "")
        .split("\n")
        .map((r) => r.split("\t"));
      if (block.length + index > rows.length)
        throw new Error(
          "Khối dán vượt số dòng của trang. Chọn trang lớn hơn hoặc chia khối.",
        );
      const payload: RankPayload[] = [];
      for (let r = 0; r < block.length; r++)
        for (let c = 0; c < block[r].length; c++) {
          if (start + c > Math.max(35, current.week))
            throw new Error("Khối dán vượt các tuần đang hiển thị.");
          payload.push(
            makeRank(
              rows[index + r].id,
              current.profile,
              start + c,
              block[r][c],
              current.weekOnly,
              current.checkedAt,
            ),
          );
        }
      onBatch(payload);
    },
    [onBatch],
  );
  const [pasteError, setPasteError] = useState("");
  const safePaste = useCallback(
    (id: string, text: string, week: number) => {
      try {
        setPasteError("");
        paste(id, text, week);
      } catch (e) {
        setPasteError((e as Error).message);
      }
    },
    [paste],
  );
  return (
    <>
      {pasteError && (
        <p role="alert" className="action-error">
          {pasteError}
        </p>
      )}
      <div
        className="kw-table-scroll"
        role="region"
        aria-label="Bảng theo dõi 35 tuần"
        tabIndex={0}
      >
        <table className="kw-table">
          <thead>
            <tr>
              {columns
                .filter(([key]) => props.visible.has(key))
                .map(([key, label, width]) => (
                  <th
                    key={key}
                    scope="col"
                    className={`kw-fixed kw-fixed-${key}`}
                    style={{
                      left: offsets[key],
                      width,
                      minWidth: width,
                      maxWidth: width,
                    }}
                  >
                    {label}
                  </th>
                ))}
              {Array.from(
                { length: Math.max(35, props.week) },
                (_, i) => i + 1,
              ).map((n) => {
                const w = props.set.weeks.find((w) => w.week_number === n);
                return (
                  <th
                    key={n}
                    scope="col"
                    title={w ? `${w.start_date} – ${w.end_date}` : ""}
                    className={n === props.week ? "kw-selected-week" : ""}
                  >
                    Tuần {n}
                    <small>
                      {w?.start_date.slice(5).split("-").reverse().join("/")}
                    </small>
                  </th>
                );
              })}
              <th scope="col">Biến động tuần {props.week}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <TrackingRow
                key={row.id}
                row={row}
                index={index}
                props={{ ...shared, checked: selected.has(row.id) }}
                offsets={offsets}
                onPaste={safePaste}
              />
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="kw-empty">
            Chưa có từ khóa phù hợp. Thêm từ khóa hoặc thay đổi bộ lọc.
          </div>
        )}
      </div>
      <p className="muted-copy kw-table-help">
        Rank: số = đã tìm thấy · NA = đã kiểm tra nhưng ngoài phạm vi · — = chưa
        kiểm tra. Số nhỏ phía trên là số quan sát. Enter lưu, Esc hủy, Tab lưu
        và sang ô kế, phím mũi tên để di chuyển. Dán khối sẽ mở bản xem trước.
      </p>
    </>
  );
}
export const fixedColumns = columns;
