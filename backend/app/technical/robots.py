import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class Robots:
    state: str = 'unknown'
    groups: list = field(default_factory=list)
    sitemaps: list = field(default_factory=list)
    status: int | None = None
    error: str | None = None

    @classmethod
    def parse(cls, fetched):
        result = cls(status=fetched.status,error=fetched.error)
        if fetched.error or fetched.truncated: return result
        if fetched.status in (404,410): result.state='missing';return result
        if fetched.status in (401,403): result.state='denied';return result
        if not fetched.status or not 200<=fetched.status<300: return result
        text = fetched.body.decode('utf-8-sig',errors='replace')
        if '\ufffd' in text or '<html' in text[:1000].lower():
            result.error='invalid_robots';return result
        groups,agents,rules,delay=[],[],[],None
        had_directive=False
        for raw in text.splitlines():
            line=raw.split('#',1)[0].strip()
            if ':' not in line: continue
            name,value=(v.strip() for v in line.split(':',1)); name=name.lower()
            if name=='sitemap' and value: result.sitemaps.append(value)
            elif name=='user-agent':
                if had_directive:
                    groups.append((agents,rules,delay));agents,rules,delay=[],[],None
                    had_directive=False
                agents.append(value.lower())
            elif agents and name in ('allow','disallow'):
                had_directive=True
                if value:rules.append((value,name=='allow'))
            elif agents and name=='crawl-delay':
                had_directive=True
                try: delay=float(value)
                except ValueError: pass
        if agents: groups.append((agents,rules,delay))
        result.groups,result.state=groups,'parsed'
        return result

    def selected(self, agent):
        candidates=[]
        for agents,rules,delay in self.groups:
            matches=[len(a) if a!='*' else 0 for a in agents if a=='*' or a in agent.lower()]
            if matches: candidates.append((max(matches),rules,delay))
        best=max((x[0] for x in candidates),default=-1)
        return [(rules,delay) for score,rules,delay in candidates if score==best]

    def delay(self,agent):
        values=[d for _,d in self.selected(agent) if d is not None]
        return max(values,default=0)

    def allowed(self,url,agent='LocalSEOWorkspace'):
        if self.state=='denied': return False
        if self.state=='unknown': return None
        if self.delay(agent)>60: return None
        parsed=urlsplit(url);path=parsed.path+('?' + parsed.query if parsed.query else '')
        matches=[]
        for rules,_ in self.selected(agent):
            for pattern,allow in rules:
                end=pattern.endswith('$');pattern=pattern[:-1] if end else pattern
                expression='^'+'.*'.join(re.escape(p) for p in pattern.split('*'))+('$' if end else '')
                if re.search(expression,path): matches.append((len(pattern.replace('*','')),allow))
        return max(matches,default=(0,True))[1]
