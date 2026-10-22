import gzip
import io
from datetime import date, datetime, timezone

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.technical.urls import CrawlError

MAX_XML = 4 * 1024 * 1024


def parse_sitemap(body):
    if len(body)>MAX_XML:raise CrawlError('sitemap_too_large','Sitemap vượt giới hạn 4 MiB.')
    if body[:2]==b'\x1f\x8b':
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as archive:body=archive.read(MAX_XML+1)
        except (OSError,EOFError):raise CrawlError('invalid_xml','Sitemap gzip không hợp lệ.') from None
    if len(body)>MAX_XML:raise CrawlError('sitemap_too_large','Sitemap giải nén vượt giới hạn 4 MiB.')
    try:root=ElementTree.fromstring(body,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except (ElementTree.ParseError,DefusedXmlException):raise CrawlError('invalid_xml','XML không hợp lệ hoặc chứa DTD/entity bị cấm.') from None
    tag=lambda node:node.tag.rsplit('}',1)[-1]
    kind=tag(root)
    if kind not in ('urlset','sitemapindex'):raise CrawlError('invalid_xml','Không phải urlset hoặc sitemapindex.')
    rows=[]
    for child in root:
        if tag(child) not in ('url','sitemap'):continue
        values={tag(item):(item.text or '').strip() for item in child}
        if values.get('loc'):rows.append({'url':values['loc'],'lastmod':values.get('lastmod','')})
        if len(rows)>10000:raise CrawlError('sitemap_too_many_urls','Sitemap vượt 10.000 URL trong bản Core.')
    return kind,rows


def lastmod_state(value):
    if not value:return 'missing'
    try:
        if len(value)==10: day=date.fromisoformat(value)
        else:day=datetime.fromisoformat(value.replace('Z','+00:00')).date()
        return 'future' if day>datetime.now(timezone.utc).date() else 'valid'
    except (ValueError,TypeError):return 'invalid'
