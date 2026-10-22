"""Read reports use SQL paging; comparison requires evidence, not mere absence."""
from collections import Counter

from sqlalchemy import func, or_, select

from app.gsc.errors import GSCError
from app.technical.jobs import public, require
from app.technical.models import AuditIssue, AuditLink, AuditProject, AuditRun, AuditSitemap, AuditTask, AuditURL
from app.technical.rules import absence_verified, catalog


def like(value):return '%'+value.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


def paginate(session,query,model,page,page_size,order):
    total=session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows=list(session.scalars(query.order_by(*order).offset((page-1)*page_size).limit(page_size)))
    return {'rows':[public(row) for row in rows],'total':total,'page':page,'page_size':page_size}


def list_urls(db,key,page=1,page_size=25,search='',state='',sort='url',direction='asc'):
    sorts={'url':AuditURL.url,'status':AuditURL.status_code,'depth':AuditURL.depth,'inbound':AuditURL.inbound,'outbound':AuditURL.outbound,'title':AuditURL.title,'duration':AuditURL.duration_ms}
    with db.session() as session:
        run=require(session,AuditRun,key)
        query=select(AuditURL).where(AuditURL.audit_id==key)
        if search:query=query.where(or_(AuditURL.url.ilike(like(search),escape='\\'),AuditURL.title.ilike(like(search),escape='\\')))
        if state:query=query.where(AuditURL.indexability==state)
        order=sorts[sort].desc() if direction=='desc' else sorts[sort].asc()
        result=paginate(session,query,AuditURL,page,page_size,[order.nulls_last(),AuditURL.id])
        for row in result['rows']:
            d=row.pop('data');row.update(word_count=d.get('word_count'),intent=d.get('intent'),gsc=d.get('gsc'),fetch_error=d.get('fetch_error'))
            if 'checks' not in run.summary:row.update(inbound=None,outbound=None,depth=None)
        return result


def list_issues(db,key,page=1,page_size=25,search='',severity='',category='',rule='',sort='priority',direction='desc'):
    sorts={'priority':AuditIssue.priority,'severity':AuditIssue.priority,'url':AuditIssue.url,'rule':AuditIssue.rule_id,'title':AuditIssue.title}
    with db.session() as session:
        require(session,AuditRun,key)
        query=select(AuditIssue).where(AuditIssue.audit_id==key)
        if search:query=query.where(or_(AuditIssue.url.ilike(like(search),escape='\\'),AuditIssue.title.ilike(like(search),escape='\\')))
        if severity:query=query.where(AuditIssue.severity==severity)
        if category:query=query.where(AuditIssue.category==category)
        if rule:query=query.where(AuditIssue.rule_id==rule)
        counts=dict(session.execute(select(AuditIssue.rule_id,func.count()).where(AuditIssue.audit_id==key).group_by(AuditIssue.rule_id)).all())
        order=sorts[sort].desc() if direction=='desc' else sorts[sort].asc()
        result=paginate(session,query,AuditIssue,page,page_size,[order,AuditIssue.id])
        for row in result['rows']:
            row['affected_url_count']=counts[row['rule_id']]
            task=session.scalar(select(AuditTask).where(AuditTask.project_id==row['project_id'],AuditTask.fingerprint==row['fingerprint']))
            row['status']=task.status if task else 'open'
        return result


def rules_for_run(run):
    counts=run.summary.get('checks',{})
    result=[]
    for row in catalog():
        number=counts.get(row['id'],0)
        state='not_implemented' if row['capability']=='not_implemented' else 'not_available' if row['capability']=='integration_required' else 'needs_review' if row['capability']=='manual_review' else 'not_checked'
        if row['capability']=='automated' and number and run.coverage.get('complete') and run.status=='completed':state='passed'
        result.append({**row,'state':state,'evaluated_urls':number})
    return result


def overview(db,key):
    with db.session() as session:
        run=require(session,AuditRun,key)
        result=public(run);result['project']=public(require(session,AuditProject,run.project_id))
        result['top_issues']=[public(i) for i in session.scalars(select(AuditIssue).where(AuditIssue.audit_id==key).order_by(AuditIssue.priority.desc()).limit(10))]
        result['rules']=rules_for_run(run)
        found={row[0] for row in session.execute(select(AuditIssue.rule_id).where(AuditIssue.audit_id==key).distinct())}
        if 'TECH-LINK-005' in found:found.add('TECH-HTTP-005')  # Shared evidence, one remediation task.
        for row in result['rules']:
            if row['id'] in found:row['state']='issue_found'
        return result


