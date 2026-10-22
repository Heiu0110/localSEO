import csv
import hashlib
import html
import io
import json
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import delete, func, or_, select, update

from app.gsc.dates import now
from app.gsc.errors import GSCError
from app.gsc.runtime import Runtime, get_runtime
from app.technical.fixtures import ROOT as FIXTURE_ROOT
from app.technical.jobs import public, require, validate_config
from app.technical.models import AuditImport, AuditIssue, AuditLink, AuditProject, AuditRun, AuditSitemap, AuditTask, AuditURL, URLIntent
from app.technical.reports import comparison, like, list_issues, list_urls, overview, paginate, url_detail
from app.technical.rules import catalog
from app.technical.schemas import AuditInput, AuditView, ConfirmDelete, CrawlConfig, IntentInput, PageResult, ProjectInput, ProjectView, TaskUpdate
from app.technical.urls import CrawlError, Scope, normalize

router=APIRouter(prefix='/api/technical',tags=['Technical SEO'])
RuntimeDep=Annotated[Runtime,Depends(get_runtime)]
Page=Annotated[int,Query(ge=1)]
PageSize=Annotated[int,Query(ge=1,le=100)]
Search=Annotated[str,Query(max_length=200)]


@router.get('/projects',response_model=list[ProjectView])
def projects(runtime:RuntimeDep):
    with runtime.db.session() as session:return list(session.scalars(select(AuditProject).order_by(AuditProject.updated_at.desc()).limit(200)))


@router.post('/projects',response_model=ProjectView,status_code=201)
def create_project(body:ProjectInput,runtime:RuntimeDep):return runtime.technical.create_project(body)


@router.get('/projects/{project_id}',response_model=ProjectView)
def project(project_id:str,runtime:RuntimeDep):
    with runtime.db.session() as session:return require(session,AuditProject,project_id)


@router.patch('/projects/{project_id}',response_model=ProjectView)
def edit_project(project_id:str,body:ProjectInput,runtime:RuntimeDep):
    with runtime.db.session.begin() as session:
        row=require(session,AuditProject,project_id)
        if normalize(body.root_url)!=row.root_url or body.property_id!=row.property_id:
            raise GSCError('immutable_project_scope','Đổi website/property cần tạo dự án mới để giữ lịch sử đúng scope.',422)
        if session.scalar(select(AuditRun.id).where(AuditRun.project_id==project_id,AuditRun.status.in_(('queued','running')))):
            raise GSCError('audit_already_active','Chờ audit hoàn tất trước khi đổi cấu hình.',409)
        validate_config(row.root_url,body.config.model_dump(),row.source_type=='fixture')
        row.name=body.name.strip() or row.name;row.config=body.config.model_dump();row.updated_at=now()
        session.flush();return ProjectView.model_validate(row)


@router.post('/fixtures',response_model=ProjectView,status_code=201)
def fixture_project(runtime:RuntimeDep):
    return runtime.technical.create_project(ProjectInput(root_url=FIXTURE_ROOT,name='Technical SEO — bộ thử nghiệm ngoại tuyến',
        config=CrawlConfig(max_urls=30,important_urls=[FIXTURE_ROOT+'private'])),fixture=True)


@router.post('/audits',response_model=AuditView,status_code=202)
def start_audit(body:AuditInput,runtime:RuntimeDep):return runtime.technical.start(body)


@router.get('/audits',response_model=PageResult)
def audits(runtime:RuntimeDep,project_id:str,page:Page=1,page_size:PageSize=20):
    with runtime.db.session() as session:
        require(session,AuditProject,project_id)
        return paginate(session,select(AuditRun).where(AuditRun.project_id==project_id),AuditRun,page,page_size,[AuditRun.started_at.desc()])


@router.get('/audits/{audit_id}',response_model=AuditView)
def audit(audit_id:str,runtime:RuntimeDep):return runtime.technical.get(audit_id)


@router.post('/audits/{audit_id}/cancel',response_model=AuditView)
def cancel(audit_id:str,runtime:RuntimeDep):return runtime.technical.cancel(audit_id)


@router.post('/audits/{audit_id}/restart',response_model=AuditView,status_code=202)
def restart(audit_id:str,runtime:RuntimeDep):
    run=runtime.technical.get(audit_id)
    if run.status in ('queued','running'):raise GSCError('audit_already_active','Audit vẫn đang active.',409)
    config={k:v for k,v in run.config.items() if k in CrawlConfig.model_fields}
    return runtime.technical.start(AuditInput(project_id=run.project_id,name=run.name,config=CrawlConfig(**config)))


