import gzip
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.db.database import Database
from app.db.models import Connection, MetricFact, Property
from app.gsc.runtime import Runtime, get_runtime
from app.main import app
from app.technical.extract import extract, indexability, noindex
from app.technical.fetch import Fetcher, Fetched, SafeNetworkBackend
from app.technical.fixtures import ROOT, fixture_transport
from app.technical.jobs import AuditManager
from app.technical.models import AuditIssue, AuditLink, AuditProject, AuditRun, AuditTask, AuditURL
from app.technical.reports import comparison, overview
from app.technical.robots import Robots
from app.technical.schemas import AuditInput, CrawlConfig, ProjectInput
from app.technical.sitemap import MAX_XML, lastmod_state, parse_sitemap
from app.technical.urls import CrawlError, Scope, normalize, public_ip


@pytest.fixture
def manager(tmp_path):
    db=Database(tmp_path/'technical.db');db.migrate()
    value=AuditManager(db)
    yield value
    value.close();db.engine.dispose()


def project(manager,**config):
    return manager.create_project(ProjectInput(root_url=ROOT,config=CrawlConfig(**config)),fixture=True)


def audit(manager,proj,config=None):
    result=manager.start(AuditInput(project_id=proj.id,config=config),submit=False)
    manager.run(result.id)
    return manager.get(result.id)


@pytest.mark.parametrize('raw,expected',[
    ('HTTPS://Public.Example.org:443/a%7eb/#fragment','https://public.example.org/a~b/'),
    ('https://public.example.org/a/../b','https://public.example.org/b'),
    ('https://public.example.org/a','https://public.example.org/a'),
    ('https://public.example.org/a/','https://public.example.org/a/'),
    ('https://public.example.org/?x=1&x=2','https://public.example.org/?x=1&x=2'),
])
def test_url_identity(raw,expected):assert normalize(raw)==expected


@pytest.mark.parametrize('url',['http://127.0.0.1/','http://169.254.169.254/','http://10.0.0.1/','http://localhost/','http://2130706433/','http://[::1]/','https://user:password@public.example.org/','file:///etc/passwd','https://public.example.org:8000/','https://public.example.org/checkout','https://public.example.org/?action=delete'])
def test_reject_unsafe_root(url):
    with pytest.raises(CrawlError):Scope(url,CrawlConfig().model_dump())


def test_normalization_scope_and_query_policies():
    config=CrawlConfig(include_patterns=['/blog/*'],exclude_patterns=['/blog/private*']).model_dump()
    scope=Scope('https://public.example.org/',config)
    assert scope.allowed('https://public.example.org/blog/a')
    assert not scope.allowed('https://public.example.org/blog/private-a')
    assert not scope.allowed('https://other.example.org/blog/a')
    assert normalize('../a?sort=price&utm_source=test','https://public.example.org/blog/', 'drop_tracking')=='https://public.example.org/a?sort=price'
    assert normalize('https://public.example.org/?sort=price',query_policy='preserve').endswith('?sort=price')


def test_dns_rebinding_mixed_addresses_and_socket_ip_pinning():
    resolver=Mock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))])
    backend=SafeNetworkBackend({'public.example.org'},resolver)
    with patch('httpcore._backends.sync.SyncBackend.connect_tcp',return_value='stream') as dial:
        assert backend.connect_tcp('public.example.org',443,timeout=3)=='stream'
        assert dial.call_args.args[0]=='8.8.8.8'
        resolver.return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
        with pytest.raises(CrawlError):backend.connect_tcp('public.example.org',443)
        assert dial.call_count==1
        resolver.return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]
        with pytest.raises(CrawlError):backend.connect_tcp('public.example.org',443)
    with pytest.raises(CrawlError):backend.connect_tcp('evil.example.org',443)
    assert not public_ip('64:ff9b::7f00:1') and not public_ip('2002:7f00:1::')


