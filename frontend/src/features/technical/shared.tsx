import type { ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import type { TechnicalPageResult } from '../../types/technical';
import { Button } from '../../components/ui/button';
import { EmptyState, ErrorState } from '../../components/ui/states';
import { number } from '../../lib/format';

export const technicalLabels:Record<string,string>={
  queued:'Đang chờ',running:'Đang chạy',completed:'Hoàn tất',partial:'Một phần',cancelled:'Đã hủy',interrupted:'Bị gián đoạn',failed:'Lỗi',
  critical:'Nghiêm trọng',high:'Cao',medium:'Trung bình',low:'Thấp',informational:'Thông tin',
  confirmed:'Đã quan sát',strong_evidence:'Bằng chứng mạnh',suspected:'Nghi vấn',needs_manual_verification:'Cần xác minh thủ công',unknown:'Chưa xác định',
  indexable_candidate:'Ứng viên có thể index',noindex:'Noindex',robots_blocked:'Robots chặn',canonicalized:'Canonical sang URL khác',redirected:'Chuyển hướng',error:'Lỗi',
  automated:'Tự động',integration_required:'Cần tích hợp',manual_review:'Xem thủ công',not_implemented:'Chưa triển khai',passed:'Đạt trong phạm vi đã kiểm tra',issue_found:'Phát hiện vấn đề',needs_review:'Cần xem xét',not_checked:'Chưa đánh giá',not_available:'Chưa có nguồn dữ liệu',
  open:'Chưa xử lý',in_progress:'Đang xử lý',fixed:'Đã sửa, chờ kiểm tra',ignored:'Bỏ qua có chủ ý',resolved:'Đã đóng',
  observed:'Còn quan sát thấy',awaiting_recrawl:'Chờ audit xác minh',verified_absent:'Đã xác minh không còn',reopened:'Tái xuất hiện',manual_status:'Trạng thái do người dùng đặt',source_deleted:'Snapshot xác minh đã xóa',
  new:'Mới',newly_observed:'Mới quan sát',persistent:'Vẫn còn',not_observed:'Chưa quan sát lại; chưa kết luận đã sửa',
  critical_money:'Trang kinh doanh trọng yếu',important:'Landing page quan trọng',supporting:'Nội dung hỗ trợ',
  yes:'Nên index',no:'Không nên index',undecided:'Chưa quyết định',
  observed_fact:'Quan sát trực tiếp',derived:'Suy luận từ dữ liệu',heuristic:'Heuristic, cần xem xét',
  stored_page_performance:'GSC Page Performance đã lưu',detected:'Đã phát hiện',not_configured:'Chưa cấu hình',unavailable:'Không khả dụng',fixture:'Thử nghiệm ngoại tuyến',raw_html_only:'Chỉ HTML gốc',
};
export const label=(value:string)=>technicalLabels[value]??value;
export const count=(value:number|null|undefined)=>value==null?'—':number(value);
export function TechnicalBadge({value}:{value:string}){return <span className={`badge technical-badge state-${value}`}>{label(value)}</span>;}
export function Evidence({value}:{value:unknown}){return <pre className="technical-evidence">{JSON.stringify(value,null,2)}</pre>;}
export interface Column<T>{key:string;title:string;sort?:string;render:(row:T)=>ReactNode}
interface Query<T>{data?:TechnicalPageResult<T>;isPending:boolean;isError:boolean;error:Error|null;refetch:()=>unknown}
export function TechnicalTable<T extends {id:string|number}>({title,query,columns,page,setPage,size,setSize,search,setSearch,sort,direction,onSort,children}:{title:string;query:Query<T>;columns:Column<T>[];page:number;setPage:(page:number)=>void;size?:number;setSize?:(size:number)=>void;search?:string;setSearch?:(value:string)=>void;sort?:string;direction?:string;onSort?:(key:string)=>void;children?:ReactNode}){
  return <section className="card technical-table" aria-label={title}><div className="card-heading"><div><h2>{title}</h2><p>{query.data?`${count(query.data.total)} bản ghi đã lưu`:'Đang đọc SQLite…'}</p></div>{children}</div>
    {setSearch&&<div className="table-toolbar"><label className="search-input"><Search size={14}/><input aria-label={`Tìm ${title}`} placeholder="Tìm trong dữ liệu đã lưu…" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/></label></div>}
    {query.isPending?<div className="state-box" role="status">Đang tải dữ liệu…</div>:query.isError?<ErrorState message={query.error?.message??'Không thể đọc dữ liệu.'} onRetry={()=>void query.refetch()}/>:!query.data?.rows.length?<EmptyState/>:<div className="table-scroll"><table><thead><tr>{columns.map(column=><th key={column.key} aria-sort={column.sort&&sort===column.sort?(direction==='desc'?'descending':'ascending'):undefined}>{column.sort&&onSort?<button onClick={()=>onSort(column.sort!)} aria-label={`Sắp xếp ${title} theo ${column.title}`}>{column.title} {sort===column.sort?(direction==='desc'?'↓':'↑'):''}</button>:column.title}</th>)}</tr></thead><tbody>{query.data.rows.map(row=><tr key={row.id}>{columns.map(column=><td key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody></table></div>}
    <div className="table-footer"><span>Trang {page} / {Math.max(1,Math.ceil((query.data?.total??0)/(size??20)))}</span><div>{setSize&&<label className="rows-label">Dòng<select aria-label={`Số dòng ${title}`} value={size} onChange={e=>{setSize(Number(e.target.value));setPage(1);}}>{[10,25,50,100].map(n=><option key={n}>{n}</option>)}</select></label>}<Button variant="ghost" size="icon" aria-label={`Trang trước ${title}`} disabled={page<=1||query.isPending} onClick={()=>setPage(page-1)}><ChevronLeft size={15}/></Button><Button variant="ghost" size="icon" aria-label={`Trang sau ${title}`} disabled={!query.data||page*(size??20)>=query.data.total||query.isPending} onClick={()=>setPage(page+1)}><ChevronRight size={15}/></Button></div></div>
  </section>;
}
