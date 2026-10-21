import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Square } from 'lucide-react';
import { mutate } from '../../services/apiClient';
import { integrationQuery, jobsQuery } from '../../services/gscApi';
import type { GSCProperty, SyncJob } from '../../types/gsc';
import type { SearchType } from '../../types/api';
import { date, number } from '../../lib/format';
import { Button } from '../ui/button';

export const jobLabels: Record<string, string> = {
  not_started: 'Chưa đồng bộ', queued: 'Đang chờ', running: 'Đang đồng bộ', completed: 'Đã hoàn tất',
  partial: 'Cần tiếp tục', failed: 'Thất bại', cancelled: 'Đã hủy', reauthorization_required: 'Cần xác thực lại',
};
export const searchTypes: Record<SearchType, string> = { web: 'Web', image: 'Hình ảnh', video: 'Video', news: 'Tin tức (Search)' };
export function shiftDay(day: string, delta: number) {
  const value = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(value.getTime())) return '';
  value.setUTCDate(value.getUTCDate() + delta);
  return value.toISOString().slice(0, 10);
}

export function SyncPanel({ property }: { property?: GSCProperty }) {
  const status = useQuery(integrationQuery);
  const jobs = useQuery({ ...jobsQuery(property?.id), enabled: !!property });
  const queryClient = useQueryClient();
  const [history, setHistory] = useState('90');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [type, setType] = useState<SearchType>('web');
  const [mode, setMode] = useState('initial');
  const last = status.data?.latest_final_date ?? '';
  const first = status.data?.history_start ?? '';
  const selectedEnd = end || last;
  const proposedStart = selectedEnd ? history === 'max' ? first : shiftDay(selectedEnd, -Number(history) + 1) : '';
  const selectedStart = start || proposedStart;
  const workload = selectedStart && selectedEnd ? Math.max(0, Math.floor((Date.parse(selectedEnd) - Date.parse(selectedStart)) / 86400000) + 1) : 0;
  const active = jobs.data?.some(j => ['queued', 'running'].includes(j.status)) ?? false;
  const wasActive = useRef(false);
  const lastFinished = useRef<string | undefined>(undefined);
  const finishedId = jobs.data?.find(j => j.finished_at)?.id;
  useEffect(() => {
    if ((wasActive.current && !active) || (finishedId && lastFinished.current !== finishedId)) {
      lastFinished.current = finishedId;
      void queryClient.invalidateQueries({ predicate: query => query.queryKey[0] !== 'gsc-jobs' });
    }
    wasActive.current = active;
  }, [active, finishedId, queryClient]);
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => mutate<SyncJob>(path, body),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['gsc-jobs'] }); void queryClient.invalidateQueries({ queryKey: ['gsc-properties'] }); },
  });
  return <section className="card integration-card" aria-label="Đồng bộ GSC"><div className="card-heading"><div><h2><RefreshCw size={17} />Đồng bộ dữ liệu</h2><p>5 tập dữ liệu độc lập theo ngày, chỉ lấy dữ liệu final từ Google.</p></div></div><div className="integration-body">
    {!property ? <p className="muted-copy">Thêm và chọn một property trong workspace để đồng bộ.</p> : <><p className="selected-property">{property.site_url}</p><div className="gsc-form-grid">
      <label>Lịch sử<select aria-label="Lịch sử đồng bộ" value={history} onChange={e => { setHistory(e.target.value); setStart(''); setEnd(''); }}><option value="28">28 ngày</option><option value="90">90 ngày (khuyến nghị)</option><option value="180">180 ngày</option><option value="max">Tối đa khoảng 16 tháng</option></select></label>
      <label>Search type<select aria-label="Search type đồng bộ" value={type} onChange={e => setType(e.target.value as SearchType)}>{Object.entries(searchTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Từ ngày<input aria-label="Đồng bộ từ ngày" type="date" value={selectedStart} min={first} max={selectedEnd} onChange={e => setStart(e.target.value)} /></label>
      <label>Đến ngày<input aria-label="Đồng bộ đến ngày" type="date" value={selectedEnd} min={selectedStart} max={last} onChange={e => setEnd(e.target.value)} /></label>
      <label>Chế độ<select aria-label="Chế độ đồng bộ" value={mode} onChange={e => setMode(e.target.value)}><option value="initial">Nhập lịch sử / bỏ qua ngày đã hoàn tất</option><option value="incremental">Cập nhật tăng dần + làm mới 7 ngày</option><option value="refresh">Lấy lại toàn bộ kỳ đã chọn</option></select></label>
    </div><p className="muted-copy">{mode === 'incremental' ? 'Cập nhật từ mốc gần nhất và làm mới cửa sổ 7 ngày. ' : ''}{workload} ngày · ít nhất {number(workload * 5)} yêu cầu nếu lấy toàn kỳ, chưa tính phân trang. Ngày dữ liệu theo giờ Pacific; khoảng trống không được coi là 0.</p>
    <Button disabled={action.isPending || active || !workload || selectedStart > selectedEnd} onClick={() => action.mutate({ path: '/gsc/sync/start', body: { property_id: property.id, start_date: selectedStart, end_date: selectedEnd, search_type: type, sync_mode: mode } })}><RefreshCw size={15} />{active ? 'Đang đồng bộ…' : 'Bắt đầu đồng bộ'}</Button></>}
    {action.isError && <p role="alert" className="action-error">{action.error.message}</p>}
    {jobs.isError && <p role="alert" className="action-error">{jobs.error.message}</p>}
    {jobs.data?.slice(0, 5).map(job => <div className="sync-job" key={job.id} data-testid="sync-job"><div className="sync-job-title"><strong>{jobLabels[job.status] ?? job.status}</strong><span>{job.search_type} · {date(job.requested_date_start)} – {date(job.requested_date_end)}</span></div><progress aria-label="Tiến độ đồng bộ" value={job.completed_days} max={job.total_days || 1} /><p>{job.completed_days}/{job.total_days} ngày · {number(job.rows_fetched)} dòng · {job.retry_count} lần thử lại</p><p className="muted-copy">{job.current_task}</p>{job.error_message && <p className="action-error">{job.error_message}</p>}{['queued','running'].includes(job.status) ? <Button variant="outline" size="sm" disabled={action.isPending || job.cancel_requested} onClick={() => action.mutate({ path: `/gsc/sync/jobs/${job.id}/cancel` })}><Square size={12} />{job.cancel_requested ? 'Đang chờ hủy an toàn' : 'Hủy đồng bộ'}</Button> : job.status !== 'completed' && <Button variant="outline" size="sm" disabled={action.isPending || active} onClick={() => action.mutate({ path: `/gsc/sync/jobs/${job.id}/retry` })}>Tiếp tục từ checkpoint</Button>}</div>)}
  </div></section>;
}