def fetcher(handler,**kwargs):
    config=CrawlConfig(delay_seconds=.5).model_dump();scope=Scope('https://public.example.org/',config)
    return Fetcher(scope,config,transport=httpx.MockTransport(handler),sleeper=lambda _:None,**kwargs)


def test_redirect_chain_loop_and_external_destination_blocked():
    calls=[]
    def handler(request):
        calls.append(str(request.url));p=request.url.path
        return httpx.Response(301,headers={'location':{'/':'/a','/a':'/b','/loop':'/loop','/external':'http://127.0.0.1/'}[p]}) if p!='/b' else httpx.Response(200,text='ok')
    f=fetcher(handler)
    result=f.fetch('https://public.example.org/');assert len(result.chain)==2 and result.url.endswith('/b')
    assert f.fetch('https://public.example.org/loop').error=='redirect_loop'
    assert f.fetch('https://public.example.org/external').error=='external_or_unsafe_redirect'
    assert all('127.0.0.1' not in url for url in calls)
    blocked=f.fetch('https://public.example.org/',redirect_guard=lambda url:not url.endswith('/a'))
    assert blocked.error=='redirect_robots_blocked'
    f.close()


def test_timeout_size_cap_retry_after_and_host_stop():
    def timeout(request):raise httpx.ReadTimeout('timeout',request=request)
    f=fetcher(timeout);assert f.fetch('https://public.example.org/').error=='timeout';f.close()
    f=fetcher(lambda request:httpx.Response(200,content=b'x'*100));assert f.fetch('https://public.example.org/',body_limit=50).truncated;f.close()
    count=[]
    def quota(request):count.append(1);return httpx.Response(429,headers={'retry-after':'120'})
    f=fetcher(quota);assert f.fetch('https://public.example.org/').status==429
    assert f.fetch('https://public.example.org/other').error=='host_backoff';assert len(count)==1;f.close()


def test_robots_groups_wildcards_longest_match_and_unknown():
    robots=Robots.parse(Fetched(ROOT+'robots.txt',200,body=b'User-agent: *\nDisallow: /private*\nAllow: /private/public$\nUser-agent: Googlebot\nDisallow: /google\nCrawl-delay: 2\n'))
    assert robots.allowed(ROOT+'private/a') is False
    assert robots.allowed(ROOT+'private/public') is True
    assert robots.allowed(ROOT+'google','Googlebot') is False
    assert robots.allowed(ROOT+'private/a','Googlebot') is True
    assert Robots.parse(Fetched(ROOT,status=503)).allowed(ROOT) is None
    assert Robots.parse(Fetched(ROOT,status=403)).allowed(ROOT) is False
    assert Robots.parse(Fetched(ROOT,status=404)).allowed(ROOT) is True
    grouped=Robots.parse(Fetched(ROOT,status=200,body=b'User-agent: *\nDisallow:\nUser-agent: Googlebot\nDisallow: /\n'))
    assert grouped.allowed(ROOT) is True and grouped.allowed(ROOT,'Googlebot') is False


def test_extraction_canonical_headers_headings_robots_and_breadcrumb():
    body=b'<html lang="en"><head><title>A title</title><meta name="robots" content="index"><link rel="canonical" href="/a"></head><body><h1>One</h1><h3>Three</h3><nav aria-label="breadcrumb"><a href="../b"> Anchor </a></nav><script>private script text</script></body></html>'
    result=extract(body,{'content-type':'text/html','link':'<https://public.example.org/b>; rel="canonical"','x-robots-tag':'noindex'},'https://public.example.org/a')
    assert result['title']=='A title' and len(result['canonical'])==2
    assert result['links'][0]['anchor'].strip()=='Anchor' and result['breadcrumbs']
    assert result['headings'][1]['level']==3 and noindex(result)
    assert not noindex({'x_robots_tag':'bingbot: noindex'})
    assert not noindex({'x_robots_tag':'bingbot: nofollow, noindex'})
    assert noindex({'x_robots_tags':['bingbot: nofollow','noindex']})
    assert indexability(200,'fetched',result,'https://public.example.org/a')=='noindex'


