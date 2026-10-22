import { useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { keywordWrite } from "../../services/keywordApi";
import type { ImportPreview, KeywordSet, Profile } from "../../types/keywords";
import type { Action } from "./KeywordForms";
export function ImportExport({
  set,
  profile,
  action,
  busy,
  onImported,
  onExport,
}: {
  set: KeywordSet;
  profile: Profile;
  action: Action;
  busy: boolean;
  onImported: (set: string) => void;
  onExport: (format: "csv" | "xlsx") => void;
}) {
  const file = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mode, setMode] = useState("history");
  const [duplicates, setDuplicates] = useState("skip");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [accept, setAccept] = useState(false);
  function inspect() {
    void action(async () => {
      const selected = file.current?.files?.[0];
      if (!selected) throw new Error("Chọn tệp CSV hoặc XLSX trước.");
      const form = new FormData();
      form.set("file", selected);
      form.set("set_id", set.id);
      form.set("profile_id", profile.id);
      form.set("mode", mode);
      form.set("duplicates", duplicates);
      form.set("mapping", JSON.stringify(mapping));
      const result = await keywordWrite<ImportPreview>("/import", form);
      setPreview(result);
      setAccept(false);
    });
  }
  return (
    <>
      <section className="card kw-form">
        <h2>Nhập bảng theo dõi CSV / XLSX</h2>
        <p className="muted-copy">
          Header: Từ khóa, Nhóm, URL, Click, Impression, Vị trí trung bình, Tuần
          1…35. Tệp UTF-8 tối đa 100 KiB, 1.000 dòng. Xem trước không thay đổi
          danh sách.
        </p>
        <div className="kw-form-grid">
          <label>
            Tệp bảng tính
            <input
              ref={file}
              aria-label="Tệp bảng tính"
              type="file"
              accept=".csv,.xlsx"
              onChange={() => {
                setPreview(null);
                setMapping({});
              }}
            />
          </label>
          <label>
            Chế độ nhập
            <select
              aria-label="Chế độ nhập"
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                setPreview(null);
              }}
            >
              <option value="keywords">Chỉ từ khóa và metadata</option>
              <option value="history">Từ khóa + lịch sử rank</option>
              <option value="full">
                Toàn bộ bảng tính (metric chưa xác minh)
              </option>
            </select>
          </label>
          <label>
            Từ khóa trùng
            <select
              aria-label="Xử lý trùng"
              value={duplicates}
              onChange={(e) => {
                setDuplicates(e.target.value);
                setPreview(null);
              }}
            >
              <option value="skip">Bỏ qua</option>
              <option value="update">Cập nhật metadata, thêm lịch sử</option>
              <option value="separate">Tạo bộ campaign riêng</option>
            </select>
          </label>
        </div>
        <Button disabled={busy} onClick={inspect}>
          Xem trước tệp nhập
        </Button>
      </section>
      {preview && (
        <section className="card kw-form">
          <h2>Xem trước · {preview.filename}</h2>
          <p>
            {preview.data.total_rows} dòng · {preview.data.errors.length} lỗi ·{" "}
            {preview.data.warnings.length} cảnh báo trùng
          </p>
          <details>
            <summary>Ánh xạ cột ({preview.data.headers.length} header)</summary>
            <p className="muted-copy">
              Thay ánh xạ rồi xem trước lại để áp dụng. Có thể bỏ qua các cột
              không sử dụng.
            </p>
            <div className="kw-form-grid">
              {Object.entries(preview.data.mapping).map(([field, header]) => (
                <label key={field}>
                  {field}
                  <select
                    value={mapping[field] ?? header ?? ""}
                    onChange={(e) =>
                      setMapping((old) => ({ ...old, [field]: e.target.value }))
                    }
                  >
                    <option value="">Bỏ qua</option>
                    {preview.data.headers.map((h) => (
                      <option key={h}>{h}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <Button variant="outline" disabled={busy} onClick={inspect}>
              Xem trước lại ánh xạ
            </Button>
          </details>
          <div className="kw-import-preview">
            <table>
              <thead>
                <tr>
                  <th>Dòng</th>
                  <th>Từ khóa</th>
                  <th>Nhóm</th>
                  <th>URL</th>
                  <th>Tuần 1</th>
                  <th>Tuần 2</th>
                  <th>Kiểm tra</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.samples.map((r, i) => (
                  <tr key={i}>
                    <td>{r.row}</td>
                    <td>{r.keyword_text}</td>
                    <td>{r.group}</td>
                    <td>{r.target_url}</td>
                    <td>{r.week_1 || "—"}</td>
                    <td>{r.week_2 || "—"}</td>
                    <td>{r.valid ? "Hợp lệ" : "Bị từ chối"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(preview.data.errors.length > 0 ||
            preview.data.warnings.length > 0) && (
            <details open>
              <summary>Lỗi và cảnh báo</summary>
              <ul>
                {[...preview.data.errors, ...preview.data.warnings]
                  .slice(0, 100)
                  .map((e, i) => (
                    <li key={i}>
                      Dòng {e.row}: {e.message}
                    </li>
                  ))}
              </ul>
              {preview.data.errors.length + preview.data.warnings.length >
                100 && (
                <p>
                  Chỉ hiển thị 100 thông báo đầu; tổng lỗi được ghi rõ phía
                  trên.
                </p>
              )}
            </details>
          )}
          <p className="report-warning">
            Rank lịch sử không có ngày kiểm tra sẽ lưu “chỉ biết tuần”. Metric
            từ bảng tính là lịch sử chưa xác minh, không thay GSC hiện tại. Tất
            cả thay đổi được lưu trong một transaction.
          </p>
          {preview.data.errors.length > 0 && (
            <label className="compare-control">
              <input
                type="checkbox"
                checked={accept}
                onChange={(e) => setAccept(e.target.checked)}
              />
              Tôi chấp nhận bỏ qua toàn bộ dòng lỗi
            </label>
          )}
          <Button
            disabled={busy || (preview.data.errors.length > 0 && !accept)}
            onClick={() =>
              void action(async () => {
                const result = await keywordWrite<{ keyword_set_id: string }>(
                  `/import/${preview.id}/commit`,
                  { confirm: true, accept_rejected: accept },
                );
                setPreview(null);
                onImported(result.keyword_set_id);
              })
            }
          >
            Xác nhận nhập dữ liệu
          </Button>
        </section>
      )}
      <section className="card kw-form">
        <h2>Xuất báo cáo theo bộ lọc hiện tại</h2>
        <p className="muted-copy">
          Sáu cột chính + Tuần 1–35. NA, số và ô trống được giữ riêng. CSV có
          UTF-8 BOM; XLSX kèm sheet Metadata. Tối đa 5.000 từ khóa mỗi lần xuất.
        </p>
        <div className="technical-inline">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onExport("csv")}
          >
            Xuất CSV
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => onExport("xlsx")}
          >
            Xuất XLSX
          </Button>
        </div>
      </section>
    </>
  );
}
