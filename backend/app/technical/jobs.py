import hashlib
import heapq
import json
import logging
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import MetricFact, Property
from app.gsc.dates import now
from app.gsc.errors import GSCError
from app.technical.extract import extract, indexability
from app.technical.fetch import Fetcher, Fetched
from app.technical.fixtures import ROOT as FIXTURE_ROOT, fixture_transport
from app.technical.models import AuditImport, AuditIssue, AuditLink, AuditProject, AuditRun, AuditSitemap, AuditTask, AuditURL, URLIntent
from app.technical.robots import Robots
from app.technical.rules import VERSION, absence_verified, evaluate
from app.technical.schemas import AuditView, CrawlConfig, ProjectView
from app.technical.sitemap import MAX_XML, parse_sitemap
from app.technical.urls import CrawlError, Scope, normalize

ACTIVE=('queued','running')
logger=logging.getLogger(__name__)


def require(session,model,key):
    item=session.get(model,key)
    if not item:raise GSCError('technical_not_found','Không tìm thấy dự án, audit hoặc bản ghi Technical SEO.',404)
    return item


def public(item):
    result={column.name:getattr(item,column.name) for column in item.__table__.columns}
    if isinstance(item,AuditIssue):
        for key in ('description','expected_behavior','actual_behavior','business_impact'):
            result[key]=item.evidence.get(key)
    return result


def property_matches(prop,root):
    if prop.site_url.startswith('sc-domain:'):
        domain=prop.site_url[10:];host=urlsplit(root).hostname
        return host==domain or host.endswith('.'+domain)
    return root.startswith(prop.site_url)


def validate_config(root,config,fixture=False):
    scope=Scope(root,config,fixture)
    for url in config.get('important_urls',[])+config.get('sitemap_urls',[]):scope.check(url)
    return scope