def test_network_body_gzip_bomb_is_bounded_before_expansion():
    compressed=gzip.compress(b'x'*1_000_000)
    f=fetcher(lambda request:httpx.Response(200,headers={'content-encoding':'gzip'},stream=httpx.ByteStream(compressed)))
    result=f.fetch('https://public.example.org/',body_limit=10_000)
    assert result.truncated and len(result.body)<=10_000
    f.close()


def test_rate_delay_and_cancellation_are_not_bypassed():
    state={'time':0.,'cancelled':False};requests=[]
    config=CrawlConfig(delay_seconds=1).model_dump();scope=Scope('https://public.example.org/',config)
    def sleep(seconds):state['time']+=seconds
    f=Fetcher(scope,config,transport=httpx.MockTransport(lambda request:(requests.append(state['time']) or httpx.Response(200))),sleeper=sleep,clock=lambda:state['time'],cancelled=lambda:state['cancelled'])
    f.fetch('https://public.example.org/');f.fetch('https://public.example.org/b')
    assert requests[1]-requests[0]>=1
    state['cancelled']=True
    with pytest.raises(CrawlError,match='hủy'):f.fetch('https://public.example.org/c')
    assert len(requests)==2;f.close()


def test_trickling_response_has_deadline_and_checks_cancellation():
    state={'time':0,'cancelled':False,'emitted':0}
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                state['time']+=1;state['emitted']+=1;yield b'x'
    config=CrawlConfig(timeout_seconds=2).model_dump();scope=Scope('https://public.example.org/',config)
    f=Fetcher(scope,config,transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Stream())),sleeper=lambda _:None,clock=lambda:state['time'])
    result=f.fetch('https://public.example.org/')
    assert result.error=='timeout' and state['emitted']==3
    f.close()


def test_actual_resolution_reopening_and_incomplete_evidence(manager):
    state={'broken':True,'timeout':False}
    def transport(scope,config):
        def respond(request):
            if request.url.path=='/robots.txt':return httpx.Response(404)
            if request.url.path!='/' :return httpx.Response(404)
            if state['timeout']:raise httpx.ReadTimeout('expected test timeout',request=request)
            title='' if state['broken'] else '<title>Fixed title</title>'
            body='<html lang="en"><head>'+title+'<meta name="description" content="description"><link rel="canonical" href="'+ROOT+'"></head><body><main><h1>Heading</h1>'+('words '*110)+'</main></body></html>'
            return httpx.Response(200,headers={'content-type':'text/html'},text=body)
        return httpx.MockTransport(respond)
    manager.transport_factory=transport;p=project(manager)
    first=audit(manager,p)
    state['broken']=False;second=audit(manager,p)
    result=comparison(manager.db,first.id,second.id)
    assert result['comparable'] and any(row['rule_id']=='TECH-ONPAGE-001' and row['state']=='resolved' for row in result['rows'])
    state['broken']=True;third=audit(manager,p)
    result=comparison(manager.db,second.id,third.id)
    assert any(row['rule_id']=='TECH-ONPAGE-001' and row['state']=='reopened' for row in result['rows'])
    state['timeout']=True;fourth=audit(manager,p)
    result=comparison(manager.db,third.id,fourth.id)
    assert not result['comparable'] and not result['counts'].get('resolved')
    assert any(row['rule_id']=='TECH-ONPAGE-001' and row['state']=='not_observed' for row in result['rows'])


