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
  const title = modules.find(m => m.path === location.pathname)?.label ?? 'Không tìm thấy trang';
  const toggle = () => setCollapsed(value => {
    try { localStorage.setItem('sidebar-collapsed', String(!value)); } catch { /* Storage is optional. */ }
    return !value;
  });
  return <div className={`app-shell ${collapsed ? 'sidebar-small' : ''}`}>
    <a className="skip-link" href="#main-content">Chuyển đến nội dung</a>
    <AppSidebar collapsed={collapsed} toggle={toggle} />
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><Button className="mobile-toggle" variant="ghost" size="icon" onClick={toggle} aria-label="Ẩn/hiện thanh bên"><PanelLeft size={18} /></Button><span>Không gian làm việc</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="local-badge"><span className="status-dot" /><Laptop size={15} />Môi trường cục bộ</div></header>
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      <footer className="app-footer"><span>SEO Local Workspace <span className="footer-divider">/</span> Nền tảng v0.1</span><span>Hiểu rõ hơn hiệu suất tìm kiếm.</span></footer>
    </div>
  </div>;
}
