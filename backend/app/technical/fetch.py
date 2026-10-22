"""DNS is validated AND pinned at the socket connection; original TLS SNI is preserved."""
import socket
import ssl
import time
import gzip
import io
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpcore
import httpx
from httpcore._backends.sync import SyncBackend

from app.technical.urls import CrawlError, normalize, public_ip

MAX_BODY = 2 * 1024 * 1024


class SafeNetworkBackend(SyncBackend):
    def __init__(self, hosts, resolver=socket.getaddrinfo):
        self.hosts, self.resolver = hosts, resolver

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        host = host.decode() if isinstance(host, bytes) else host
        if host not in self.hosts or port not in (80,443):
            raise CrawlError('unsafe_network','Kết nối mạng ngoài scope đã bị chặn.')
        try: addresses = list(dict.fromkeys(row[4][0] for row in self.resolver(host,port,type=socket.SOCK_STREAM)))
        except socket.gaierror: raise CrawlError('dns_error','Không phân giải được DNS.') from None
        if not addresses or any(not public_ip(ip) for ip in addresses):
            raise CrawlError('unsafe_network','DNS trỏ tới mạng riêng hoặc địa chỉ không công khai; đã chặn kết nối.')
        # Connect to the validated numeric IP, never resolve the hostname a second time.
        return super().connect_tcp(addresses[0],port,timeout,local_address,socket_options)

    def connect_unix_socket(self, *args, **kwargs):
        raise CrawlError('unsafe_network','Unix sockets không được phép.')


class PinnedTransport(httpx.HTTPTransport):
    def __init__(self, hosts):
        super().__init__(trust_env=False)
        self._pool.close()
        self._pool = httpcore.ConnectionPool(ssl_context=ssl.create_default_context(),max_connections=2,max_keepalive_connections=0,
                                              network_backend=SafeNetworkBackend(hosts), retries=0)


@dataclass
class Fetched:
    url: str
    status: int | None = None
    headers: dict = field(default_factory=dict)
    body: bytes = b''
    chain: list = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0
    truncated: bool = False


def retry_delay(value, fallback=2):
    try:
        delay = float(value)
    except (ValueError,TypeError):
        try: delay = (parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
        except (ValueError,TypeError,OverflowError): delay = fallback
    return max(0, delay)


class Fetcher:
    def __init__(self, scope, config, transport=None, sleeper=time.sleep, clock=time.monotonic, cancelled=lambda: False, on_request=lambda:None):
        self.scope, self.config, self.sleep, self.clock = scope, config, sleeper, clock
        self.cancelled, self.on_request = cancelled, on_request
        self.client = httpx.Client(transport=transport or PinnedTransport(scope.hosts),trust_env=False,follow_redirects=False,
                                   timeout=config['timeout_seconds'],headers={'User-Agent':config['user_agent'],'Accept-Encoding':'gzip, deflate','Accept':'text/html,application/xhtml+xml,application/xml,text/plain;q=0.9'})
        self.last, self.host_delays, self.failures = {}, {}, {}

    def wait(self, seconds):
        # Check cancellation while waiting, never a long uncancellable backoff.
        remaining = seconds
        while remaining > 0:
            if self.cancelled(): raise CrawlError('cancelled','Đã yêu cầu hủy audit.')
            step = min(.25,remaining)
            self.sleep(step); remaining -= step

    def fetch(self, url, redirect_guard=None, body_limit=MAX_BODY):
        original = self.scope.check(url)
        result, seen = Fetched(original), set()
        start = self.clock()
        for hop in range(9):
            if url in seen:
                result.error = 'redirect_loop'; break
            seen.add(url)
            self.scope.check(url)
            if redirect_guard and not redirect_guard(url):
                result.error = 'redirect_robots_blocked'; break
            host = urlsplit(url).hostname
            if self.failures.get(host,0)>=3:
                result.error='host_backoff'; break
            for attempt in range(2):
                self.wait(max(0,self.last.get(host,-1e9)+max(self.config['delay_seconds'],self.host_delays.get(host,0))-self.clock()))
                if self.cancelled(): raise CrawlError('cancelled','Đã yêu cầu hủy audit.')
                self.on_request()
                self.last[host] = self.clock()
                request_started=self.clock()
                try:
                    self.client.cookies.clear()
                    with self.client.stream('GET',url) as response:
                        result.status = response.status_code
                        result.headers = {k:v[:8000] for k,v in response.headers.items() if k in ('content-type','location','x-robots-tag','link','retry-after','cache-control','etag','content-encoding')}
                        result.headers['x-robots-tag-values']=response.headers.get_list('x-robots-tag')[:20]
                        body = bytearray()
                        # Bound compressed input BEFORE decoding, then bound expanded output.
                        # iter_bytes could allocate a gzip bomb inside httpx before our size check.
                        predecoded=response.is_stream_consumed  # In-memory fixture transports only.
                        chunks=response.iter_bytes(chunk_size=16*1024) if predecoded else response.iter_raw()
                        for chunk in chunks:
                            if self.cancelled():raise CrawlError('cancelled','Đã yêu cầu hủy audit.')
                            if self.clock()-request_started>self.config['timeout_seconds']:
                                raise httpx.ReadTimeout('Response exceeded request deadline')
                            if len(body)+len(chunk)>body_limit:
                                result.truncated=True;break
                            body.extend(chunk)
                        raw=bytes(body);encoding='identity' if predecoded else response.headers.get('content-encoding','identity').lower()
                        if not result.truncated:
                            if encoding=='gzip':
                                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:raw=stream.read(body_limit+1)
                            elif encoding=='deflate':
                                try:raw=zlib.decompressobj().decompress(raw,body_limit+1)
                                except zlib.error:raw=zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw,body_limit+1)
                            elif encoding not in ('identity',''):result.error='unsupported_content_encoding'
                        result.truncated=result.truncated or len(raw)>body_limit
                        result.body=raw[:body_limit]
                except httpx.TimeoutException:
                    result.status=None; result.error='timeout'; break
                except (httpx.HTTPError, OSError, ssl.SSLError, EOFError, zlib.error):
                    result.status=None; result.error='network_or_tls_error'; break
                if result.status in (429,500,502,503,504):
                    self.failures[host]=self.failures.get(host,0)+1
                    delay=retry_delay(result.headers.get('retry-after'),2**(attempt+1))
                    if attempt==0 and delay<=30:
                        self.wait(delay);continue
                    if delay>30:self.failures[host]=3
                elif result.status and result.status<500: self.failures[host]=0
                break
            result.url=url
            if result.error: break
            if result.status not in (301,302,303,307,308): break
            location=result.headers.get('location')
            if not location:
                result.error='redirect_missing_location';break
            try:
                target=normalize(location,url)
                self.scope.check(target)
            except CrawlError:
                result.chain.append({'url':url,'status':result.status,'target':location[:2048]})
                result.error='external_or_unsafe_redirect';break
            result.chain.append({'url':url,'status':result.status,'target':target})
            if not self.config['follow_redirects']: break
            if hop==8:
                result.error='redirect_limit';break
            url=target
        result.duration_ms=round((self.clock()-start)*1000,2)
        return result

    def close(self): self.client.close()
