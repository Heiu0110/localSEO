import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from app.technical.urls import CrawlError, normalize


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=[];self.titles=[];self.headings=[];self.links=[];self.resources=[];self.canonicals=[];self.meta_robots=[]
        self.description=[];self.language='';self.charset='';self.text=[];self.active_title=False;self.heading=None
        self.skip=0;self.anchor=None;self.breadcrumb=0;self.nav_stack=[];self.base=None;self.hrefless=0;self.viewport=''
        self.jsonld=[];self.script_text=None
        self.main_depth=0;self.main_text=[];self.limited=False

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('main','article'):self.main_depth+=1
        if tag=='html': self.language=a.get('lang') or ''
        if tag=='base' and not self.base: self.base=a.get('href')
        if tag=='title': self.active_title=True;self.title=[]
        if re.fullmatch('h[1-6]',tag): self.heading={'level':int(tag[1]),'text':''}
        if tag in ('script','style','template'): self.skip+=1
        if tag=='script' and a.get('type','').lower()=='application/ld+json': self.script_text=[]
        if tag=='meta':
            name=a.get('name','').lower();content=a.get('content') or ''
            if name=='description': self.description.append(content[:3000])
            if name in ('robots','googlebot'): self.meta_robots.append({'agent':name,'content':content[:3000]})
            if name=='viewport': self.viewport=content[:1000]
            if a.get('charset'): self.charset=a['charset'][:100]
        rel=(a.get('rel') or '').lower().split()
        if tag=='link' and 'canonical' in rel and a.get('href'): self.canonicals.append(a['href'])
        if tag=='link' and 'stylesheet' in rel and a.get('href'): self.resources.append(a['href'])
        if tag=='script' and a.get('src'): self.resources.append(a['src'])
        if tag=='nav':
            is_breadcrumb=any('breadcrumb' in (a.get(k) or '').lower() for k in ('aria-label','class','id'))
            self.nav_stack.append(is_breadcrumb);self.breadcrumb+=int(is_breadcrumb)
        if tag=='a':
            href=a.get('href') or ''
            if not href or href.lower().startswith(('javascript:','#')): self.hrefless+=1
            self.anchor={'href':href,'anchor':'','rel':' '.join(rel),'context':'breadcrumb' if self.breadcrumb else 'html'}

    def handle_endtag(self,tag):
        if tag=='title' and self.active_title: self.titles.append(' '.join(self.title).strip());self.active_title=False
        if tag in ('script','style','template'):
            self.skip=max(0,self.skip-1)
            if tag=='script' and self.script_text is not None:
                if len(self.jsonld)<10: self.jsonld.append(''.join(self.script_text)[:100_000])
                self.script_text=None
        if self.heading and tag==f"h{self.heading['level']}":
            self.heading['text']=self.heading['text'].strip()[:2000]
            if len(self.headings)<200: self.headings.append(self.heading)
            else:self.limited=True
            self.heading=None
        if tag=='a' and self.anchor:
            if len(self.links)<3000:self.links.append(self.anchor)
            else:self.limited=True
            self.anchor=None
        if tag=='nav' and self.nav_stack: self.breadcrumb-=int(self.nav_stack.pop())
        if tag in ('main','article'):self.main_depth=max(0,self.main_depth-1)

    def handle_data(self,text):
        if self.script_text is not None and sum(map(len,self.script_text))<100_000:self.script_text.append(text)
        if self.skip: return
        text=' '.join(text.split())
        if self.active_title: self.title.append(text)
        if self.heading:self.heading['text']+=text+' '
        if self.anchor:self.anchor['anchor']=(self.anchor['anchor']+text+' ')[:500]
        if text:
            self.text.append(text)
            if self.main_depth:self.main_text.append(text)


def extract(body,headers,url):
    charset_match=re.search(r'charset=["\s]*([^\s;"\']+)',headers.get('content-type',''),re.I)
    encoding=charset_match[1] if charset_match else 'utf-8'
    try: text=body.decode(encoding,errors='replace')
    except LookupError: text=body.decode('utf-8',errors='replace')
    parser=Extractor()
    try: parser.feed(text);parser.close()
    except (ValueError,AssertionError): return {'html':True,'parse_error':True,'links':[],'canonical':[]}
    base=urljoin(url,parser.base) if parser.base else url
    canonical=parser.canonicals+re.findall(r'<([^>]+)>\s*;\s*rel\s*=\s*["\']?canonical["\']?',headers.get('link',''),re.I)
    normalized=[];canonical_invalid=False
    for value in canonical[:10]:
        try: normalized.append(normalize(value.strip(),base))
        except CrawlError:
            normalized.append(value[:2048]);canonical_invalid=True
    visible=' '.join(parser.main_text or parser.text)
    return {'html':True,'title':parser.titles[0][:3000] if parser.titles else '', 'title_count':len(parser.titles),
            'description':parser.description,'headings':parser.headings,'canonical':normalized,'canonical_invalid':canonical_invalid,'meta_robots':parser.meta_robots,
            'x_robots_tag':headers.get('x-robots-tag',''),'x_robots_tags':headers.get('x-robots-tag-values',[]),'language':parser.language,'charset':parser.charset,
            'encoding_errors':text.count('\ufffd'),'word_count':len(re.findall(r'\w+',visible)),
            'word_count_scope':'main_or_article' if parser.main_text else 'visible_raw_document','extraction_limited':parser.limited or len(parser.resources)>200 or any(len(t)>3000 for t in parser.titles),
            'content_fingerprint':hashlib.sha256(visible.encode()).hexdigest(),'links':parser.links,'resources':parser.resources[:200],
            'base':base,'hrefless_links':parser.hrefless,'viewport':parser.viewport,'jsonld_count':len(parser.jsonld),
            'breadcrumbs':[a for a in parser.links if a['context']=='breadcrumb'][:100],
            'soft_404_candidate':bool(re.search(r'(page not found|không tìm thấy trang|404 not found)',visible[:3000],re.I)) and len(visible)<3000}


def noindex(data):
    values=[row['content'] for row in data.get('meta_robots',[])]
    # An X-Robots-Tag scoped to an unrelated bot must not affect Google assessment.
    for header in data.get('x_robots_tags') or [data.get('x_robots_tag','')]:
        agent=None
        for raw in header.split(','):
            if ':' in raw:
                prefix,remainder=raw.split(':',1)
                if prefix.strip().lower() not in ('max-snippet','max-video-preview','max-image-preview','unavailable_after'):
                    agent,raw=prefix.strip().lower(),remainder
            if agent in (None,'googlebot','robots','*'):values.append(raw)
    tokens={t for value in values for t in re.split(r'[\s,;]+',value.lower())}
    return 'noindex' in tokens or 'none' in tokens


def indexability(status,state,data,url):
    if state=='robots_blocked':return 'robots_blocked'
    if data.get('redirect_chain'):return 'redirected'
    if not status or data.get('fetch_error'):return 'error' if state=='fetched' else 'unknown'
    if status>=400:return 'error'
    if 300<=status<400:return 'redirected'
    if not 200<=status<300 or not data.get('html') or data.get('truncated') or data.get('parse_error'):return 'unknown'
    if noindex(data):return 'noindex'
    if data.get('canonical_invalid'):return 'unknown'
    canonical=list(dict.fromkeys(data.get('canonical',[])))
    if len(canonical)>1:return 'unknown'
    if canonical and canonical[0]!=url:return 'canonicalized'
    return 'indexable_candidate'