@router.get('/audits/{audit_id}/overview')
def audit_overview(audit_id:str,runtime:RuntimeDep):return overview(runtime.db,audit_id)


@router.get('/audits/{audit_id}/urls',response_model=PageResult)
def urls(audit_id:str,runtime:RuntimeDep,page:Page=1,page_size:PageSize=25,search:Search='',state:str='',
         sort:Literal['url','status','depth','inbound','outbound','title','duration']='url',direction:Literal['asc','desc']='asc'):
    return list_urls(runtime.db,audit_id,page,page_size,search,state,sort,direction)


@router.get('/audits/{audit_id}/urls/{url_id}')
def url(audit_id:str,url_id:str,runtime:RuntimeDep):return url_detail(runtime.db,audit_id,url_id)


@router.get('/audits/{audit_id}/issues',response_model=PageResult)
def issues(audit_id:str,runtime:RuntimeDep,page:Page=1,page_size:PageSize=25,search:Search='',severity:str='',category:str='',rule:str='',
           sort:Literal['priority','severity','url','rule','title']='priority',direction:Literal['asc','desc']='desc'):
    return list_issues(runtime.db,audit_id,page,page_size,search,severity,category,rule,sort,direction)


@router.get('/issues/{issue_id}')
def issue(issue_id:str,runtime:RuntimeDep):
    with runtime.db.session() as session:
        row=require(session,AuditIssue,issue_id);result=public(row)
        task=session.scalar(select(AuditTask).where(AuditTask.project_id==row.project_id,AuditTask.fingerprint==row.fingerprint))
        result['task']=public(task) if task else None;return result


@router.get('/audits/{audit_id}/sitemaps',response_model=PageResult)
def sitemaps(audit_id:str,runtime:RuntimeDep,page:Page=1,page_size:PageSize=25):
    with runtime.db.session() as session:
        require(session,AuditRun,audit_id)
        return paginate(session,select(AuditSitemap).where(AuditSitemap.audit_id==audit_id),AuditSitemap,page,page_size,[AuditSitemap.url])


@router.get('/audits/{audit_id}/links',response_model=PageResult)
def links(audit_id:str,runtime:RuntimeDep,page:Page=1,page_size:PageSize=25,search:Search='',internal:bool|None=None):
    with runtime.db.session() as session:
        require(session,AuditRun,audit_id)
        query=select(AuditLink).where(AuditLink.audit_id==audit_id)
        if search:query=query.where(or_(AuditLink.target_url.ilike(like(search),escape='\\'),AuditLink.anchor.ilike(like(search),escape='\\')))
        if internal is not None:query=query.where(AuditLink.internal==internal)
        result=paginate(session,query,AuditLink,page,page_size,[AuditLink.id])
        for row in result['rows']:
            source=session.get(AuditURL,row['source_id']);row['source_url']=source.url if source else None
            target=session.scalar(select(AuditURL).where(AuditURL.audit_id==audit_id,AuditURL.url==row['target_url']))
            row['target_status']=target.status_code if target else None
        return result


@router.get('/compare')
def compare(runtime:RuntimeDep,before:str,after:str):return comparison(runtime.db,before,after)


@router.get('/backlog',response_model=PageResult)
def backlog(runtime:RuntimeDep,project_id:str,page:Page=1,page_size:PageSize=25,status:str='',search:Search=''):
    with runtime.db.session() as session:
        require(session,AuditProject,project_id)
        query=select(AuditTask).where(AuditTask.project_id==project_id)
        if status:query=query.where(AuditTask.status==status)
        if search:query=query.where(or_(AuditTask.url.ilike(like(search),escape='\\'),AuditTask.title.ilike(like(search),escape='\\')))
        return paginate(session,query,AuditTask,page,page_size,[AuditTask.priority.desc(),AuditTask.id])


@router.patch('/backlog/{task_id}')
def edit_task(task_id:str,body:TaskUpdate,runtime:RuntimeDep):
    with runtime.db.session.begin() as session:
        task=require(session,AuditTask,task_id);task.status=body.status;task.owner=body.owner;task.notes=body.notes
        task.verification='awaiting_recrawl' if body.status=='fixed' else 'manual_status' if body.status=='resolved' else task.verification
        session.flush();return public(task)


