import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Info, ShieldCheck } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ErrorState } from '../../components/ui/states';
import { timestamp } from '../../lib/format';
import { activeAudit, technicalBacklogQuery, technicalCompareQuery, technicalIssuesQuery, technicalLinksQuery, technicalMutation, technicalRunsQuery, technicalSitemapsQuery, technicalURLsQuery } from '../../services/technicalApi';
import type { AuditProject, AuditRun, TechnicalImport, TechnicalOverview, TechnicalTask } from '../../types/technical';
import { count, Evidence, label, TechnicalBadge, TechnicalTable } from './shared';
import { TaskPanel } from './TechnicalDetails';

export function OverviewView({data,onIssue}:{data:TechnicalOverview;onIssue:(id:string)=>void}){
  const summary=data.summary;
  return <><div className="technical-kpis">{[['URL đã crawl',summary.crawled],['Lỗi nghiêm trọng',summary.critical],['URL cần xem indexability',summary.indexability?Object.entries(summary.indexability).filter(([key])=>!['indexable_candidate'].includes(key)).reduce((n,[,v])=>n+v,0):undefined],['Liên kết nội bộ hỏng',summary.broken_links],['URL chuyển hướng',summary.redirects],['Vấn đề sitemap',summary.sitemap_errors]].map(([title,value])=><section className="card technical-kpi" key={title}><span>{title}</span><strong>{value==null?'—':count(Number(value))}</strong><small>{data.finished_at?'Trong snapshot đã lưu':'Đang thu thập; tổng hợp sau khi dừng'}</small></section>)}</div>
    <div className="technical-distributions"><Distribution title="Phân bố mức độ vấn đề" values={summary.severity??{}}/><Distribution title="HTTP response" values={summary.http??{}}/><Distribution title="Local indexability" values={summary.indexability??{}}/></div>
    <section className="card technical-priorities"><div className="card-heading"><div><h2><AlertTriangle size={16}/>Ưu tiên xử lý</h2><p>Theo severity, mục đích URL, độ tin cậy và exposure GSC nếu có. Không phải SEO health score.</p></div></div>{data.top_issues.length?<div className="table-scroll"><table><thead><tr><th>Vấn đề / URL</th><th>Mức độ</th><th>Độ tin cậy</th><th>Bằng chứng</th></tr></thead><tbody>{data.top_issues.map(issue=><tr key={issue.id}><td><button className="table-link technical-issue-link" onClick={()=>onIssue(issue.id)}>{issue.title}</button><span className="technical-cell-note">{issue.url}</span></td><td><TechnicalBadge value={issue.severity}/></td><td><TechnicalBadge value={issue.confidence}/></td><td><Button size="sm" variant="ghost" onClick={()=>onIssue(issue.id)}>Chi tiết</Button></td></tr>)}</tbody></table></div>:<p className="muted-copy integration-body">{activeAudit(data.status)?'Chưa tổng hợp vấn đề; crawler đang chạy.':'Chưa có finding trong dữ liệu đã đánh giá. Xem coverage và danh mục kiểm tra trước khi kết luận.'}</p>}</section>
    <section className="card integration-card"><div className="card-heading"><div><h2><ShieldCheck size={16}/>Phạm vi và nguồn bằng chứng</h2><p>Trạng thái cục bộ không xác nhận Google đã index URL.</p></div></div><div className="integration-body"><dl className="technical-facts"><div><dt>Bắt đầu</dt><dd>{timestamp(data.started_at)}</dd></div><div><dt>Kết thúc</dt><dd>{data.finished_at?timestamp(data.finished_at):'Chưa kết thúc'}</dd></div><div><dt>URL phát hiện / đã crawl</dt><dd>{count(summary.discovered)} / {count(summary.crawled)}</dd></div><div><dt>Độ sâu HTML quan sát tối đa</dt><dd>{count(summary.maximum_depth)}</dd></div><div><dt>Robots / rendering</dt><dd>Luôn tôn trọng robots · chỉ HTML gốc</dd></div><div><dt>Coverage</dt><dd>{data.coverage.complete?'Đã xử lý hết frontier trong cấu hình này':'Chưa đầy đủ; không kết luận lỗi vắng mặt đã được sửa'}</dd></div></dl><div className="technical-inline">{Object.entries(data.coverage.sources??{}).map(([key,value])=><span className="badge badge-neutral" key={key}>{key}: {label(value)}</span>)}</div>{data.coverage.gsc!=null&&<Evidence value={data.coverage.gsc}/>}<details className="technical-advanced"><summary>Chi tiết robots đã quan sát</summary><Evidence value={data.coverage.robots}/></details></div></section>
    <details className="card technical-checklist"><summary>Danh mục kiểm tra · {data.rules.length} checks, có ghi rõ khả năng thực thi</summary><div className="table-scroll"><table><thead><tr><th>Rule / tên</th><th>Khả năng</th><th>Kết quả</th><th>URL đã đánh giá</th></tr></thead><tbody>{data.rules.map(rule=><tr key={rule.id}><td><strong>{rule.id}</strong><span className="technical-cell-note">{rule.name}</span></td><td>{label(rule.capability)}</td><td><TechnicalBadge value={rule.state}/></td><td>{count(rule.evaluated_urls)}</td></tr>)}</tbody></table></div></details>
  </>;
}
function Distribution({title,values}:{title:string;values:Record<string,number>}){
  const max=Math.max(1,...Object.values(values));return <section className="card technical-distribution"><h2>{title}</h2>{Object.keys(values).length?Object.entries(values).sort(([a],[b])=>["critical","high","medium","low","informational","2xx","3xx","4xx","429","5xx","network_error","indexable_candidate","noindex","robots_blocked","canonicalized","redirected","error","unknown"].indexOf(a)-["critical","high","medium","low","informational","2xx","3xx","4xx","429","5xx","network_error","indexable_candidate","noindex","robots_blocked","canonicalized","redirected","error","unknown"].indexOf(b)).map(([key,value])=><div className={`technical-bar state-${key}`} key={key}><span>{label(key)}</span><strong>{count(value)}</strong><div className="technical-bar-track"><span style={{width:`${value/max*100}%`}}/></div></div>):<p className="muted-copy">Chưa có tổng hợp.</p>}</section>;
}
export function URLsView({audit,filter='',onURL}:{audit:AuditRun;filter?:string;onURL:(id:string)=>void}){
  const [search,setSearch]=useState('');const [state,setState]=useState(filter);const [page,setPage]=useState(1);const [size,setSize]=useState(25);const [sort,setSort]=useState('url');const [direction,setDirection]=useState('asc');
  const query=useQuery(technicalURLsQuery(audit.id,{search,state,page,page_size:size,sort,direction},activeAudit(audit.status)));
  return <><div className="technical-inline technical-filters"><label>Local indexability<select aria-label="Lọc indexability" value={state} onChange={e=>{setState(e.target.value);setPage(1);}}><option value="">Mọi trạng thái</option>{['indexable_candidate','noindex','robots_blocked','canonicalized','redirected','error','unknown'].map(key=><option key={key} value={key}>{label(key)}</option>)}</select></label><span className="muted-copy">Chỉ URL đã phát hiện trong scope; chưa crawl không được coi là 0 hoặc indexable.</span></div><TechnicalTable title="URL Inventory" query={query} page={page} setPage={setPage} size={size} setSize={setSize} search={search} setSearch={setSearch} sort={sort} direction={direction} onSort={key=>{setDirection(sort===key&&direction==='asc'?'desc':'asc');setSort(key);setPage(1);}} columns={[
    {key:'url',title:'URL / Title',sort:'url',render:row=><><button className="table-link technical-long-link" onClick={()=>onURL(row.id)}>{row.url}</button><span className="technical-cell-note">{row.title||'Chưa có title'}</span></>},
    {key:'status',title:'HTTP',sort:'status',render:row=>row.status_code??'—'},
    {key:'index',title:'Local indexability',render:row=><TechnicalBadge value={row.indexability}/>},
    {key:'depth',title:'Độ sâu',sort:'depth',render:row=>count(row.depth)},
    {key:'in',title:'Links vào',sort:'inbound',render:row=>count(row.inbound)},
    {key:'out',title:'Links ra',sort:'outbound',render:row=>count(row.outbound)},
    {key:'clicks',title:'GSC clicks đã lưu',render:row=>row.gsc?count(row.gsc.clicks):'—'},
    {key:'source',title:'Nguồn phát hiện',render:row=>row.sources.join(', ')},
  ]}/></>;
}
export function IssuesView({audit,onIssue}:{audit:AuditRun;onIssue:(id:string)=>void}){
  const [search,setSearch]=useState('');const [severity,setSeverity]=useState('');const [category,setCategory]=useState('');const [page,setPage]=useState(1);const [size,setSize]=useState(25);const [sort,setSort]=useState('priority');const [direction,setDirection]=useState('desc');
  const query=useQuery(technicalIssuesQuery(audit.id,{search,severity,category,page,page_size:size,sort,direction},activeAudit(audit.status)));
  return <><div className="technical-inline technical-filters"><label>Mức độ<select aria-label="Lọc mức độ vấn đề" value={severity} onChange={e=>{setSeverity(e.target.value);setPage(1);}}><option value="">Mọi mức độ</option>{['critical','high','medium','low','informational'].map(key=><option key={key} value={key}>{label(key)}</option>)}</select></label><label>Nhóm kiểm tra<select aria-label="Lọc nhóm vấn đề" value={category} onChange={e=>{setCategory(e.target.value);setPage(1);}}><option value="">Mọi nhóm</option>{['CRAWL','INDEX','CAN','SITEMAP','HTTP','ARCH','LINK','ONPAGE'].map(key=><option key={key}>{key}</option>)}</select></label></div><TechnicalTable title="Issue Explorer" query={query} page={page} setPage={setPage} size={size} setSize={setSize} search={search} setSearch={setSearch} sort={sort} direction={direction} onSort={key=>{setDirection(sort===key&&direction==='desc'?'asc':'desc');setSort(key);setPage(1);}} columns={[
    {key:'title',title:'Vấn đề / URL',sort:'title',render:row=><><button className="table-link technical-issue-link" onClick={()=>onIssue(row.id)}>{row.title}</button><span className="technical-cell-note">{row.url}</span></>},
    {key:'rule',title:'Rule',sort:'rule',render:row=>row.rule_id},
    {key:'severity',title:'Mức độ',sort:'priority',render:row=><TechnicalBadge value={row.severity}/>},
    {key:'confidence',title:'Độ tin cậy',render:row=><TechnicalBadge value={row.confidence}/>},
    {key:'count',title:'URL cùng rule',render:row=>count(row.affected_url_count)},
    {key:'state',title:'Backlog',render:row=>label(row.status??'open')},
  ]}/></>;
}
export function SitemapsView({audit}:{audit:AuditRun}){
  const [page,setPage]=useState(1);const query=useQuery(technicalSitemapsQuery(audit.id,{page,page_size:25}));
  return <><p className="muted-copy">Tài liệu đã truy xuất trong scope, giới hạn 10 sitemap và 3 cấp index. Lỗi URL/noindex/canonical/lastmod nằm trong Issue Explorer. Không tự submit sitemap lên Google.</p><TechnicalTable title="XML Sitemaps" query={query} page={page} setPage={setPage} size={25} columns={[
    {key:'url',title:'Sitemap URL',render:row=><span className="technical-long-link">{row.url}</span>},
    {key:'status',title:'HTTP',render:row=>row.status_code??'—'},
    {key:'valid',title:'XML',render:row=>row.data.valid?'Đã parse':'Chưa xác nhận hợp lệ'},
    {key:'kind',title:'Loại',render:row=>row.data.kind??'—'},
    {key:'entries',title:'Số mục khai báo',render:row=>count(row.data.entries)},
    {key:'error',title:'Giới hạn / lỗi',render:row=>row.data.error??'—'},
  ]}/></>;
}
export function LinksView({audit}:{audit:AuditRun}){
  const [page,setPage]=useState(1);const [size,setSize]=useState(25);const [search,setSearch]=useState('');const query=useQuery(technicalLinksQuery(audit.id,{page,page_size:size,search}));
  return <><p className="muted-copy">Đồ thị href trong HTML gốc, không phải toàn bộ liên kết Google nhìn thấy. Độ sâu là đường HTML ngắn nhất đã quan sát; sitemap/GSC seed không được gán giả độ sâu 0.</p><TechnicalTable title="Liên kết đã quan sát" query={query} page={page} setPage={setPage} size={size} setSize={setSize} search={search} setSearch={setSearch} columns={[
    {key:'source',title:'URL nguồn',render:row=><span className="technical-long-link">{row.source_url}</span>},
    {key:'target',title:'URL đích',render:row=><span className="technical-long-link">{row.target_url}</span>},
    {key:'status',title:'HTTP đích',render:row=>row.target_status??'Chưa crawl'},
    {key:'anchor',title:'Anchor',render:row=>row.anchor||'Trống'},
    {key:'context',title:'Context / rel',render:row=>`${row.context} · ${row.rel||'—'}`},
    {key:'scope',title:'Scope',render:row=>row.internal?'Nội bộ':'Ngoài site · không tự crawl'},
  ]}/></>;
}
export function BacklogView({project}:{project:AuditProject}){
  const [page,setPage]=useState(1);const [size,setSize]=useState(25);const [search,setSearch]=useState('');const [status,setStatus]=useState('');const [task,setTask]=useState<TechnicalTask|null>(null);
  const query=useQuery(technicalBacklogQuery(project.id,{page,page_size:size,search,status}));
  return <><div className="technical-inline technical-filters"><label>Trạng thái công việc<select aria-label="Lọc backlog" value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="">Mọi trạng thái</option>{['open','in_progress','fixed','ignored','resolved'].map(key=><option key={key} value={key}>{label(key)}</option>)}</select></label><span className="muted-copy">Ghi chú giữ qua các lần audit. Không có thay đổi tự động trên website.</span></div><TechnicalTable title="Action Backlog" query={query} page={page} setPage={setPage} size={size} setSize={setSize} search={search} setSearch={setSearch} columns={[
    {key:'title',title:'Công việc / URL',render:row=><><button className="table-link technical-issue-link" onClick={()=>setTask(row)}>{row.title}</button><span className="technical-cell-note">{row.url}</span></>},
    {key:'severity',title:'Mức độ',render:row=><TechnicalBadge value={row.severity}/>},
    {key:'status',title:'Trạng thái',render:row=><TechnicalBadge value={row.status}/>},
    {key:'verification',title:'Xác minh',render:row=>label(row.verification)},
    {key:'owner',title:'Người xử lý',render:row=>row.owner||'Chưa gán'},
    {key:'date',title:'Gần nhất',render:row=>timestamp(row.last_seen_at)},
  ]}/><TaskPanel task={task} onClose={()=>setTask(null)}/></>;
}
export function HistoryView({project,onSelect,onAction}:{project:AuditProject;onSelect:(id:string)=>void;onAction:(task:()=>Promise<unknown>)=>Promise<void>}){
  const client=useQueryClient();const [page,setPage]=useState(1);const runs=useQuery(technicalRunsQuery(project.id,page));const [before,setBefore]=useState('');const [after,setAfter]=useState('');const [selected,setSelected]=useState({before:'',after:''});const compare=useQuery(technicalCompareQuery(selected.before,selected.after));
  const first=before||runs.data?.rows[1]?.id||'';const last=after||runs.data?.rows[0]?.id||'';
  return <><TechnicalTable title="Lịch sử audit" query={runs} page={page} setPage={setPage} size={20} columns={[
    {key:'name',title:'Audit',render:row=><button className="table-link technical-issue-link" onClick={()=>onSelect(row.id)}>{row.name}</button>},
    {key:'date',title:'Bắt đầu',render:row=>timestamp(row.started_at)},
    {key:'status',title:'Trạng thái',render:row=><TechnicalBadge value={row.status}/>},
    {key:'urls',title:'URL crawl',render:row=>count(row.summary.crawled)},
    {key:'issues',title:'Findings',render:row=>count(row.summary.issues)},
    {key:'delete',title:'Lưu trữ',render:row=><Button variant="ghost" size="sm" disabled={activeAudit(row.status)} onClick={()=>{if(window.confirm('Xóa vĩnh viễn snapshot audit này? Backlog và ghi chú vẫn được giữ. Nên xuất báo cáo hoặc backup trước.'))void onAction(async()=>{await technicalMutation(`/audits/${row.id}/delete`,{confirm:true});await client.invalidateQueries({queryKey:['technical']});});}}>Xóa snapshot</Button>},
  ]}/><section className="card integration-card"><div className="card-heading"><div><h2>So sánh hai snapshot</h2><p>Chỉ xác nhận “đã sửa” khi cùng scope/version, đủ coverage và rule đã đánh giá lại URL.</p></div></div><div className="integration-body"><div className="gsc-form-grid"><label>Audit trước<select aria-label="Audit trước" value={first} onChange={e=>setBefore(e.target.value)}><option value="">Chọn audit trước</option>{before&&!runs.data?.rows.some(row=>row.id===before)&&<option value={before}>{before}</option>}{runs.data?.rows.map(row=><option key={row.id} value={row.id}>{timestamp(row.started_at)} · {label(row.status)}</option>)}</select></label><label>Audit sau<select aria-label="Audit sau" value={last} onChange={e=>setAfter(e.target.value)}><option value="">Chọn audit sau</option>{after&&!runs.data?.rows.some(row=>row.id===after)&&<option value={after}>{after}</option>}{runs.data?.rows.map(row=><option key={row.id} value={row.id}>{timestamp(row.started_at)} · {label(row.status)}</option>)}</select></label></div><Button variant="outline" disabled={!first||!last||first===last} onClick={()=>setSelected({before:first,after:last})}>So sánh audit</Button>
    {selected.before&&compare.isPending&&<p role="status" className="muted-copy">Đang so sánh…</p>}{compare.isError&&<ErrorState message={compare.error.message} onRetry={()=>void compare.refetch()}/>}
    {compare.data&&<><div className="report-warning"><Info size={16}/><p>{compare.data.warning??'Hai snapshot cùng phạm vi; chỉ lỗi có bằng chứng đánh giá lại mới được đánh dấu resolved.'}</p></div><div className="technical-inline">{Object.entries(compare.data.counts).map(([key,value])=><span className="badge badge-neutral" key={key}>{label(key)}: {count(value)}</span>)}</div><div className="technical-compare-list">{compare.data.rows.map(row=><div key={`${row.id}-${row.state}`}><TechnicalBadge value={row.state}/><strong>{row.title}</strong><span>{row.url}</span></div>)}</div><p className="muted-copy">Hiển thị {compare.data.rows.length}/{compare.data.total} findings; {compare.data.url_changes_total} URL có thay đổi metadata/status.</p>{compare.data.url_changes.length>0&&<details className="technical-advanced"><summary>Bằng chứng thay đổi URL</summary><Evidence value={compare.data.url_changes}/></details>}</>}
    </div></section></>;
}
export function ImportURLs({project,onAction}:{project:AuditProject;onAction:(task:()=>Promise<unknown>)=>Promise<void>}){
  const [preview,setPreview]=useState<TechnicalImport|null>(null);const [message,setMessage]=useState('');
  return <section className="card integration-card"><div className="card-heading"><div><h2>Nhập URL quan trọng (CSV)</h2><p>UTF-8 · tối đa 100 KiB / 1.000 URL · xem trước rồi mới lưu vào dự án này.</p></div></div><div className="integration-body"><p className="muted-copy">Cột: url, priority, should_index, page_type, notes. priority: critical_money / important / supporting / low; should_index: yes / no / undecided.</p><label className="button button-outline technical-file-label">Chọn CSV URL<input type="file" accept=".csv,text/csv" aria-label="Nhập CSV URL quan trọng" onChange={e=>{const file=e.target.files?.[0];if(!file)return;void onAction(async()=>{const form=new FormData();form.append('file',file);setMessage('');setPreview(await technicalMutation<TechnicalImport>(`/import?project_id=${project.id}`,form));});e.target.value='';}}/></label>{preview&&<><p className="muted-copy">{preview.filename} · {preview.count} URL. Chưa áp dụng cho đến khi xác nhận.</p><Evidence value={preview.preview}/><Button onClick={()=>void onAction(async()=>{await technicalMutation(`/import/${preview.id}/commit`);setMessage(`Đã nhập ${preview.count} URL. Chạy audit mới để dùng phân loại này.`);setPreview(null);})}>Xác nhận nhập URL</Button></>}<p role="status" className="muted-copy">{message}</p><p className="muted-copy">Log server, redirect mapping và Page Indexing CSV chưa được hỗ trợ trong Core. Không gửi file credentials vào khu vực này.</p></div></section>;
}
