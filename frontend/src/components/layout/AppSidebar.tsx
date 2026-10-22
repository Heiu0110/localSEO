import { Activity, ChartNoAxesCombined, ChevronLeft, ChevronRight, FileChartColumn, Globe2, Layers3, LayoutDashboard, Link2, Network, Settings2, Target } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { Button } from '../ui/button';
import { Tooltip } from '../ui/tooltip';

export const modules = [
  { path: '/', label: 'Tổng quan', icon: LayoutDashboard },
  { path: '/gsc-analytics', label: 'Phân tích GSC', icon: ChartNoAxesCombined },
  { path: '/technical-seo', label: 'Technical SEO', icon: Activity },
  { path: '/keyword-tracking', label: 'Theo dõi từ khóa', icon: Target },
  { path: '/topical-map', label: 'Topical Map', icon: Network },
  { path: '/internal-links', label: 'Liên kết nội bộ', icon: Link2 },
  { path: '/seo-reports', label: 'Báo cáo SEO', icon: FileChartColumn },
  { path: '/settings', label: 'Cài đặt', icon: Settings2 },
];

export function AppSidebar({ collapsed, toggle }: { collapsed: boolean; toggle: () => void }) {
  const { pathname, search } = useLocation();
  return <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
    <NavLink to={{ pathname: '/', search }} className="brand" aria-label="Trang chủ SEO Local Workspace"><span className="brand-mark"><ChartNoAxesCombined size={23} /></span><span className="brand-name">SEO Local<span>KHÔNG GIAN SEO</span></span></NavLink>
    <div className="sidebar-section">KHÔNG GIAN LÀM VIỆC</div>
    <nav aria-label="Điều hướng chính">{modules.slice(0, -1).map(({ path, label, icon: Icon }) => {
      const link = <NavLink key={path} end={path === '/'} to={{ pathname: path, search }} className={`nav-item ${pathname === path ? 'active' : ''}`} aria-label={label}><Icon size={19} /><span>{label}</span>{path === '/' && <span className="nav-active-dot" />}</NavLink>;
      return collapsed ? <Tooltip text={label} key={path}>{link}</Tooltip> : link;
    })}</nav>
    <div className="sidebar-bottom"><div className="local-note"><Globe2 size={19} /><div><strong>Không gian làm việc riêng</strong><span>Riêng tư. Đơn giản. Tập trung.</span></div></div>
      <NavLink to={{ pathname: '/settings', search }} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} aria-label="Cài đặt"><Settings2 size={19} /><span>Cài đặt</span></NavLink>
      <div className="sidebar-footer"><span><Layers3 size={14} /> Nền tảng v0.3</span><Button variant="ghost" size="icon" className="collapse-button" onClick={toggle} aria-label={collapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'} aria-expanded={!collapsed}>{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</Button></div>
    </div>
  </aside>;
}
