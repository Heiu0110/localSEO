import { queryOptions } from '@tanstack/react-query';
import { api, ApiError, mutate } from './apiClient';
import type { AuditProject, AuditRun, TechnicalOverview, TechnicalPageResult, TechnicalURL, TechnicalIssue, TechnicalTask, TechnicalLink, TechnicalSitemap, TechnicalURLDetail, TechnicalComparison } from '../types/technical';

const root='/technical';
export const activeAudit=(status?:string)=>status==='queued'||status==='running';
export const technicalProjectsQuery=queryOptions({queryKey:['technical','projects'],queryFn:({signal})=>api<AuditProject[]>(root+'/projects',signal)});
export function technicalRunsQuery(project:string,page=1){return queryOptions({queryKey:['technical','runs',project,page],queryFn:({signal})=>api<TechnicalPageResult<AuditRun>>(`${root}/audits?project_id=${encodeURIComponent(project)}&page=${page}`,signal),enabled:!!project});}
export function technicalRunQuery(id:string){return queryOptions({queryKey:['technical','run',id],queryFn:({signal})=>api<AuditRun>(`${root}/audits/${id}`,signal),enabled:!!id,refetchInterval:q=>activeAudit(q.state.data?.status)?1000:false});}
export function technicalOverviewQuery(id:string,running=false){return queryOptions({queryKey:['technical','overview',id],queryFn:({signal})=>api<TechnicalOverview>(`${root}/audits/${id}/overview`,signal),enabled:!!id,refetchInterval:running?2000:false});}
export function technicalRowsQuery<T>(id:string,kind:string,params:Record<string,string|number>,running=false){const query=new URLSearchParams(Object.entries(params).map(([k,v])=>[k,String(v)]));return queryOptions({queryKey:['technical',kind,id,params],queryFn:({signal})=>api<TechnicalPageResult<T>>(`${root}/audits/${id}/${kind}?${query}`,signal),enabled:!!id,refetchInterval:running?2000:false});}
export const technicalURLsQuery=(id:string,params:Record<string,string|number>,running=false)=>technicalRowsQuery<TechnicalURL>(id,'urls',params,running);
export const technicalIssuesQuery=(id:string,params:Record<string,string|number>,running=false)=>technicalRowsQuery<TechnicalIssue>(id,'issues',params,running);
export const technicalLinksQuery=(id:string,params:Record<string,string|number>)=>technicalRowsQuery<TechnicalLink>(id,'links',params);
export const technicalSitemapsQuery=(id:string,params:Record<string,string|number>)=>technicalRowsQuery<TechnicalSitemap>(id,'sitemaps',params);
export function technicalBacklogQuery(project:string,params:Record<string,string|number>){const query=new URLSearchParams({project_id:project,...Object.fromEntries(Object.entries(params).map(([k,v])=>[k,String(v)]))});return queryOptions({queryKey:['technical','backlog',project,params],queryFn:({signal})=>api<TechnicalPageResult<TechnicalTask>>(`${root}/backlog?${query}`,signal),enabled:!!project});}
export function technicalURLQuery(audit:string,id:string){return queryOptions({queryKey:['technical','url',audit,id],queryFn:({signal})=>api<TechnicalURLDetail>(`${root}/audits/${audit}/urls/${id}`,signal),enabled:!!audit&&!!id});}
export function technicalIssueQuery(id:string){return queryOptions({queryKey:['technical','issue',id],queryFn:({signal})=>api<TechnicalIssue>(`${root}/issues/${id}`,signal),enabled:!!id});}
export function technicalCompareQuery(before:string,after:string){return queryOptions({queryKey:['technical','compare',before,after],queryFn:({signal})=>api<TechnicalComparison>(`${root}/compare?before=${before}&after=${after}`,signal),enabled:!!before&&!!after});}
export const technicalMutation=<T>(path:string,body?:unknown,method:'POST'|'PATCH'='POST')=>mutate<T>(root+path,body,method);
export async function exportTechnical(id:string,format:'csv'|'json'|'html',dataset='issues') {
  const base=import.meta.env.VITE_API_BASE_URL||'/api';
  const response=await fetch(`${base}${root}/audits/${id}/export?format=${format}&dataset=${dataset}`);
  if(!response.ok){const result=await response.json().catch(()=>null);throw new ApiError(result?.detail||'Không thể xuất báo cáo.',response.status);}
  const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`technical-${dataset}-${id}.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
