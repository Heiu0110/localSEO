import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Target } from "lucide-react";
import { keywordQuery } from "../../services/keywordApi";
import { num } from "./shared";
interface Summary {
  keyword_set_id: string;
  name: string;
  profile_id: string;
  week: number;
  total: number;
  top10: number;
  improved: number;
  dropped: number;
  checked: number;
}
export function KeywordSummary({ site }: { site: string }) {
  const query = useQuery(
    keywordQuery<Summary | null>(
      `/summary?site_id=${encodeURIComponent(site)}`,
      !!site,
    ),
  );
  const row = query.data;
  if (!row) return null;
  return (
    <section className="card technical-dashboard-summary">
      <div>
        <h2>
          <Target size={16} />
          Theo dõi từ khóa · {row.name}
        </h2>
        <p>
          Tuần {row.week} · {num(row.total)} từ khóa · Top 10: {row.top10} ·
          Tăng: {row.improved} · Giảm: {row.dropped} · {row.checked}/{row.total}{" "}
          đã kiểm tra thủ công
        </p>
      </div>
      <Link
        className="button button-outline"
        to={`/keyword-tracking?site=${encodeURIComponent(site)}&set=${row.keyword_set_id}&profile=${row.profile_id}&week=${row.week}&tab=overview`}
      >
        Xem thứ hạng tuần
      </Link>
    </section>
  );
}