def url_detail(db,key,url_id):
    with db.session() as session:
        item=require(session,AuditURL,url_id)
        if item.audit_id!=key:raise GSCError('technical_not_found','URL không thuộc audit này.',404)
        result=public(item)
        if 'checks' not in require(session,AuditRun,key).summary:result.update(inbound=None,outbound=None,depth=None)
        incoming=select(AuditLink).where(AuditLink.audit_id==key,AuditLink.target_url==item.url)
        outgoing=select(AuditLink).where(AuditLink.source_id==item.id)
        result['incoming']=[public(row) for row in session.scalars(incoming.limit(100))]
        result['outgoing']=[public(row) for row in session.scalars(outgoing.limit(100))]
        result['issues']=[public(row) for row in session.scalars(select(AuditIssue).where(AuditIssue.audit_id==key,AuditIssue.url_id==url_id))]
        result['google_index_status']=None;result['google_selected_canonical']=None
        result['limitations']=['Local indexability không phải trạng thái index của Google.','Liên kết trong panel giới hạn 100 dòng mỗi chiều; xem tab Liên kết nội bộ để phân trang.']
        target=(item.data.get('canonical') or [None])[0]
        other=session.scalar(select(AuditURL).where(AuditURL.audit_id==key,AuditURL.url==target)) if target else None
        result['canonical_target_status']=other.status_code if other else None
        return result


def comparison(db,before_id,after_id):
    with db.session() as session:
        before,after=require(session,AuditRun,before_id),require(session,AuditRun,after_id)
        if before.id==after.id or before.project_id!=after.project_id or before.started_at>=after.started_at:
            raise GSCError('invalid_comparison','Chọn hai audit cùng dự án, audit trước phải cũ hơn audit sau.',422)
        comparable=all(r.status=='completed' and r.coverage.get('complete') for r in (before,after)) and before.scope_hash==after.scope_hash and before.rule_version==after.rule_version
        older={r.fingerprint:r for r in session.scalars(select(AuditIssue).where(AuditIssue.audit_id==before_id))}
        newer={r.fingerprint:r for r in session.scalars(select(AuditIssue).where(AuditIssue.audit_id==after_id))}
        current_urls={u.url:u for u in session.scalars(select(AuditURL).where(AuditURL.audit_id==after_id))}
        prior_fingerprints=set(session.scalars(select(AuditIssue.fingerprint).join(AuditRun,AuditRun.id==AuditIssue.audit_id).where(
            AuditRun.project_id==after.project_id,AuditRun.started_at<before.started_at)))
        rows=[]
        for fingerprint,row in newer.items():
            status='persistent' if fingerprint in older else 'reopened' if fingerprint in prior_fingerprints else 'new' if comparable else 'newly_observed'
            rows.append({'state':status,**public(row)})
        for fingerprint,row in older.items():
            if fingerprint in newer:continue
            checked=absence_verified(row,current_urls,{u.url:u.data.get('checked_rules',[]) for u in current_urls.values()})
            rows.append({'state':'resolved' if comparable and checked else 'not_observed','id':row.id,'rule_id':row.rule_id,'url':row.url,'title':row.title,'severity':row.severity})
        changes=[]
        for old in session.scalars(select(AuditURL).where(AuditURL.audit_id==before_id)):
            new=current_urls.get(old.url)
            if not new or old.state!='fetched' or new.state!='fetched':continue
            delta={key:{'before':getattr(old,key),'after':getattr(new,key)} for key in ('title','status_code','indexability') if getattr(old,key)!=getattr(new,key)}
            for key in ('canonical','meta_robots','x_robots_tag','content_fingerprint'):
                if old.data.get(key)!=new.data.get(key):delta[key]={'before':old.data.get(key),'after':new.data.get(key)}
            if delta:changes.append({'url':old.url,'changes':delta})
        return {'before':before_id,'after':after_id,'comparable':bool(comparable),'warning':None if comparable else 'Audit không cùng scope/version hoặc chưa hoàn tất coverage. Vắng lỗi không có nghĩa đã sửa.',
                'counts':dict(Counter(row['state'] for row in rows)),'rows':rows[:500],'total':len(rows),'url_changes':changes[:200],'url_changes_total':len(changes)}
