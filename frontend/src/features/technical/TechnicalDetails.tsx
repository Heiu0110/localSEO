import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Sheet } from '../../components/ui/sheet';
import { Button } from '../../components/ui/button';
import { ErrorState } from '../../components/ui/states';
import { technicalIssueQuery, technicalMutation, technicalURLQuery } from '../../services/technicalApi';
import type { TechnicalTask, TechnicalURLDetail } from '../../types/technical';
import { timestamp } from '../../lib/format';
import { count, Evidence, label, TechnicalBadge } from './shared';

function Facts({values}:{values:Array<[string,unknown]>}){return <dl className="technical-facts">{values.map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value==null?'—':String(value)}</dd></div>)}</dl>;}
export function URLPanel({audit,id,project,onClose}:{audit:string;id:string;project:string;onClose:()=>void}){
  const query=useQuery(technicalURLQuery(audit,id));
  return <Sheet open={!!id} onOpenChange={open=>{if(!open)onClose();}} title="Chi tiết URL đã crawl" description="Bằng chứng của snapshot này được giữ nguyên; phân loại mới áp dụng cho audit sau.">
    {query.isPending?<p className="muted-copy">Đang tải URL…</p>:query.isError?<ErrorState message={query.error.message} onRetry={()=>void query.refetch()}/>:<URLContents key={query.data.id} row={query.data} project={project}/>}</Sheet>;
}
function URLContents({row,project}:{row:TechnicalURLDetail;project:string}){
  const data=row.data;const initial=(data.intent??{}) as {importance?:string;should_index?:string;notes?:string;page_type?:string};
  const [importance,setImportance]=useState(initial.importance??'supporting');const [intent,setIntent]=useState(initial.should_index??'undecided');const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);
  return <><p className="technical-url-title">{row.url}</p><TechnicalBadge value={row.indexability}/><Facts values={[
    ['Original URL / href',row.original_url],['HTTP / trạng thái',`${row.status_code??'—'} · ${row.state}`],['Final URL',row.final_url],['Title',row.title],['Word count (HTML gốc)',data.word_count],
    ['Độ sâu HTML quan sát',row.depth],['Liên kết vào / ra',`${count(row.inbound)} / ${count(row.outbound)}`],['Thời gian chuỗi request (ms)',row.duration_ms],
    ['Robots cho crawler',data.robots_allowed],['Googlebot (mô phỏng robots)',data.googlebot_allowed],['Canonical target HTTP',row.canonical_target_status],['Rendering',label(String(data.rendering_status??'unknown'))],
    ['Google index status','Chưa có URL Inspection'],['Nguồn discovery',row.sources.join(', ')],['Disposition (khuyến nghị)',data.disposition],
  ]}/><h3>Metadata và directives</h3><Evidence value={{description:data.description,headings:data.headings,canonical:data.canonical,meta_robots:data.meta_robots,x_robots_tag:data.x_robots_tag,redirect_chain:data.redirect_chain,fetch_error:data.fetch_error}}/>
  {data.gsc!=null&&<><h3>Exposure GSC đã lưu · page/byPage</h3><Evidence value={data.gsc}/><p className="muted-copy">Không phải tổng site, Page Indexing hoặc bằng chứng traffic giảm do lỗi kỹ thuật.</p></>}
  <h3>Liên kết vào / ra đã quan sát</h3><Evidence value={{incoming:row.incoming,outgoing:row.outgoing}}/>
  <h3>Phân loại mục đích URL</h3><div className="gsc-form-grid"><label>Mức độ quan trọng<select aria-label="Độ quan trọng URL" value={importance} onChange={e=>setImportance(e.target.value)}>{['critical_money','important','supporting','low'].map(key=><option value={key} key={key}>{label(key)}</option>)}</select></label><label>Ý định index<select aria-label="Ý định index URL" value={intent} onChange={e=>setIntent(e.target.value)}>{['yes','no','undecided'].map(key=><option value={key} key={key}>{label(key)}</option>)}</select></label></div>
  <Button disabled={busy} variant="outline" onClick={async()=>{setBusy(true);setMessage('');try{await technicalMutation(`/projects/${project}/intent`,{url:row.url,importance,should_index:intent,page_type:initial.page_type??'',notes:initial.notes??''});setMessage('Đã lưu phân loại cho lần audit tiếp theo. Snapshot hiện tại giữ nguyên.');}catch(error){setMessage((error as Error).message);}finally{setBusy(false);}}}>Lưu phân loại URL</Button><p role="status" className="muted-copy">{message}</p>
  {row.limitations.map(value=><p className="muted-copy" key={value}>{value}</p>)}</>;
}
export function IssuePanel({id,onClose,onBacklog}:{id:string;onClose:()=>void;onBacklog:()=>void}){
  const query=useQuery(technicalIssueQuery(id));const row=query.data;
  return <Sheet open={!!id} onOpenChange={open=>{if(!open)onClose();}} title="Bằng chứng và hướng xử lý" description="Phân biệt sự kiện quan sát, suy luận và heuristic; không phải kết luận xếp hạng của Google.">
    {query.isPending?<p className="muted-copy">Đang tải bằng chứng…</p>:query.isError?<ErrorState message={query.error.message} onRetry={()=>void query.refetch()}/>:row&&<><p className="technical-url-title">{row.title}</p><div className="technical-inline"><TechnicalBadge value={row.severity}/><TechnicalBadge value={row.confidence}/><span className="muted-copy">{row.rule_id} · {label(row.evidence_type)}</span></div><p className="technical-url-title">{row.url}</p>{row.expected_behavior&&<><h3>Hành vi mong muốn</h3><p className="detail-note">{row.expected_behavior}</p></>}{row.business_impact&&<p className="muted-copy">{row.business_impact}</p>}<Evidence value={row.evidence}/><h3>Khuyến nghị</h3><p className="detail-note">{row.recommendation}</p><h3>Cách xác minh</h3><p className="detail-note">{row.verification}</p><h3>Lý do ưu tiên</h3><ul className="setup-steps">{row.priority_reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><p className="muted-copy">Đầu tiên: {timestamp(row.first_seen_at)} · Gần nhất: {timestamp(row.last_seen_at)}</p><Button variant="outline" onClick={onBacklog}>Mở backlog xử lý</Button></>}
  </Sheet>;
}
export function TaskPanel({task,onClose}:{task:TechnicalTask|null;onClose:()=>void}){
  return <Sheet open={!!task} onOpenChange={open=>{if(!open)onClose();}} title="Cập nhật công việc" description="Trạng thái thủ công không thay thế việc xác minh bằng audit mới.">{task&&<TaskEditor key={task.id} task={task} onClose={onClose}/>}</Sheet>;
}
function TaskEditor({task,onClose}:{task:TechnicalTask;onClose:()=>void}){
  const client=useQueryClient();const [status,setStatus]=useState(task.status);const [owner,setOwner]=useState(task.owner);const [notes,setNotes]=useState(task.notes);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  return <><p className="technical-url-title">{task.title}</p><p className="technical-url-title">{task.url}</p><TechnicalBadge value={task.verification}/><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{await technicalMutation(`/backlog/${task.id}`,{status,owner,notes},'PATCH');await client.invalidateQueries({queryKey:['technical','backlog']});onClose();}catch(error){setError((error as Error).message);}finally{setBusy(false);}}}><div className="gsc-form-grid"><label>Trạng thái<select aria-label="Trạng thái công việc" value={status} onChange={e=>setStatus(e.target.value)}>{['open','in_progress','fixed','ignored','resolved'].map(key=><option key={key} value={key}>{label(key)}</option>)}</select></label><label>Người xử lý<input aria-label="Người xử lý" maxLength={100} value={owner} onChange={e=>setOwner(e.target.value)}/></label></div><label className="technical-field">Ghi chú<textarea aria-label="Ghi chú công việc" rows={6} maxLength={4000} value={notes} onChange={e=>setNotes(e.target.value)}/></label><p className="muted-copy">Chọn “Đã sửa, chờ kiểm tra” rồi chạy audit mới cùng scope để xác minh. Nếu lỗi còn, công việc được mở lại; ghi chú vẫn giữ.</p>{error&&<p role="alert" className="action-error">{error}</p>}<Button type="submit" disabled={busy}>Lưu công việc</Button></form></>;
}