def test_gsc_page_exposure_is_frozen_and_does_not_require_oauth(manager):
    stamp='2026-10-20T00:00:00+00:00'
    with manager.db.session.begin() as session:
        session.add(Connection(id='gsc-test',display_name='test',provider='google',status='disconnected',scope='readonly',created_at=stamp,updated_at=stamp));session.flush()
        session.add(Property(id='property-test',connection_id='gsc-test',site_url='sc-domain:public.example.org',display_name='test',property_type='domain',permission_level='siteOwner',source_type='gsc',is_active=True,added_at=stamp));session.flush()
        session.add(MetricFact(property_id='property-test',date='2026-10-20',search_type='web',dataset_type='page',dimension_value='https://public.example.org/',aggregation_type='byPage',clicks=17,impressions=123,ctr=17/123,position=2,data_state='final',fetched_at=stamp))
    def transport(scope,config):
        return httpx.MockTransport(lambda request:httpx.Response(404) if request.url.path!='/' else httpx.Response(200,headers={'content-type':'text/html'},text='<html><h1>Page</h1></html>'))
    manager.transport_factory=transport;manager.sleeper=lambda _:None
    p=manager.create_project(ProjectInput(root_url='https://public.example.org/',property_id='property-test',config=CrawlConfig(max_urls=5)))
    first=audit(manager,p)
    with manager.db.session() as session:
        row=session.scalar(select(AuditURL).where(AuditURL.audit_id==first.id))
        assert row.data['gsc']['clicks']==17 and row.data['gsc']['impressions']==123 and row.data['gsc']['source']=='stored_page_byPage'
        assert row.data.get('google_index_status') is None
        assert session.scalar(select(func.sum(MetricFact.clicks)))==17
    assert first.coverage['sources']['gsc']=='stored_page_performance'


def test_additive_migration_preserves_existing_gsc_rows(tmp_path):
    from alembic import command
    from alembic.config import Config
    from app.db.database import BACKEND
    db=Database(tmp_path/'upgrade.db');config=Config();config.set_main_option('script_location',str(BACKEND/'migrations'))
    with db.engine.begin() as connection:
        config.attributes['connection']=connection;command.upgrade(config,'001_gsc_storage')
        connection.exec_driver_sql("INSERT INTO google_connections VALUES ('keep','Keep','google','connected','readonly','date','date')")
        connection.exec_driver_sql("INSERT INTO app_settings VALUES ('keep_setting','keep_value')")
    db.migrate()
    with db.engine.connect() as connection:
        assert connection.scalar(text("SELECT display_name FROM google_connections WHERE id='keep'"))=='Keep'
        assert connection.scalar(text("SELECT value FROM app_settings WHERE key='keep_setting'"))=='keep_value'
        assert connection.scalar(text('SELECT count(*) FROM technical_projects'))==0
        assert connection.scalar(text('PRAGMA foreign_keys'))==1
    db.engine.dispose()


def test_truncated_html_and_invalid_canonical_do_not_become_false_passes(manager):
    def transport(scope,config):
        return httpx.MockTransport(lambda request:httpx.Response(404) if request.url.path!='/' else httpx.Response(200,headers={'content-type':'text/html'},stream=httpx.ByteStream(b'x'*(2*1024*1024+1))))
    manager.transport_factory=transport;p=project(manager);run=audit(manager,p)
    assert run.status=='partial'
    with manager.db.session() as session:
        keys=set(session.scalars(select(AuditIssue.rule_id).where(AuditIssue.audit_id==run.id)))
        assert 'TECH-ONPAGE-010' in keys and 'TECH-ONPAGE-001' not in keys
    data=extract(b'<html><link rel="canonical" href="https://public.example.org:8000/a"></html>',{'content-type':'text/html'},'https://public.example.org/')
    assert data['canonical_invalid'] and indexability(200,'fetched',data,'https://public.example.org/')=='unknown'


def test_metadata_limits_are_explicit_and_title_storage_is_bounded():
    body=('<html><title>'+('x'*4000)+'</title>'+''.join(f'<script src="/file-{n}.js"></script>' for n in range(201))+'</html>').encode()
    data=extract(body,{'content-type':'text/html'},ROOT)
    assert len(data['title'])==3000 and data['extraction_limited']
    assert len(data['resources'])==200