def save_intent(session,project_id,body,source):
    project=require(session,AuditProject,project_id)
    scope=Scope(project.root_url,project.config,project.source_type=='fixture')
    value=scope.check(body.url,patterns=True)
    value=normalize(value,query_policy=project.config['query_policy'])
    row=session.scalar(select(URLIntent).where(URLIntent.project_id==project_id,URLIntent.url==value))
    if not row:
        count=session.scalar(select(func.count()).select_from(URLIntent).where(URLIntent.project_id==project_id))
        if count>=5000:raise GSCError('intent_limit','Tối đa 5.000 phân loại URL mỗi dự án.',422)
        row=URLIntent(id=str(uuid4()),project_id=project_id,url=value);session.add(row)
    row.importance=body.importance;row.should_index=body.should_index;row.page_type=body.page_type;row.notes=body.notes;row.source=source;row.updated_at=now()
    session.flush();return public(row)


@router.post('/projects/{project_id}/intent')
def classify(project_id:str,body:IntentInput,runtime:RuntimeDep):
    with runtime.db.session.begin() as session:return save_intent(session,project_id,body,'manual')


@router.post('/import')
async def preview_import(runtime:RuntimeDep,project_id:str,file:Annotated[UploadFile,File()]):
    try:
        content=await file.read(100*1024+1)
        if len(content)>100*1024:raise GSCError('import_too_large','CSV tối đa 100 KiB và 1.000 dòng.',413)
        try:
            text=content.decode('utf-8-sig',errors='strict');reader=csv.DictReader(io.StringIO(text))
            if not reader.fieldnames or 'url' not in reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError()
            rows=[];seen=set()
            with runtime.db.session() as session:
                project=require(session,AuditProject,project_id);scope=Scope(project.root_url,project.config,project.source_type=='fixture')
                for number,row in enumerate(reader,2):
                    if len(rows)>=1000 or None in row or any(v is None for v in row.values()):raise ValueError()
                    body=IntentInput(url=normalize(scope.check(row['url'],patterns=True),query_policy=project.config['query_policy']),importance=row.get('priority') or 'supporting',should_index=row.get('should_index') or 'undecided',page_type=row.get('page_type') or '',notes=row.get('notes') or '')
                    if body.url in seen:raise ValueError()
                    seen.add(body.url);rows.append(body.model_dump())
            if not rows:raise ValueError()
        except (ValueError,UnicodeError,csv.Error,CrawlError):raise GSCError('invalid_csv','CSV UTF-8 cần cột url, tối đa 1.000 URL duy nhất trong scope. Kiểm tra priority/should_index và cấu trúc dòng.',422) from None
        with runtime.db.session.begin() as session:
            item=AuditImport(id=str(uuid4()),project_id=project_id,filename=(file.filename or 'import.csv').replace('\\','/').split('/')[-1][:100],digest=hashlib.sha256(content).hexdigest(),status='preview',rows=rows,created_at=now())
            session.add(item);session.flush();return {'id':item.id,'filename':item.filename,'count':len(rows),'preview':rows[:20],'status':'preview'}
    finally:await file.close()


@router.post('/import/{import_id}/commit')
def commit_import(import_id:str,runtime:RuntimeDep):
    with runtime.db.session.begin() as session:
        item=require(session,AuditImport,import_id)
        if item.status=='imported':return {'id':item.id,'status':'imported','count':len(item.rows)}
        for row in item.rows:save_intent(session,item.project_id,IntentInput(**row),item.id)
        item.status='imported';return {'id':item.id,'status':'imported','count':len(item.rows)}


@router.get('/rules')
def rule_catalog():return catalog()


@router.post('/audits/{audit_id}/delete')
def delete_audit(audit_id:str,body:ConfirmDelete,runtime:RuntimeDep):
    if not body.confirm:raise GSCError('delete_confirmation','Cần xác nhận xóa snapshot audit.',422)
    with runtime.db.session.begin() as session:
        run=require(session,AuditRun,audit_id)
        if run.status in ('queued','running'):raise GSCError('audit_already_active','Chờ hoặc hủy audit trước khi xóa.',409)
        session.execute(update(AuditTask).where(AuditTask.verification_audit_id==audit_id).values(verification_audit_id=None,verification='source_deleted'))
        session.delete(run)
    return {'deleted':audit_id}


@router.get('/summary')
def dashboard_summary(runtime:RuntimeDep,site_id:str):
    from app.db.models import Property
    from app.services.dashboard_service import get_service
    with runtime.db.session() as session:
        prop=session.get(Property,site_id)
        domain=next((site.domain for site in get_service().provider.sites if site.id==site_id),None)
        projects=list(session.scalars(select(AuditProject).where(AuditProject.source_type=='live')))
        candidates=[p.id for p in projects if (prop and p.property_id==prop.id) or (domain and urlsplit(p.root_url).hostname==domain)]
        if not candidates:return None
        run=session.scalar(select(AuditRun).where(AuditRun.project_id.in_(candidates)).order_by(AuditRun.started_at.desc()).limit(1))
        return public(run) if run else None


