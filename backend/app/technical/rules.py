"""Deterministic, versioned checks. Local candidates never assert Google's index state."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from app.technical.extract import noindex
from app.technical.sitemap import lastmod_state

VERSION = '0.3-core-1'

# A catalog capability is not a passed evaluation. Collected signals and service-backed
# checks are included; every audit exposes evaluated counts separately.
IMPLEMENTED = {
    'CRAWL': [1,2,3,4,7], 'INDEX':[1,2,6,7,9,10], 'CAN':[1,2,3,4,5,6,9,10],
    'SITEMAP':[1,2,3,4,5,6,7,8,9], 'HTTP':[1,2,3,4,5,9], 'ARCH':[1,2,3,8],
    'LINK':[1,2,3,4,5,6,7,8,10], 'ONPAGE':[1,2,3,4,5,8,9,10], 'MONITOR':[1,2,3,4,5,6,8,9],
}

TITLES = {
    'CRAWL-001':'Không xác nhận được robots.txt', 'CRAWL-002':'URL quan trọng bị robots chặn',
    'CRAWL-003':'Tài nguyên CSS/JS bị robots chặn (mô phỏng)', 'CRAWL-004':'URL quan trọng trả lỗi HTTP',
    'CRAWL-007':'Nhiều biến thể query parameter',
    'INDEX-002':'Noindex trên URL dự kiến lập chỉ mục', 'INDEX-006':'Ứng viên soft 404',
    'INDEX-007':'Ứng viên nội dung ít chữ — cần xem thủ công',
    'CAN-002':'Thiếu canonical khai báo', 'CAN-003':'Canonical mâu thuẫn hoặc không hợp lệ',
    'CAN-004':'Canonical trỏ tới URL lỗi', 'CAN-005':'Canonical trỏ tới redirect',
    'CAN-006':'Canonical trỏ tới URL noindex', 'CAN-009':'Biến thể dấu / cùng trả nội dung',
    'CAN-010':'Biến thể parameter có cùng fingerprint nội dung',
    'SITEMAP-001':'Chưa phát hiện sitemap đọc được', 'SITEMAP-002':'Không truy xuất được sitemap',
    'SITEMAP-003':'XML sitemap không hợp lệ', 'SITEMAP-005':'URL trong sitemap trả lỗi hoặc redirect',
    'SITEMAP-006':'URL noindex nằm trong sitemap', 'SITEMAP-007':'URL canonicalized nằm trong sitemap',
    'SITEMAP-008':'URL chỉ được thấy từ một nguồn trong phạm vi crawl', 'SITEMAP-009':'Lastmod cần kiểm tra',
    'HTTP-002':'Chuỗi redirect nhiều bước', 'HTTP-003':'Vòng lặp hoặc vượt giới hạn redirect',
    'HTTP-004':'Redirect kết thúc lỗi hoặc ngoài scope', 'HTTP-005':'Liên kết nội bộ đi qua redirect',
    'HTTP-009':'Lỗi DNS, TLS, timeout hoặc kết nối',
    'ARCH-002':'Trang quan trọng sâu hơn 4 liên kết', 'ARCH-003':'Ứng viên orphan trong phạm vi đã quan sát',
    'LINK-004':'Liên kết nội bộ trỏ tới URL lỗi', 'LINK-005':'Liên kết trỏ tới URL chuyển hướng',
    'LINK-010':'Liên kết thiếu href có thể crawl',
    'ONPAGE-001':'Title thiếu, trùng hoặc nhiều khai báo', 'ONPAGE-002':'Meta description thiếu hoặc trùng',
    'ONPAGE-003':'H1 thiếu hoặc có nhiều khai báo', 'ONPAGE-004':'Cấp heading bị nhảy',
    'ONPAGE-008':'Thiếu thuộc tính ngôn ngữ HTML', 'ONPAGE-009':'Có lỗi giải mã ký tự',
    'ONPAGE-010':'HTML không đầy đủ để phân tích',
}

RECOMMENDATIONS = {
    'CRAWL':'Kiểm tra robots.txt/quyền truy cập và URL quan trọng. Không bỏ robots hoặc giả Googlebot để vượt chặn.',
    'INDEX':'Xác nhận mục đích lập chỉ mục, kiểm tra nội dung/directives và xác minh trong GSC; không đổi noindex hàng loạt.',
    'CAN':'Xác nhận URL đại diện rồi thống nhất canonical tới URL 200 có thể index; không tự redirect các trang khác mục đích.',
    'SITEMAP':'Đối chiếu sitemap với URL mong muốn index; sửa URL lỗi/redirect/noindex và lastmod theo thay đổi thực tế.',
    'HTTP':'Kiểm tra URL đích, status và chuỗi redirect; sửa liên kết ở nguồn. 302 không tự động là lỗi.',
    'ARCH':'Kiểm tra menu, breadcrumb và liên kết ngữ cảnh tới trang quan trọng. Kết quả orphan chỉ trong coverage đã crawl.',
    'LINK':'Sửa href ở trang nguồn tới URL phù hợp, dùng anchor có nghĩa; xác nhận đích trước khi đổi liên kết.',
    'ONPAGE':'Kiểm tra HTML gốc và mục đích trang; sửa metadata/cấu trúc phù hợp nội dung. Xác minh bằng lần crawl mới.',
}

EXPECTED = {
    'CRAWL':'URL/tài nguyên được phép truy cập theo ý định và robots trong phạm vi đã chọn.',
    'INDEX':'Directives và nội dung phù hợp ý định index; cần Google-reported evidence để kết luận Google index.',
    'CAN':'Canonical thống nhất tới URL đại diện phù hợp, không mâu thuẫn status/noindex.',
    'SITEMAP':'Sitemap parse được và khai báo URL/lastmod phù hợp ý định index, không mặc định mọi URL cần nằm trong sitemap.',
    'HTTP':'Liên kết/redirect đi tới đích phù hợp, không lỗi hoặc loop; 302 có thể là chủ ý.',
    'ARCH':'Trang quan trọng có đường HTML được quan sát; độ sâu/orphan là tín hiệu cần xem xét, không phải ranking rule.',
    'LINK':'Href/anchor dẫn tới URL phù hợp và có thể kiểm tra; external targets không được tự crawl.',
    'ONPAGE':'Metadata và cấu trúc HTML hỗ trợ nội dung trang; nhiều H1/ít chữ không tự chứng minh chất lượng kém.',
}

DEFAULT_SEVERITY={
    'CRAWL-001':'high','CRAWL-002':'high','CRAWL-004':'high','INDEX-002':'high','INDEX-007':'low',
    'CAN-002':'informational','CAN-003':'high','CAN-004':'high','CAN-005':'low','CAN-006':'high','CAN-009':'low','CAN-010':'low',
    'SITEMAP-001':'informational','SITEMAP-006':'high','SITEMAP-008':'informational','SITEMAP-009':'low',
    'HTTP-002':'low','HTTP-003':'high','HTTP-004':'high','HTTP-005':'low','HTTP-009':'high','ARCH-003':'low',
    'LINK-004':'high','LINK-005':'low','LINK-010':'low',
    'ONPAGE-002':'low','ONPAGE-003':'low','ONPAGE-004':'low','ONPAGE-008':'low','ONPAGE-009':'low','ONPAGE-010':'low',
}


def catalog():
    result=[]
    for definition in json.loads(Path(__file__).with_name('catalog.json').read_text()):
        row=dict(definition); category=row['category']; number=int(row['id'].rsplit('-',1)[1]); key=row['id'][5:]
        capability='automated' if number in IMPLEMENTED.get(category,[]) else 'not_implemented'
        if key in ('CRAWL-008','SERVER-003','SERVER-007','SERVER-009','SEC-008','SEC-009','MONITOR-010'):capability='manual_review'
        if key in ('INDEX-003','INDEX-004','INDEX-005','CAN-007','CAN-011','SITEMAP-010','CRAWL-006','ONPAGE-006','ONPAGE-007','MONITOR-007') or category=='CWV':
            capability='integration_required'
        row.update(name=TITLES.get(key,row['name']),capability=capability,version=VERSION,
                   priority_group='P0' if category in ('CRAWL','INDEX','CAN','HTTP','SEC') else 'P2' if category in ('SCHEMA','LOCAL') else 'P1',
                   required_sources=['gsc_page_performance'] if key=='MONITOR-006' else ['crawl_snapshot'] if capability=='automated' else ['optional_integration_or_manual_review'],
                   description=EXPECTED.get(category,'Workflow hoặc nguồn tích hợp riêng; không giả dữ liệu khi chưa có.'),
                   default_severity=DEFAULT_SEVERITY.get(key,'medium' if key in TITLES else 'informational'),confidence_rules='HTTP/HTML = observed; graph = derived; content/depth = suspected; no Google index assertion.',
                   recommendation=RECOMMENDATIONS.get(category,'Cần nguồn dữ liệu hoặc xác minh thủ công; chưa tự động hóa trong Core.'))
        result.append(row)
    return result


def rule_id(key):return 'TECH-'+key


def prioritize(severity,confidence,data):
    value={'critical':100,'high':80,'medium':50,'low':20,'informational':5}[severity]
    reasons=[f'Mức độ: {severity} ({value})']
    importance=data.get('intent',{}).get('importance','supporting')
    extra={'critical_money':30,'important':20,'supporting':0,'low':-5}.get(importance,0)
    value+=extra;reasons.append(f'Phân loại URL: {importance} ({extra:+d})')
    if data.get('gsc'):
        clicks=data['gsc']['clicks'];bonus=min(20,round(math.log1p(clicks)*3))
        value+=bonus;reasons.append(f'Exposure đã lưu: {clicks} clicks / {data["gsc"]["impressions"]} impressions; +{bonus}. Không suy ra quan hệ nhân quả.')
    else:reasons.append('Không có traffic GSC phù hợp; không coi URL ít traffic là ít quan trọng.')
    extra={'confirmed':10,'strong_evidence':5,'suspected':0,'needs_manual_verification':-5,'unknown':-10}[confidence]
    return value+extra,reasons+[f'Độ tin cậy: {confidence} ({extra:+d}); thứ tự xử lý nội bộ, không phải SEO health score.']


def evaluate(urls,links,sitemaps,run):
    """Return immutable issue snapshots + per-URL evaluated check IDs."""
    issues=[];checks={u.url:set() for u in urls};by_url={u.url:u for u in urls};root=run.config['root_url']
    by_id={u.id:u for u in urls}
    html=[u for u in urls if u.state=='fetched' and u.data.get('html') and not any(u.data.get(k) for k in ('truncated','parse_error','extraction_limited','redirect_chain')) and u.status_code and 200<=u.status_code<300]
    titles=Counter(u.title for u in html if u.title)
    descriptions=Counter((u.data.get('description') or [''])[0] for u in html if u.data.get('description'))

    def checked(u,key):checks[u.url].add(rule_id(key))
    def emit(u,key,evidence,severity='medium',confidence='confirmed',evidence_type='observed'):
        if not u:return
        checked(u,key);rid=rule_id(key)
        fingerprint=hashlib.sha256((rid+'\n'+u.url).encode()).hexdigest()
        existing=next((x for x in issues if x['fingerprint']==fingerprint),None)
        if existing:
            observations=existing['evidence'].setdefault('additional_observations',[])
            if evidence!=existing['evidence'].get('actual_behavior') and evidence not in observations:
                existing['evidence']['additional_observations_count']=existing['evidence'].get('additional_observations_count',0)+1
                if len(observations)<50:observations.append(evidence)
            return
        priority,reasons=prioritize(severity,confidence,u.data)
        category=key.split('-')[0]
        evidence={**evidence,'expected_behavior':EXPECTED.get(category,''),'actual_behavior':dict(evidence),
                  'description':TITLES.get(key,key),'business_impact':f"URL importance: {u.data.get('intent',{}).get('importance','supporting')}. Có thể ảnh hưởng khả năng truy cập/diễn giải nội dung; không kết luận tác động ranking.",
                  'rule_version':VERSION,'coverage_complete':run.coverage.get('complete',False)}
        issues.append(dict(fingerprint=fingerprint,url_id=u.id,url=u.url,rule_id=rid,category=category,
                           title=TITLES.get(key,key),severity=severity,confidence=confidence,evidence_type=evidence_type,
                           evidence=evidence,recommendation=RECOMMENDATIONS.get(key.split('-')[0],'Xem lại bằng chứng và crawl lại.'),
                           verification='Chạy audit mới cùng cấu hình; kiểm tra URL và rule đã được đánh giá lại. Dùng GSC URL Inspection thủ công khi cần xác nhận Google.',
                           priority=priority,priority_reasons=reasons))

    home=by_url.get(root)
    if home:
        robots=run.coverage.get('robots',{})
        checked(home,'CRAWL-001')
        if any(v['state'] in ('unknown','denied') for v in robots.values()):emit(home,'CRAWL-001',{'robots':robots},'high','strong_evidence')
        checked(home,'SITEMAP-001')
        if not any(s.data.get('valid') for s in sitemaps):emit(home,'SITEMAP-001',{'attempted':[s.url for s in sitemaps]},'informational','suspected')
    for site in sitemaps:
        if not home:continue
        checked(home,'SITEMAP-002')
        if site.data.get('error') and site.status_code not in (404,410):emit(home,'SITEMAP-002',{'sitemap':site.url,**site.data},'medium')
        if site.status_code and 200<=site.status_code<300:
            checked(home,'SITEMAP-003')
            if not site.data.get('valid'):emit(home,'SITEMAP-003',{'sitemap':site.url,**site.data})
        if site.data.get('kind')=='sitemapindex':checked(home,'SITEMAP-004')
    for u in urls:
        d=u.data;important=d.get('intent',{}).get('importance') in ('critical_money','important') or u.url==root
        if u.state in ('fetched','robots_blocked','robots_unknown'):checked(u,'INDEX-001')
        if u.state=='fetched':
            checked(u,'HTTP-001');checked(u,'HTTP-009')
            if d.get('fetch_error') in ('dns_error','timeout','network_or_tls_error','unsafe_network','host_backoff'):
                emit(u,'HTTP-009',{'error':d['fetch_error'],'local_crawler_only':True},'high','strong_evidence')
            checked(u,'CRAWL-004')
            if important and u.status_code and u.status_code>=400:emit(u,'CRAWL-004',{'status':u.status_code},'high')
            checked(u,'HTTP-002');checked(u,'HTTP-003');checked(u,'HTTP-004')
            chain=d.get('redirect_chain',[])
            if len(chain)>1:emit(u,'HTTP-002',{'chain':chain},'low')
            if d.get('fetch_error') in ('redirect_loop','redirect_limit'):emit(u,'HTTP-003',{'chain':chain,'error':d['fetch_error']},'high')
            if chain and (d.get('fetch_error') or (d.get('final_status') and d['final_status']>=400)):
                emit(u,'HTTP-004',{'chain':chain,'final_status':d.get('final_status'),'error':d.get('fetch_error')},'high')
        checked(u,'CRAWL-002')
        if important and u.state=='robots_blocked':emit(u,'CRAWL-002',{'crawler_allowed':False,'googlebot_simulation':d.get('googlebot_allowed')},'high','confirmed')
        if d.get('html'):
            checked(u,'ONPAGE-010')
            if d.get('truncated') or d.get('parse_error') or d.get('extraction_limited'):emit(u,'ONPAGE-010',{'truncated':d.get('truncated',False),'parse_error':d.get('parse_error',False),'extraction_limited':d.get('extraction_limited',False)},'low','strong_evidence')
        if u in html:
            for key in ('CAN-001','CAN-002','CAN-003','ONPAGE-001','ONPAGE-002','ONPAGE-003','ONPAGE-004','ONPAGE-005','ONPAGE-008','ONPAGE-009','LINK-010','INDEX-002','INDEX-006','INDEX-007','CRAWL-003'):
                checked(u,key)
            can=list(dict.fromkeys(d.get('canonical',[])))
            if not can:emit(u,'CAN-002',{'canonical':[]},'informational','suspected')
            if len(can)>1 or d.get('canonical_invalid') or any(not v.startswith(('https://','http://')) for v in can):emit(u,'CAN-003',{'canonical':can},'high')
            targets=[by_url.get(target) for target in can]
            known_http=bool(targets) and all(t and t.state=='fetched' and t.status_code is not None and not t.data.get('fetch_error') for t in targets)
            if known_http:
                checked(u,'CAN-004');checked(u,'CAN-005')
                if all(t.data.get('html') and not t.data.get('truncated') and 200<=t.status_code<300 for t in targets):checked(u,'CAN-006')
            for target in can:
                other=by_url.get(target)
                if not other or other.state!='fetched':continue
                if other.status_code and other.status_code>=400:emit(u,'CAN-004',{'canonical':target,'status':other.status_code},'high','strong_evidence','derived')
                if other.data.get('redirect_chain'):emit(u,'CAN-005',{'canonical':target,'chain':other.data['redirect_chain']},'low','confirmed','derived')
                if noindex(other.data):emit(u,'CAN-006',{'canonical':target,'directives':other.data.get('meta_robots'), 'x_robots_tag':other.data.get('x_robots_tag')},'high','strong_evidence','derived')
            expected=d.get('intent',{}).get('should_index','yes' if u.url==root or 'sitemap' in u.sources else 'undecided')
            if noindex(d) and expected=='yes':emit(u,'INDEX-002',{'meta':d.get('meta_robots'), 'x_robots_tag':d.get('x_robots_tag'),'expected_index':'yes'},'critical' if u.url==root else 'high')
            if d.get('soft_404_candidate'):emit(u,'INDEX-006',{'status':u.status_code,'text_pattern':'not-found text in short HTML','word_count':d.get('word_count')},'medium','suspected','heuristic')
            if d.get('word_count',0)<100:emit(u,'INDEX-007',{'word_count':d.get('word_count'),'threshold':100,'not_a_quality_verdict':True},'low','suspected','heuristic')
            if not u.title or titles[u.title]>1 or d.get('title_count',0)>1:emit(u,'ONPAGE-001',{'title':u.title,'declarations':d.get('title_count'),'duplicate_urls':titles[u.title],'duplicate_examples':[x.url for x in html if x.title==u.title][:50]},'medium' if not u.title else 'low')
            desc=d.get('description',[])
            if not desc or not desc[0] or descriptions[desc[0]]>1:emit(u,'ONPAGE-002',{'description':desc,'duplicate_urls':descriptions[desc[0]] if desc else 0,'duplicate_examples':[x.url for x in html if desc and (x.data.get('description') or [''])[0]==desc[0]][:50]},'low')
            headings=d.get('headings',[]);h1=[h['text'] for h in headings if h['level']==1]
            if len(h1)!=1:emit(u,'ONPAGE-003',{'h1':h1},'low','strong_evidence')
            if any(b['level']>a['level']+1 for a,b in zip(headings,headings[1:])):emit(u,'ONPAGE-004',{'headings':headings[:20]},'low','suspected','heuristic')
            if not d.get('language'):emit(u,'ONPAGE-008',{'lang':''},'low')
            if d.get('encoding_errors'):emit(u,'ONPAGE-009',{'replacement_characters':d['encoding_errors']},'low','suspected')
            if d.get('hrefless_links'):emit(u,'LINK-010',{'links_without_href':d['hrefless_links']},'low','suspected')
            if d.get('blocked_resources'):emit(u,'CRAWL-003',{'resources':d['blocked_resources'],'evaluation':'robots simulation; resources not downloaded'},'medium','suspected','derived')
            for key in ('LINK-001','LINK-002','LINK-003','LINK-006','LINK-007','LINK-008','ARCH-001','ARCH-002','ARCH-003','ARCH-008','INDEX-009','INDEX-010'):checked(u,key)
            if important and u.depth is not None and u.depth>4:emit(u,'ARCH-002',{'minimum_observed_html_depth':u.depth},'medium','suspected','derived')
            if u.url!=root and u.inbound==0 and set(u.sources)&{'sitemap','important','import','gsc'}:
                emit(u,'ARCH-003',{'inbound_observed':0,'sources':u.sources,'crawl_complete':run.coverage.get('complete',False)},'medium' if important else 'low','suspected','derived')
            if run.coverage.get('sitemap_valid'):
                checked(u,'SITEMAP-008')
                if ('sitemap' in u.sources) != (u.inbound>0 or u.url==root):
                    emit(u,'SITEMAP-008',{'sources':u.sources,'observed_inbound':u.inbound,'candidate_only':True},'informational','suspected','derived')
        if 'sitemap' in u.sources:
            if u.state=='fetched':
                for key in ('SITEMAP-005','SITEMAP-006','SITEMAP-007'):checked(u,key)
                if d.get('redirect_chain') or (u.status_code and u.status_code>=400):emit(u,'SITEMAP-005',{'status':u.status_code,'chain':d.get('redirect_chain')},'medium','confirmed','derived')
                if noindex(d):emit(u,'SITEMAP-006',{'meta':d.get('meta_robots'),'x_robots_tag':d.get('x_robots_tag')},'high','strong_evidence','derived')
                if u.indexability=='canonicalized':emit(u,'SITEMAP-007',{'canonical':d.get('canonical')},'medium','strong_evidence','derived')
            checked(u,'SITEMAP-009')
            values=d.get('sitemap_lastmod',[]);states=[lastmod_state(v) for v in values]
            if any(v!='valid' for v in states):emit(u,'SITEMAP-009',{'lastmod':values,'states':states,'not_verified_against_content':True},'low','suspected')
    per_source={}
    for link in links:
        if link.internal:per_source.setdefault(link.source_id,[]).append(by_url.get(link.target_url))
    for source_id,targets in per_source.items():
        if all(t and t.state=='fetched' and t.status_code is not None and not t.data.get('fetch_error') for t in targets):
            for key in ('LINK-004','LINK-005','HTTP-005'):checked(by_id[source_id],key)
    for link in links:
        source=by_id.get(link.source_id);target=by_url.get(link.target_url)
        if not source or not link.internal or not target or target.state!='fetched':continue
        if target.status_code and target.status_code>=400:
            emit(source,'LINK-004',{'target':target.url,'status':target.status_code,'anchor':link.anchor},'high','confirmed','derived')
        if target.data.get('redirect_chain'):
            evidence={'target':target.url,'chain':target.data['redirect_chain'],'anchor':link.anchor}
            emit(source,'LINK-005',evidence,'low','confirmed','derived')
            # Same observation belongs to LINK-005; avoid creating duplicate remediation tasks under HTTP-005.
    families={}
    for u in html:
        parsed=urlsplit(u.url);key=(parsed.netloc,parsed.path.rstrip('/'))
        families.setdefault(key,[]).append(u)
    for family in families.values():
        for u in family:
            if len(family)>1:
                checked(u,'CAN-009');checked(u,'CAN-010');checked(u,'CRAWL-007')
                siblings=[other.url for other in family if other.id!=u.id and other.data.get('content_fingerprint')==u.data.get('content_fingerprint')]
                if siblings:
                    key='CAN-010' if urlsplit(u.url).query else 'CAN-009'
                    emit(u,key,{'same_text_fingerprint':siblings[:10],'canonical':u.data.get('canonical'),'candidate_only':True},'low','suspected','heuristic')
                if len(family)>=10:emit(u,'CRAWL-007',{'observed_variants':len(family),'examples':[v.url for v in family[:10]]},'medium','suspected','heuristic')
    return issues,{key:sorted(value) for key,value in checks.items()}


def absence_verified(issue,urls,checks):
    if issue.rule_id not in checks.get(issue.url,[]):return False
    if issue.rule_id in ('TECH-ONPAGE-001','TECH-ONPAGE-002') and issue.evidence.get('duplicate_urls',0)>1:
        examples=issue.evidence.get('duplicate_examples',[])
        if len(examples)<issue.evidence['duplicate_urls']:return False
        if any(url not in urls or urls[url].state!='fetched' or not urls[url].data.get('html') or urls[url].data.get('truncated') for url in examples):return False
    return True