def test_csv_formula_and_print_html_escaping(manager):
    p=project(manager);run=audit(manager,p)
    with manager.db.session.begin() as session:
        url=session.scalar(select(AuditURL).where(AuditURL.audit_id==run.id));url.title='=SUM(1,2)'
        session.get(AuditProject,p.id).name='<script>alert(1)</script>'
    app.dependency_overrides[get_runtime]=lambda:SimpleNamespace(db=manager.db,technical=manager)
    try:
        with TestClient(app,base_url='http://127.0.0.1') as client:
            import csv,io
            response=client.get(f'/api/technical/audits/{run.id}/export?format=csv&dataset=urls')
            rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
            assert any(row[6]=="'=SUM(1,2)" for row in rows[1:])
            response=client.get(f'/api/technical/audits/{run.id}/export?format=html')
            assert '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text and '<script>alert(1)</script>' not in response.text
    finally:app.dependency_overrides.clear()


def test_dashboard_summary_only_when_live_audit_matches_site(manager):
    from app.api.technical_routes import dashboard_summary
    runtime=SimpleNamespace(db=manager.db,technical=manager)
    assert dashboard_summary(runtime,'xuong-may') is None
    manager.transport_factory=lambda scope,config:httpx.MockTransport(lambda request:httpx.Response(404) if request.url.path!='/' else httpx.Response(200,headers={'content-type':'text/html'},text='<html><h1>Test</h1></html>'))
    manager.sleeper=lambda _:None
    p=manager.create_project(ProjectInput(root_url='https://xuongmaybalogiare.com/',config=CrawlConfig(max_urls=1)))
    r=audit(manager,p)
    assert dashboard_summary(runtime,'xuong-may')['id']==r.id
    assert dashboard_summary(runtime,'cong-ty') is None


def test_same_rule_keeps_multiple_broken_target_observations(manager):
    def transport(scope,config):
        def respond(request):
            if request.url.path!='/':return httpx.Response(404)
            return httpx.Response(200,headers={'content-type':'text/html'},text='<html><title>A</title><h1>One</h1><a href="/missing-a">A</a><a href="/missing-b">B</a></html>')
        return httpx.MockTransport(respond)
    manager.transport_factory=transport;p=project(manager);r=audit(manager,p)
    with manager.db.session() as session:
        issues=list(session.scalars(select(AuditIssue).where(AuditIssue.audit_id==r.id,AuditIssue.rule_id=='TECH-LINK-004')))
        assert len(issues)==1
        evidence=issues[0].evidence
        assert {evidence['target'],evidence['additional_observations'][0]['target']}=={ROOT+'missing-a',ROOT+'missing-b'}
        assert evidence['additional_observations_count']==1


def test_interrupted_url_graph_values_are_unknown_not_zero(manager):
    from app.technical.reports import list_urls,url_detail
    p=project(manager);r=manager.start(AuditInput(project_id=p.id),submit=False)
    scope=Scope(ROOT,CrawlConfig().model_dump(),fixture=True)
    manager.discover(r.id,scope,ROOT,'start',0)
    result=list_urls(manager.db,r.id)
    row=result['rows'][0]
    assert row['inbound'] is None and row['outbound'] is None and row['depth'] is None
    assert url_detail(manager.db,r.id,row['id'])['inbound'] is None


def test_blocked_dependency_cannot_resolve_link_or_duplicate_finding(manager):
    state={'blocked':False}
    def transport(scope,config):
        def respond(request):
            path=request.url.path
            if path=='/robots.txt':return httpx.Response(200,text='User-agent: *\nDisallow: '+('/bad\nDisallow: /duplicate' if state['blocked'] else ''))
            if path in ('/sitemap.xml','/sitemap_index.xml','/bad'):return httpx.Response(404)
            body='<a href="/bad">bad</a><a href="/good">good</a><a href="/duplicate">duplicate</a>' if path=='/' else ''
            return httpx.Response(200,headers={'content-type':'text/html'},text='<html lang="en"><title>'+('Unique' if path=='/good' else 'Duplicate')+'</title><h1>H</h1>'+body+'</html>')
        return httpx.MockTransport(respond)
    manager.transport_factory=transport;p=project(manager);before=audit(manager,p)
    state['blocked']=True;after=audit(manager,p)
    result=comparison(manager.db,before.id,after.id)
    relevant=[row for row in result['rows'] if row['url']==ROOT and row['rule_id'] in ('TECH-LINK-004','TECH-ONPAGE-001')]
    assert relevant and all(row['state']=='not_observed' for row in relevant)
    with manager.db.session() as session:
        for task in session.scalars(select(AuditTask).where(AuditTask.url==ROOT,AuditTask.rule_id.in_(('TECH-LINK-004','TECH-ONPAGE-001')))):
            assert task.verification!='verified_absent'


