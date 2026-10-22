"""Explicit, offline test site. NEVER used as fallback for a real website."""
import httpx

ROOT = 'https://audit.fixture.example/'


def fixture_transport():
    def page(title,body,meta='',canonical=''):
        return f'<!doctype html><html lang="vi"><head><title>{title}</title>{meta}<link rel="canonical" href="{canonical or ROOT}"></head><body>{body}</body></html>'

    def respond(request):
        path=request.url.path
        headers={'content-type':'text/html; charset=utf-8'}
        status=200
        if path=='/robots.txt':
            return httpx.Response(200,headers={'content-type':'text/plain'},text='User-agent: *\nDisallow: /private\nSitemap: '+ROOT+'sitemap.xml\n')
        if path=='/sitemap.xml':
            return httpx.Response(200,headers={'content-type':'application/xml'},text='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{ROOT}{p}</loc><lastmod>2099-01-01</lastmod></url>' for p in ('','orphan','noindex','private','old','missing'))+'</urlset>')
        if path=='/sitemap_index.xml':return httpx.Response(404)
        if path=='/':
            body=page('Website thử nghiệm Technical SEO','<h1>Website fixture ngoại tuyến</h1><nav aria-label="breadcrumb"><a href="/">Trang chủ</a></nav>'+''.join(f'<a href="/{p}">{p}</a>' for p in ('about','noindex','old','missing','private','conflict','checkout'))+'<a onclick="void(0)">Thiếu href</a>')
        elif path=='/about':body=page('Website thử nghiệm Technical SEO','<h1>Về chúng tôi</h1><h3>Cấp heading nhảy</h3><a href="/missing">Liên kết hỏng</a>',canonical=ROOT+'about')
        elif path=='/noindex':body=page('Nội dung không index','<h1>Noindex fixture</h1>',meta='<meta name="robots" content="noindex">',canonical=ROOT+'noindex')
        elif path=='/conflict':body=page('Canonical xung đột','<h1>Xung đột</h1>',meta='<link rel="canonical" href="/missing">',canonical=ROOT+'noindex')
        elif path=='/orphan':body=page('Trang chỉ trong sitemap','<h1>Ứng viên orphan</h1>',canonical=ROOT+'orphan')
        elif path=='/old':return httpx.Response(301,headers={'location':'/about'})
        elif path=='/missing':status=404;body=page('Không tìm thấy','<h1>404 not found</h1>')
        else:status=404;body=page('Không tìm thấy','<h1>404 not found</h1>')
        return httpx.Response(status,headers=headers,text=body)
    return httpx.MockTransport(respond)