@router.get('/audits/{audit_id}/export')
def export(audit_id:str,runtime:RuntimeDep,format:Literal['csv','json','html']='csv',dataset:Literal['issues','urls']='issues'):
    with runtime.db.session() as session:
        # Explicit read transaction provides one stable snapshot even if retention deletes a run concurrently.
        session.connection().exec_driver_sql('BEGIN')
        run=require(session,AuditRun,audit_id)
        if run.status in ('queued','running'):raise GSCError('audit_active_export','Chờ hoàn tất hoặc hủy audit trước khi xuất snapshot nhất quán.',409)
        project=require(session,AuditProject,run.project_id)
        findings=[public(row) for row in session.scalars(select(AuditIssue).where(AuditIssue.audit_id==audit_id).order_by(AuditIssue.priority.desc()))]
        urls=[public(row) for row in session.scalars(select(AuditURL).where(AuditURL.audit_id==audit_id).order_by(AuditURL.url))]
        tasks=[public(row) for row in session.scalars(select(AuditTask).where(AuditTask.project_id==project.id).order_by(AuditTask.priority.desc()))]
        report={'project':public(project),'audit':public(run),'issues':findings,'urls':urls,'action_plan_current':tasks,
            'limitations':['Không phải Google index coverage hoặc SEO health score.','Audit chỉ quan sát HTTP/HTML công khai trong scope và coverage đã ghi.','Không rendering, CWV, URL Inspection, log analysis; không sửa website.']}
    headers={'Content-Disposition':f'attachment; filename="technical-{audit_id}.{format}"','Cache-Control':'no-store'}
    if format=='json':return Response(json.dumps(report,ensure_ascii=False),media_type='application/json',headers=headers)
    if format=='csv':
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(['Nguồn','Website','Audit','Trạng thái','Coverage complete','URL','Tiêu đề','Rule / State','Severity / HTTP','Confidence','Evidence / Data','Khuyến nghị','Xác minh'])
        safe=lambda value:"'"+str(value) if str(value)[:1] in ('=','+','-','@','\t','\r','\n') else str(value)
        for row in findings if dataset=='issues' else urls:
            values=[project.source_type,project.root_url,run.id,run.status,run.coverage.get('complete',False),row['url'],row.get('title',''),row.get('rule_id',row.get('indexability','')),row.get('severity',row.get('status_code','')),row.get('confidence',''),json.dumps(row.get('evidence',row.get('data',{})),ensure_ascii=False),row.get('recommendation',''),row.get('verification','')]
            writer.writerow([safe(value) for value in values])
        return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers=headers)
    esc=lambda value:html.escape(str(value),quote=True)
    rows=''.join(f'<tr><td>{esc(row["rule_id"])}<br>{esc(row["url"])}</td><td>{esc(row["severity"])} / {esc(row["confidence"])}</td><td>{esc(row["title"])}<pre>{esc(json.dumps(row["evidence"],ensure_ascii=False))}</pre></td><td>{esc(row["recommendation"])}<p>{esc(row["verification"])}</p></td></tr>' for row in findings)
    page=f'<!doctype html><html lang="vi"><meta charset="utf-8"><title>Technical SEO audit</title><style>body{{font:14px system-ui;color:#35251e;margin:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d7c8b8;padding:10px;text-align:left;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media print{{body{{margin:0}}tr{{break-inside:avoid}}}}</style><h1>{esc(project.name)}</h1><p>{esc(project.root_url)} · {esc(project.source_type)} · {esc(run.started_at)} · {esc(run.status)}</p><h2>Coverage và giới hạn</h2><pre>{esc(json.dumps(run.coverage,ensure_ascii=False,indent=2))}</pre><p>Local indexability không phải Google index. Không có SEO health score. Dùng Ctrl+P để in hoặc lưu PDF qua trình duyệt.</p><h2>Bằng chứng và hành động</h2><table><thead><tr><th>Rule / URL</th><th>Mức độ / tin cậy</th><th>Bằng chứng</th><th>Khuyến nghị và xác minh</th></tr></thead><tbody>{rows}</tbody></table></html>'
    return HTMLResponse(page,headers={**headers,'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})