@pytest.mark.parametrize('status,state,data,expected',[
    (200,'fetched',{'html':True},'indexable_candidate'),(200,'fetched',{'html':True,'meta_robots':[{'content':'noindex'}]},'noindex'),
    (None,'robots_blocked',{},'robots_blocked'),(200,'fetched',{'html':True,'canonical':[ROOT+'other']},'canonicalized'),
    (301,'fetched',{'redirect_chain':[{}]},'redirected'),(404,'fetched',{},'error'),(200,'fetched',{'html':False},'unknown'),
])
def test_indexability_states(status,state,data,expected):assert indexability(status,state,data,ROOT)==expected


def test_xml_valid_index_lastmod_entities_and_gzip_limit():
    kind,rows=parse_sitemap(b'<urlset><url><loc>https://public.example.org/a</loc><lastmod>2099-01-01</lastmod></url></urlset>')
    assert kind=='urlset' and lastmod_state(rows[0]['lastmod'])=='future'
    assert lastmod_state('bad')=='invalid' and lastmod_state('')=='missing'
    assert parse_sitemap(b'<sitemapindex><sitemap><loc>https://public.example.org/s.xml</loc></sitemap></sitemapindex>')[0]=='sitemapindex'
    for body in (b'<invalid',b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><urlset>&e;</urlset>',gzip.compress(b'x'*(MAX_XML+1))):
        with pytest.raises(CrawlError):parse_sitemap(body)


def test_crawl_rules_graph_limits_persistence_and_no_html_storage(manager):
    p=project(manager,important_urls=[ROOT+'private'])
    r=audit(manager,p)
    assert r.status=='completed' and r.summary['crawled']==7
    with manager.db.session() as session:
        urls=list(session.scalars(select(AuditURL).where(AuditURL.audit_id==r.id)))
        private=next(u for u in urls if u.url==ROOT+'private');assert private.state=='robots_blocked'
        assert not any(u.url.endswith('/checkout') for u in urls)
        orphan=next(u for u in urls if u.url==ROOT+'orphan');assert orphan.depth is None and orphan.inbound==0
        root=next(u for u in urls if u.url==ROOT);assert root.depth==0
        rules=set(session.scalars(select(AuditIssue.rule_id).where(AuditIssue.audit_id==r.id)))
        assert {'TECH-LINK-004','TECH-CAN-003','TECH-SITEMAP-006','TECH-ARCH-003','TECH-ONPAGE-001'}<=rules
        assert all('body' not in u.data and 'html_document' not in u.data for u in urls)
        assert len(urls)==len(set(u.url for u in urls))
        assert session.scalar(select(func.count()).select_from(AuditTask))==r.summary['issues']
    reopened=Database(manager.db.path);reopened.migrate()
    assert overview(reopened,r.id)['summary']==r.summary
    limited=audit(manager,p,CrawlConfig(max_urls=2,max_depth=0))
    assert limited.status=='partial' and limited.processed<=2
    assert not comparison(manager.db,r.id,limited.id)['comparable']
    assert comparison(manager.db,r.id,limited.id)['counts'].get('resolved',0)==0


def test_cancel_recovery_duplicate_jobs_and_honest_checklist(manager):
    p=project(manager)
    run=manager.start(AuditInput(project_id=p.id),submit=False)
    with pytest.raises(Exception) as error:manager.start(AuditInput(project_id=p.id),submit=False)
    assert getattr(error.value,'code',None)=='audit_already_active'
    manager.cancel(run.id);manager.run(run.id);assert manager.get(run.id).status=='cancelled'
    second=manager.start(AuditInput(project_id=p.id),submit=False)
    manager.recover();assert manager.get(second.id).status=='interrupted'
    view=overview(manager.db,second.id)
    assert not any(r['state']=='passed' for r in view['rules'])
    assert any(r['capability']=='integration_required' for r in view['rules'])


def test_history_persistent_new_resolved_and_backlog_manual_notes(manager):
    p=project(manager)
    first=audit(manager,p);second=audit(manager,p)
    comp=comparison(manager.db,first.id,second.id)
    assert comp['comparable'] and comp['counts']['persistent']>0 and comp['counts'].get('resolved',0)==0
    with manager.db.session.begin() as session:
        task=session.scalar(select(AuditTask).where(AuditTask.rule_id=='TECH-ONPAGE-001'))
        task.notes='Keep my note';task.status='fixed'
    third=audit(manager,p)
    with manager.db.session() as session:
        task=session.scalar(select(AuditTask).where(AuditTask.rule_id=='TECH-ONPAGE-001',AuditTask.notes=='Keep my note'))
        assert task.notes=='Keep my note' and task.status=='open' and task.verification=='reopened'


def test_api_validation_paging_import_export_and_retention(manager):
    runtime=SimpleNamespace(db=manager.db,technical=manager)
    app.dependency_overrides[get_runtime]=lambda:runtime
    try:
        with TestClient(app,base_url='http://127.0.0.1') as client:
            headers={'X-CSRF-Token':client.get('/api/session').json()['csrf_token']}
            unsafe=client.post('/api/technical/projects',json={'root_url':'http://127.0.0.1/'},headers=headers)
            assert unsafe.status_code==422
            response=client.post('/api/technical/fixtures',json={},headers=headers);assert response.status_code==201
            p=response.json()
            assert client.post('/api/technical/audits',json={'project_id':p['id']}).status_code==403
            r=audit(manager,SimpleNamespace(id=p['id']))
            rows=client.get(f'/api/technical/audits/{r.id}/urls?page_size=2').json();assert len(rows['rows'])==2 and rows['total']==8
            assert client.get(f'/api/technical/audits/{r.id}/urls?sort=sql_expression').status_code==422
            assert client.get(f'/api/technical/audits/{r.id}/urls?search=%25').json()['total']==0
            assert client.get(f'/api/technical/audits/{r.id}/urls/{rows["rows"][0]["id"]}').json()['google_index_status'] is None
            data='url,priority,should_index,page_type,notes\n'+ROOT+'orphan,critical_money,yes,landing,=formula\n'
            preview=client.post('/api/technical/import?project_id='+p['id'],headers=headers,files={'file':('urls.csv',data,'text/csv')})
            assert preview.status_code==200 and preview.json()['count']==1
            assert client.post('/api/technical/import/'+preview.json()['id']+'/commit',headers=headers,json={}).status_code==200
            for format in ('csv','json','html'):
                export=client.get(f'/api/technical/audits/{r.id}/export?format={format}')
                assert export.status_code==200 and 'Content-Disposition' in export.headers
            assert client.get(f'/api/technical/audits/{r.id}/export?format=html').headers['content-security-policy'].startswith("default-src 'none'")
            task=client.get('/api/technical/backlog?project_id='+p['id']).json()['rows'][0]
            saved=client.patch('/api/technical/backlog/'+task['id'],json={'status':'fixed','notes':'done','owner':'SEO'},headers=headers)
            assert saved.json()['verification']=='awaiting_recrawl'
            assert client.post(f'/api/technical/audits/{r.id}/delete',json={'confirm':False},headers=headers).status_code==422
            assert client.post(f'/api/technical/audits/{r.id}/delete',json={'confirm':True},headers=headers).status_code==200
            assert client.get(f'/api/technical/audits/{r.id}').status_code==404
    finally:app.dependency_overrides.clear()