class AuditManager:
    def __init__(self,db,transport_factory=None,sleeper=time.sleep):
        self.db,self.transport_factory,self.sleeper=db,transport_factory,sleeper
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='technical-audit')
        self.lock=threading.RLock();self.closed=False;self.failures={}

    def recover(self):
        with self.db.session.begin() as session:
            session.execute(update(AuditRun).where(AuditRun.status.in_(ACTIVE)).values(status='interrupted',phase='Bị gián đoạn; dữ liệu từng URL đã lưu. Chạy lại tạo snapshot mới.',finished_at=now()))

    def create_project(self,request,fixture=False):
        root=normalize(request.root_url)
        config=request.config.model_dump()
        validate_config(root,config,fixture)
        if fixture and root!=FIXTURE_ROOT:raise GSCError('invalid_fixture','URL fixture không hợp lệ.',422)
        with self.db.session.begin() as session:
            if request.property_id:
                prop=require(session,Property,request.property_id)
                if prop.source_type!='gsc' or not property_matches(prop,root):
                    raise GSCError('property_scope_mismatch','GSC property không bao phủ website này hoặc chỉ là dữ liệu thử nghiệm.',422)
            project=AuditProject(id=str(uuid4()),name=request.name.strip() or f'Technical Audit — {urlsplit(root).hostname}',
                root_url=root,property_id=request.property_id,source_type='fixture' if fixture else 'live',config=config,created_at=now(),updated_at=now())
            session.add(project);session.flush();return ProjectView.model_validate(project)

    def start(self,request,submit=True):
        with self.lock:
            if self.closed:raise GSCError('technical_stopping','Worker đang dừng; hãy khởi động lại backend.',409)
            try:
                with self.db.session.begin() as session:
                    project=require(session,AuditProject,request.project_id)
                    if session.scalar(select(AuditRun.id).where(AuditRun.project_id==project.id,AuditRun.status.in_(ACTIVE))):
                        raise GSCError('audit_already_active','Dự án đang có audit chạy hoặc chờ xử lý.',409)
                    config=request.config.model_dump() if request.config else dict(project.config)
                    validate_config(project.root_url,config,project.source_type=='fixture')
                    project.config=config;project.updated_at=now()
                    config={**config,'root_url':normalize(project.root_url,query_policy=config['query_policy']),'source_type':project.source_type}
                    intents={row.url:{'importance':row.importance,'should_index':row.should_index,'page_type':row.page_type,'notes':row.notes,'source':row.source} for row in session.scalars(select(URLIntent).where(URLIntent.project_id==project.id))}
                    for url in config['important_urls']:
                        intents.setdefault(normalize(url,query_policy=config['query_policy']),{'importance':'important','should_index':'yes','source':'settings'})
                    config['intents']=intents
                    scope_hash=hashlib.sha256(json.dumps({k:v for k,v in config.items() if k not in ('delay_seconds','timeout_seconds')},sort_keys=True).encode()).hexdigest()
                    run=AuditRun(id=str(uuid4()),project_id=project.id,name=request.name.strip() or project.name,status='queued',config=config,
                        scope_hash=scope_hash,rule_version=VERSION,phase='Chờ worker',processed=0,requests=0,cancel_requested=False,
                        coverage={'complete':False,'warnings':[],'sources':{'crawl':'pending','sitemap':'pending','gsc':'not_configured','rendering':'not_implemented'}},summary={},started_at=now())
                    session.add(run);session.flush();result=AuditView.model_validate(run)
            except IntegrityError:raise GSCError('audit_already_active','Dự án đang có audit active.',409) from None
            if submit:self.executor.submit(self.run,result.id)
            return result

    def get(self,key):
        with self.db.session() as session:
            row=AuditView.model_validate(require(session,AuditRun,key))
            return row.model_copy(update=self.failures.get(key,{}))

    def cancel(self,key):
        with self.db.session.begin() as session:
            run=require(session,AuditRun,key)
            if run.status in ACTIVE:run.cancel_requested=True
        return self.get(key)

    def cancelled(self,key):
        if self.closed:return True
        with self.db.session() as session:
            row=session.get(AuditRun,key)
            return row is None or row.cancel_requested

    def close(self):
        self.closed=True;self.executor.shutdown(wait=True,cancel_futures=True)

    def run(self,key):
        fetcher=None
        try:
            with self.db.session.begin() as session:
                run=require(session,AuditRun,key)
                if run.status!='queued':return
                run.status='running';run.phase='Đọc robots.txt'
                config=dict(run.config);project=require(session,AuditProject,run.project_id)
                property_id=project.property_id
            fixture=config['source_type']=='fixture'
            scope=validate_config(config['root_url'],config,fixture)
            coverage={'complete':False,'warnings':[],'robots':{},'sources':{'crawl':'fixture' if fixture else 'observed','sitemap':'pending','gsc':'not_configured','rendering':'not_implemented'}}
            transport=self.transport_factory(scope,config) if self.transport_factory else fixture_transport() if fixture else None
            def on_request():
                with self.db.session.begin() as session:session.execute(update(AuditRun).where(AuditRun.id==key).values(requests=AuditRun.requests+1))
            fetcher=Fetcher(scope,config,transport=transport,sleeper=(lambda seconds:None) if fixture else self.sleeper,
                            cancelled=lambda:self.cancelled(key),on_request=on_request)
            robots={}
            def get_robots(url):
                parts=urlsplit(url);origin=urlunsplit((parts.scheme,parts.netloc,'','',''))
                if origin not in robots:
                    result=fetcher.fetch(origin+'/robots.txt',body_limit=512*1024)
                    robots[origin]=Robots.parse(result)
                    info=robots[origin]
                    coverage['robots'][origin]={'state':info.state,'status':info.status,'error':info.error,'googlebot_evaluation':'simulation'}
                    fetcher.host_delays[parts.hostname]=max(0,min(60,info.delay('LocalSEOWorkspace')))
                    self.coverage(key,coverage)
                return robots[origin]
            def guard(url):return get_robots(url).allowed(url) is True
            get_robots(config['root_url'])
            self.discover(key,scope,config['root_url'],'start',0)
            for url in config['important_urls']:self.discover(key,scope,url,'important',None)
            for url in config['intents']:self.discover(key,scope,url,'import',None)
            if property_id and config['use_gsc']:
                self.gsc_seeds(key,scope,property_id,coverage)
            self.phase(key,'Đọc XML sitemap')
            origins=[urlunsplit((urlsplit(config['root_url']).scheme,urlsplit(config['root_url']).netloc,'','',''))]
            sitemap_queue=[(u,0) for u in config['sitemap_urls']+get_robots(config['root_url']).sitemaps+[origins[0]+'/sitemap.xml',origins[0]+'/sitemap_index.xml']]
            seen=set();valid=False
            while sitemap_queue and len(seen)<10:
                if self.cancelled(key):raise CrawlError('cancelled','Đã hủy audit.')
                raw,depth=sitemap_queue.pop(0)
                try:url=scope.check(normalize(raw,config['root_url']))
                except CrawlError:coverage['warnings'].append('Bỏ qua sitemap ngoài scope hoặc URL không an toàn.');continue
                if url in seen:continue
                seen.add(url);data={};status=None
                if not guard(url):data={'valid':False,'error':'robots_blocked_or_unknown'}
                else:
                    try:
                        result=fetcher.fetch(url,guard,MAX_XML);status=result.status
                        if result.error or result.truncated or not status or not 200<=status<300:
                            data={'valid':False,'error':result.error or 'http_or_size_error','content_type':result.headers.get('content-type','')}
                        else:
                            kind,entries=parse_sitemap(result.body);valid=True
                            data={'valid':True,'kind':kind,'entries':len(entries),'content_type':result.headers.get('content-type','')}
                            if kind=='sitemapindex':
                                if depth>=3:coverage['warnings'].append('Chạm giới hạn sitemap index sâu 3 cấp.')
                                else:sitemap_queue.extend((row['url'],depth+1) for row in entries[:100])
                            else:
                                for row in entries:self.discover(key,scope,row['url'],'sitemap',None,{'sitemap_lastmod':[row['lastmod']]})
                    except CrawlError as exc:
                        if exc.code=='cancelled':raise
                        data={'valid':False,'error':exc.code}
                with self.db.session.begin() as session:session.add(AuditSitemap(id=str(uuid4()),audit_id=key,url=url,status_code=status,data=data))
            if sitemap_queue:coverage['warnings'].append('Chạm giới hạn 10 sitemap; còn tài liệu chưa đọc.')
            coverage['sitemap_valid']=valid;coverage['sources']['sitemap']='detected' if valid else 'unavailable'
            self.coverage(key,coverage)
            self.phase(key,'Crawl và phân tích HTML')
            processed=0
            while processed<config['max_urls']:
                if self.cancelled(key):raise CrawlError('cancelled','Đã hủy audit.')
                with self.db.session() as session:
                    row=session.scalar(select(AuditURL).where(AuditURL.audit_id==key,AuditURL.state=='queued').order_by(AuditURL.depth.is_(None),AuditURL.depth,AuditURL.url).limit(1))
                    if not row:break
                robot=get_robots(row.url);allowed=robot.allowed(row.url)
                if allowed is not True:
                    with self.db.session.begin() as session:
                        item=require(session,AuditURL,row.id);item.state='robots_blocked' if allowed is False else 'robots_unknown'
                        item.indexability='robots_blocked' if allowed is False else 'unknown'
                        item.data={**item.data,'robots_allowed':allowed,'googlebot_allowed':robot.allowed(row.url,'Googlebot'),'googlebot_evaluation':'simulation'}
                else:
                    try:result=fetcher.fetch(row.url,guard)
                    except CrawlError as exc:
                        if exc.code=='cancelled':raise
                        result=Fetched(row.url,error=exc.code)
                    self.save_url(key,scope,row,result,robot,config)
                processed+=1
                with self.db.session.begin() as session:
                    progress=require(session,AuditRun,key)
                    progress.processed=processed;progress.phase=f'Đã xử lý {processed}/{config["max_urls"]} URL tối đa'
                    counts=dict(session.execute(select(AuditURL.state,func.count()).where(AuditURL.audit_id==key).group_by(AuditURL.state)).all())
                    progress.summary={'discovered':sum(counts.values()),'crawled':counts.get('fetched',0),'robots_blocked':counts.get('robots_blocked',0)}
            with self.db.session() as session:
                pending=session.scalar(select(func.count()).select_from(AuditURL).where(AuditURL.audit_id==key,AuditURL.state.in_(('queued','depth_limited','robots_unknown'))))
            if pending:coverage['warnings'].append(f'{pending} URL chưa được đánh giá đầy đủ (giới hạn hoặc robots chưa xác định).')
            if processed==0:coverage['warnings'].append('Không có URL được xử lý; kiểm tra include/exclude và scope.')
            with self.db.session() as session:
                persisted=require(session,AuditRun,key).coverage
                coverage['warnings']+=persisted.get('discovery_warnings',[])
                incomplete=session.scalar(select(func.count()).select_from(AuditURL).where(AuditURL.audit_id==key,or_technical_incomplete()))
                if incomplete:coverage['warnings'].append(f'{incomplete} URL có lỗi fetch, giới hạn body hoặc chặn truy cập; có checks chưa đánh giá.')
            coverage['warnings']=list(dict.fromkeys(coverage['warnings']))[:30]
            coverage['complete']=not pending and not coverage['warnings']
            coverage['limits']={'max_urls':config['max_urls'],'max_depth':config['max_depth'],'one_worker':True,'rendering':'raw_html_only'}
            self.coverage(key,coverage)
            self.finalize(key,'completed' if coverage['complete'] else 'partial')
        except Exception as exc:
            cancelled=isinstance(exc,CrawlError) and exc.code=='cancelled'
            safe='Đã hủy ở ranh giới an toàn; kết quả đã lưu vẫn đọc được.' if cancelled else 'Audit bị lỗi; kết quả từng URL đã lưu được giữ lại. Kiểm tra cấu hình/mạng/dung lượng rồi chạy lại.'
            try:
                with self.db.session.begin() as session:
                    run=require(session,AuditRun,key);run.error=safe
                    run.coverage={**run.coverage,'complete':False,'failure_code':exc.code if isinstance(exc,CrawlError) else 'technical_internal_error'}
                self.finalize(key,'cancelled' if cancelled else 'failed')
            except Exception:
                self.failures[key]={'status':'failed','error':'Không ghi được trạng thái audit. Kiểm tra SQLite/dung lượng và khởi động lại.','phase':'Lỗi lưu dữ liệu'}
            if not cancelled:logger.warning('Technical audit failed (%s); no URL, body or credential logged',type(exc).__name__)
        finally:
            if fetcher:fetcher.close()

    def phase(self,key,text):
        with self.db.session.begin() as session:session.execute(update(AuditRun).where(AuditRun.id==key).values(phase=text))

    def coverage(self,key,value):
        with self.db.session.begin() as session:
            run=require(session,AuditRun,key)
            run.coverage={**value,'discovery_warnings':run.coverage.get('discovery_warnings',[])}

    def discover(self,key,scope,raw,source,depth,extra=None,original=None):
        try:url=normalize(raw,query_policy=scope.config['query_policy'])
        except CrawlError:return
        if not scope.allowed(url):return
        with self.db.session.begin() as session:
            old=session.scalar(select(AuditURL).where(AuditURL.audit_id==key,AuditURL.url==url))
            if old:
                old.sources=sorted(set(old.sources+[source]))
                forms=old.data.get('original_forms',[old.original_url])
                if (original or raw) not in forms and len(forms)<10:old.data={**old.data,'original_forms':forms+[original or raw]}
                if extra:
                    for k,v in extra.items():old.data={**old.data,k:list(dict.fromkeys(old.data.get(k,[])+v)) if isinstance(v,list) else v}
                if depth is not None and (old.depth is None or depth<old.depth):old.depth=depth
                return
            count=session.scalar(select(func.count()).select_from(AuditURL).where(AuditURL.audit_id==key))
            if count>=min(20000,scope.config['max_urls']*5):
                run=require(session,AuditRun,key);run.coverage={**run.coverage,'discovery_warnings':['Chạm giới hạn URL discovery; không kết luận đã bao phủ toàn website.']};return
            intent=scope.config.get('intents',{}).get(url,{'importance':'important' if url==scope.root else 'supporting','should_index':'yes' if url==scope.root or source in ('important','sitemap') else 'undecided'})
            item=AuditURL(id=str(uuid4()),audit_id=key,url=url,original_url=original or raw,state='depth_limited' if depth is not None and depth>scope.config['max_depth'] else 'queued',
                depth=depth,title='',indexability='unknown',inbound=0,outbound=0,sources=[source],data={'intent':intent,'original_forms':[original or raw],**(extra or {})})
            session.add(item)

    def save_url(self,key,scope,row,result,robot,config):
        headers=result.headers;ctype=headers.get('content-type','')
        is_html='text/html' in ctype or 'application/xhtml+xml' in ctype
        data={'html':is_html}
        if is_html and not result.truncated and not result.error:data=extract(result.body,headers,result.url)
        data.update(content_type=ctype,content_length=len(result.body),headers=headers,redirect_chain=result.chain,
            fetch_error=result.error,truncated=result.truncated,final_status=result.status,
            robots_allowed=True,googlebot_allowed=robot.allowed(row.url,'Googlebot'),googlebot_evaluation='simulation',rendering_status='raw_html_only')
        if data.get('html'):
            data['blocked_resources']=[resource for resource in (normalize_or_none(v,result.url) for v in data.get('resources',[])) if resource and urlsplit(resource).hostname==urlsplit(row.url).hostname and robot.allowed(resource,'Googlebot') is False][:30]
        first_status=result.chain[0]['status'] if result.chain else result.status
        with self.db.session.begin() as session:
            item=require(session,AuditURL,row.id)
            item.data={**item.data,**{k:v for k,v in data.items() if k not in ('links','resources','base')}}
            item.title=data.get('title','')[:3000];item.state='fetched';item.status_code=first_status
            item.final_url=result.url;item.duration_ms=result.duration_ms;item.crawled_at=now()
            item.indexability=indexability(first_status,'fetched',item.data,item.url)
            if data.get('extraction_limited'):
                run=require(session,AuditRun,key);run.coverage={**run.coverage,'discovery_warnings':['Có trang vượt giới hạn trích xuất links/headings; dữ liệu có thể thiếu.']}
        if result.chain:
            if result.url!=row.url:self.discover(key,scope,result.url,'redirect',row.depth)
            return
        if not first_status or not 200<=first_status<300 or result.error or result.truncated:return
        discovered=[];saved_links=[]
        for link in data.get('links',[]):
            target=normalize_or_none(link['href'],data.get('base') or result.url)
            if not target:continue
            internal=urlsplit(target).hostname in scope.hosts
            saved_links.append(AuditLink(audit_id=key,source_id=row.id,target_url=target,anchor=link['anchor'].strip()[:500],rel=link['rel'][:200],context=link['context'],internal=internal))
            if internal:discovered.append((target,link['href']))
        with self.db.session.begin() as session:
            count=session.scalar(select(func.count()).select_from(AuditLink).where(AuditLink.audit_id==key))
            remaining=max(0,100000-count)
            session.add_all(saved_links[:remaining])
            if len(saved_links)>remaining:
                run=require(session,AuditRun,key);run.coverage={**run.coverage,'discovery_warnings':['Chạm giới hạn 100.000 liên kết; link graph có thể thiếu.']}
        for target,original in dict.fromkeys(discovered):self.discover(key,scope,target,'html',row.depth+1 if row.depth is not None else None,original=original)
        for canonical in data.get('canonical',[]):self.discover(key,scope,canonical,'canonical',None)

    def gsc_seeds(self,key,scope,property_id,coverage):
        with self.db.session() as session:
            end=session.scalar(select(func.max(MetricFact.date)).where(MetricFact.property_id==property_id,MetricFact.dataset_type=='page',MetricFact.search_type=='web'))
            if not end:
                coverage['sources']['gsc']='unavailable';return
            start=(date.fromisoformat(end)-timedelta(days=27)).isoformat()
            rows=session.execute(select(MetricFact.dimension_value,func.sum(MetricFact.clicks),func.sum(MetricFact.impressions)).where(
                MetricFact.property_id==property_id,MetricFact.dataset_type=='page',MetricFact.search_type=='web',MetricFact.date>=start,MetricFact.date<=end)
                .group_by(MetricFact.dimension_value).order_by(func.sum(MetricFact.clicks).desc()).limit(5001)).all()
        coverage['sources']['gsc']='stored_page_performance'
        coverage['gsc']={'start':start,'end':end,'search_type':'web','scope':'page/byPage; không phải tổng site hoặc Page Indexing','seed_limit':5000}
        if len(rows)>5000:coverage['warnings'].append('GSC seeds giới hạn Top 5.000 URL đã lưu.')
        for url,clicks,impressions in rows[:5000]:self.discover(key,scope,url,'gsc',None,{'gsc':{'clicks':clicks,'impressions':impressions,'start':start,'end':end,'search_type':'web','source':'stored_page_byPage'}})

    def finalize(self,key,status):
        self.phase(key,'Tính link graph và đánh giá rules')
        with self.db.session.begin() as session:
            run=require(session,AuditRun,key)
            urls=list(session.scalars(select(AuditURL).where(AuditURL.audit_id==key)))
            links=list(session.scalars(select(AuditLink).where(AuditLink.audit_id==key)))
            sitemaps=list(session.scalars(select(AuditSitemap).where(AuditSitemap.audit_id==key)))
            by_id={u.id:u for u in urls};by_url={u.url:u for u in urls};graph=defaultdict(list);incoming=defaultdict(set);outgoing=defaultdict(set)
            for link in links:
                source=by_id[link.source_id]
                if link.internal:
                    graph[source.url].append((link.target_url,1))
                    if source.url!=link.target_url:incoming[link.target_url].add(source.url)
                    outgoing[source.url].add(link.target_url)
            for u in urls:
                if u.data.get('redirect_chain') and u.final_url and u.final_url!=u.url:graph[u.url].append((u.final_url,0))
            distances={};queue=[(0,run.config['root_url'])]
            while queue:
                depth,url=heapq.heappop(queue)
                if url in distances:continue
                distances[url]=depth
                for target,cost in graph[url]:
                    if target not in distances:heapq.heappush(queue,(depth+cost,target))
            for u in urls:u.depth=distances.get(u.url);u.inbound=len(incoming[u.url]);u.outbound=len(outgoing[u.url])
            findings,checks=evaluate(urls,links,sitemaps,run)
            # Finalizing once; interrupted runs are restarted as NEW immutable snapshots.
            session.execute(delete(AuditIssue).where(AuditIssue.audit_id==key))
            tasks={task.fingerprint:task for task in session.scalars(select(AuditTask).where(AuditTask.project_id==run.project_id))}
            observed=set()
            for finding in findings:
                fingerprint=finding['fingerprint'];observed.add(fingerprint);task=tasks.get(fingerprint)
                first=task.first_seen_at if task else now()
                session.add(AuditIssue(id=str(uuid4()),audit_id=key,project_id=run.project_id,first_seen_at=first,last_seen_at=now(),**finding))
                if task:
                    task.last_seen_at=now();task.priority=finding['priority'];task.severity=finding['severity']
                    if task.status in ('fixed','resolved'):task.status='open';task.verification='reopened'
                    else:task.verification='observed'
                    task.verification_audit_id=key
                else:session.add(AuditTask(id=str(uuid4()),project_id=run.project_id,fingerprint=fingerprint,rule_id=finding['rule_id'],url=finding['url'],title=finding['title'],severity=finding['severity'],
                    status='open',owner='',notes='',verification='observed',verification_audit_id=key,priority=finding['priority'],first_seen_at=first,last_seen_at=now()))
            if run.coverage.get('complete') and status=='completed':
                for fingerprint,task in tasks.items():
                    previous=session.scalar(select(AuditRun).join(AuditIssue,AuditIssue.audit_id==AuditRun.id).where(AuditIssue.fingerprint==fingerprint,AuditRun.project_id==run.project_id,AuditRun.id!=key).order_by(AuditRun.started_at.desc()).limit(1))
                    prior_issue=session.scalar(select(AuditIssue).where(AuditIssue.fingerprint==fingerprint,AuditIssue.audit_id==previous.id)) if previous else None
                    if fingerprint not in observed and previous and previous.scope_hash==run.scope_hash and previous.rule_version==run.rule_version and prior_issue and absence_verified(prior_issue,by_url,checks):
                        task.verification='verified_absent';task.verification_audit_id=key
                        if task.status!='ignored':task.status='resolved'
            for u in urls:u.data={**u.data,'checked_rules':checks.get(u.url,[]),'disposition':'manual_review' if u.indexability not in ('indexable_candidate','noindex') else 'improve' if any(f['url']==u.url for f in findings) else 'keep'}
            http=Counter('network_error' if u.status_code is None else '429' if u.status_code==429 else str(u.status_code//100)+'xx' for u in urls if u.state=='fetched')
            run.summary={'discovered':len(urls),'crawled':sum(u.state=='fetched' for u in urls),'robots_blocked':sum(u.state=='robots_blocked' for u in urls),
                'http':dict(http),'indexability':dict(Counter(u.indexability for u in urls)),'severity':dict(Counter(f['severity'] for f in findings)),
                'issues':len(findings),'critical':sum(f['severity']=='critical' for f in findings),'high':sum(f['severity']=='high' for f in findings),
                'broken_links':sum(link.internal and link.target_url in by_url and (by_url[link.target_url].status_code or 0)>=400 for link in links),
                'redirects':sum(bool(u.data.get('redirect_chain')) for u in urls),'sitemap_errors':sum(f['category']=='SITEMAP' for f in findings),
                'canonical_issues':sum(f['category']=='CAN' for f in findings),'maximum_depth':max((d for d in distances.values()),default=0),
                'checks':dict(Counter(rid for values in checks.values() for rid in values))}
            run.status=status;run.finished_at=now();run.phase='Hoàn tất' if status=='completed' else 'Kết quả một phần' if status=='partial' else 'Đã hủy' if status=='cancelled' else 'Lỗi audit'


def normalize_or_none(value,base):
    if not value:return None
    try:return normalize(value.strip(),base)
    except CrawlError:return None


def or_technical_incomplete():
    from sqlalchemy import or_
    return or_(AuditURL.data['fetch_error'].as_string().is_not(None),AuditURL.data['truncated'].as_boolean()==True,
               AuditURL.status_code.in_((401,403,429,500,502,503,504)))
