import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { ChevronRight, Laptop, PanelLeft } from 'lucide-react';
import { AppSidebar, modules } from './AppSidebar';
import { Button } from '../ui/button';

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('sidebar-collapsed');
      return saved === null ? window.matchMedia('(max-width: 950px)').matches : saved === 'true';
    } catch { return window.matchMedia('(max-width: 950px)').matches; }
  });
  const location = useLocation();
  const title = modules.find(m => m.path === location.pathname)?.label ?? 'Page not found';
  const toggle = () => setCollapsed(value => {
    try { localStorage.setItem('sidebar-collapsed', String(!value)); } catch { /* Storage is optional. */ }
    return !value;
  });
  return <div className={`app-shell ${collapsed ? 'sidebar-small' : ''}`}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <AppSidebar collapsed={collapsed} toggle={toggle} />
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><Button className="mobile-toggle" variant="ghost" size="icon" onClick={toggle} aria-label="Toggle sidebar"><PanelLeft size={18} /></Button><span>Workspace</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="local-badge"><span className="status-dot" /><Laptop size={15} />Local environment</div></header>
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      <footer className="app-footer"><span>SEO Local Workspace <span className="footer-divider">/</span> Foundation v0.1</span><span>Built for a clearer view of search.</span></footer>
    </div>
  </div>;
}
