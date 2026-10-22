"""URL identity, explicit host scope and action-URL exclusions. No DNS in normalization."""
import fnmatch
import ipaddress
import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit


class CrawlError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def normalize(value: str, base: str | None = None, query_policy="preserve") -> str:
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\x00-\x20\x7f\\]", value):
        raise CrawlError("invalid_url", "URL không hợp lệ hoặc quá dài.")
    try:
        url = urlsplit(urljoin(base, value) if base else value)
        if url.scheme.lower() not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError()
        host = url.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if url.port not in (None, 80 if url.scheme.lower() == "http" else 443):
            raise ValueError()
        if any(not part or len(part)>63 for part in host.split('.')) or not re.fullmatch(r"[a-z0-9.-]+", host):
            raise ValueError()
        path = quote(url.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if re.search(r"%(?![0-9a-fA-F]{2})", path):
            raise ValueError()
        path = re.sub(r"%([0-9a-fA-F]{2})", lambda m: chr(int(m[1],16)) if chr(int(m[1],16)) in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~" else "%"+m[1].upper(), path)
        # Normalize dot segments while retaining the meaningful trailing slash.
        segments = []
        for segment in path.split('/'):
            if segment == '..':
                if segments: segments.pop()
            elif segment != '.': segments.append(segment)
        path = '/'.join(segments) or '/'
        if path[0] != '/': path = '/' + path
        if url.path.endswith(('/.','/..')) and not path.endswith('/'): path += '/'
        query = url.query
        if query_policy == "drop_all": query = ""
        elif query_policy == "drop_tracking":
            query = urlencode([(k,v) for k,v in parse_qsl(query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('gclid','fbclid')])
        return urlunsplit((url.scheme.lower(), host, path, query, ""))
    except (ValueError, UnicodeError):
        raise CrawlError("invalid_url", "Chỉ hỗ trợ URL HTTP/HTTPS công khai, không credentials hoặc cổng tùy ý.") from None


def public_ip(value):
    try:
        ip = ipaddress.ip_address(value.split('%')[0])
        if getattr(ip, 'ipv4_mapped', None): ip = ip.ipv4_mapped
        if ip.version==6 and (ip.sixtofour or ip.teredo or ip in ipaddress.ip_network('64:ff9b::/96') or ip in ipaddress.ip_network('64:ff9b:1::/48')):
            return False
        return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False


def safe_host(host):
    if host in ('localhost','metadata.google.internal') or '.' not in host or host.endswith(('.localhost','.local','.internal','.home','.test','.example','.invalid')):
        return False
    try:
        ipaddress.ip_address(host)
        return public_ip(host)
    except ValueError:
        return not re.fullmatch(r"[0-9.]+",host)


def action_url(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path).lower()
    if re.search(r"(?:^|[/_.-])(logout|log-out|delete|remove|checkout|purchase|buy-now|wp-admin|wp-login|add-to-cart)(?:[/_.-]|$)", path):
        return True
    return any(k.lower() in ('action','do','delete','remove','logout','add-to-cart','wc-ajax','checkout','purchase') for k,v in parse_qsl(parsed.query))


class Scope:
    def __init__(self, root, config, fixture=False):
        if action_url(normalize(root)):raise CrawlError('unsafe_action_url','Không crawl URL có thể kích hoạt hành động.')
        self.root = normalize(root,query_policy=config.get('query_policy','preserve'))
        self.hosts = {urlsplit(self.root).hostname}
        for host in config.get('allowed_hosts', []):
            if '://' in host or '/' in host or ':' in host:
                raise CrawlError('invalid_scope', 'Allowed hosts chỉ chứa hostname, không scheme, path hoặc port.')
            self.hosts.add(urlsplit(normalize('https://'+host+'/')).hostname)
        self.fixture = fixture
        if not fixture and not all(safe_host(h) for h in self.hosts):
            raise CrawlError('unsafe_host', 'Không crawl localhost, địa chỉ mạng riêng hoặc tên miền dành riêng.')
        if fixture and self.hosts != {'audit.fixture.example'}:
            raise CrawlError('invalid_fixture', 'Bộ thử nghiệm chỉ dùng audit.fixture.example và không gửi request mạng.')
        self.config = config
        agent = config.get('user_agent', '')
        if not agent.startswith('LocalSEOWorkspace/') or 'googlebot' in agent.lower() or re.search(r"[\r\n\x00]",agent):
            raise CrawlError('invalid_user_agent', 'User-Agent phải nhận diện LocalSEOWorkspace, không giả Googlebot.')
        if any(len(p)>200 for p in config.get('include_patterns',[])+config.get('exclude_patterns',[])):
            raise CrawlError('invalid_pattern','Pattern quá dài; dùng glob như /blog/*, không dùng regex.')
        self.check(self.root)

    def allowed(self, url, patterns=True):
        try: normalized = normalize(url)
        except CrawlError: return False
        if urlsplit(normalized).hostname not in self.hosts or action_url(normalized): return False
        if not patterns: return True
        path = urlsplit(normalized).path
        include, exclude = self.config.get('include_patterns',[]), self.config.get('exclude_patterns',[])
        return (not include or normalized == self.root or any(fnmatch.fnmatchcase(path,p) for p in include)) and not any(fnmatch.fnmatchcase(path,p) for p in exclude)

    def check(self, url, patterns=False):
        value = normalize(url)
        if not self.allowed(value,patterns):
            raise CrawlError('out_of_scope','URL hoặc đích redirect nằm ngoài host được cho phép, hoặc là URL hành động.')
        return value
