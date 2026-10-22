import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type {
  KeywordOverview as Overview,
  KeywordSet,
} from "../../types/keywords";
import { num } from "./shared";
const labels: Record<string, string> = {
  total: "Tổng từ khóa",
  top3: "Top 3",
  top10: "Top 10",
  top20: "Top 20",
  improved: "Tăng hạng",
  dropped: "Giảm hạng",
  not_found: "NA · Không tìm thấy",
  not_checked: "Chưa kiểm tra",
};
export function KeywordOverview({
  data,
  set,
  week,
}: {
  data: Overview;
  set: KeywordSet;
  week: number;
}) {
  return (
    <>
      <div className="kw-kpis">
        {Object.entries(labels).map(([key, label]) => (
          <section className="card kw-kpi" key={key}>
            <span>{label}</span>
            <strong>{num(data.stats[key])}</strong>
            <small>Tuần {week} · rank thủ công</small>
          </section>
        ))}
      </div>
      <section className="card kw-completion">
        <div>
          <h2>Tiến độ kiểm tra tuần {week}</h2>
          <span>
            {data.stats.checked}/{data.stats.total} từ khóa đã kiểm tra ·{" "}
            {data.stats.total
              ? Math.round((data.stats.checked / data.stats.total) * 100)
              : 0}
            %
          </span>
        </div>
        <progress max={data.stats.total || 1} value={data.stats.checked} />
        <p className="muted-copy">
          Tăng/giảm chỉ tính khi cả hai tuần liền nhau có rank số và cùng chuỗi.
          NA không tham gia trung bình.
        </p>
      </section>
      <div className="kw-chart-grid">
        <section className="card kw-chart-card">
          <h2>Phân bố rank tuần {week}</h2>
          <div className="kw-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.distribution}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} width={30} />
                <Tooltip />
                <Bar
                  dataKey="value"
                  name="Từ khóa"
                  fill="var(--chart-current)"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="card kw-chart-card">
          <h2>Quan sát theo tuần</h2>
          <p className="muted-copy">
            Số từ khóa đã quan sát; không nối trung bình rank của các phép đo
            khác nhau.
          </p>
          {data.trends.length ? (
            <div className="kw-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.trends}>
                  <XAxis dataKey="week" tickFormatter={(n) => `T${n}`} />
                  <YAxis allowDecimals={false} width={30} />
                  <Tooltip />
                  <Bar
                    dataKey="found"
                    name="Tìm thấy"
                    fill="var(--chart-current)"
                    stackId="checks"
                    isAnimationActive={false}
                  />
                  <Bar
                    dataKey="not_found"
                    name="NA"
                    fill="var(--silver)"
                    stackId="checks"
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="kw-empty">Chưa đủ dữ liệu lịch sử.</p>
          )}
        </section>
      </div>
      <section className="card kw-form">
        <h2>Hiệu suất nhóm</h2>
        <div className="kw-group-stats">
          {data.groups.map((g) => (
            <article key={g.group_id}>
              <strong>
                {set.groups.find((x) => x.id === g.group_id)?.name ||
                  "Chưa phân nhóm"}
              </strong>
              <span>
                {g.checked}/{g.total} đã kiểm tra · {g.top10} trong Top 10
              </span>
              <small>
                {!g.comparable && "Chưa đủ dữ liệu so sánh hai tuần · "}Trung
                bình rank số: {num(g.average_rank, 1)} · chỉ mô tả các quan sát
                hiện có
              </small>
            </article>
          ))}
          {!data.groups.length && (
            <p className="muted-copy">Thêm từ khóa để bắt đầu theo dõi.</p>
          )}
        </div>
      </section>
    </>
  );
}
