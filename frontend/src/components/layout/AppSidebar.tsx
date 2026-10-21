import { Activity, ChartNoAxesCombined, ChevronLeft, ChevronRight, FileChartColumn, Globe2, Layers3, LayoutDashboard, Link2, Network, Settings2, Target } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { Button } from '../ui/button';
import { Tooltip } from '../ui/tooltip';

export const modules = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/gsc-analytics', label: 'GSC Analytics', icon: ChartNoAxesCombined },
  { path: '/technical-seo', label: 'Technical SEO', icon: Activity },
  { path: '/keyword-tracking', label: 'Keyword Tracking', icon: Target },
  { path: '/topical-map', label: 'Topical Map', icon: Network },
  { path: '/internal-links', label: 'Internal Links', icon: Link2 },
  { path: '/seo-reports', label: 'SEO Reports', icon: FileChartColumn },
  { path: '/settings', label: 'Settings', icon: Settings2 },
];

export function AppSidebar({ collapsed, toggle }: { collapsed: boolean; toggle: () => void }) {
  const { search } = useLocation();
  return <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
    <NavLink to={{ pathname: '/', search }} className="brand" aria-label="SEO Local Workspace home"><span className="brand-mark"><ChartNoAxesCombined size={23} /></span><span className="brand-name">SEO Local<span>WORKSPACE</span></span></NavLink>
    <div className="sidebar-section">WORKSPACE</div>
    <nav aria-label="Main navigation">{modules.slice(0, -1).map(({ path, label, icon: Icon }) => {
      const link = <NavLink key={path} end={path === '/'} to={{ pathname: path, search }} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} aria-label={label}><Icon size={19} /><span>{label}</span>{path === '/' && <span className="nav-active-dot" />}</NavLink>;
      return collapsed ? <Tooltip text={label} key={path}>{link}</Tooltip> : link;
    })}</nav>
    <div className="sidebar-bottom"><div className="local-note"><Globe2 size={19} /><div><strong>Your local workspace</strong><span>Private. Simple. Focused.</span></div></div>
      <NavLink to={{ pathname: '/settings', search }} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} aria-label="Settings"><Settings2 size={19} /><span>Settings</span></NavLink>
      <div className="sidebar-footer"><span><Layers3 size={14} /> Foundation v0.1</span><Button variant="ghost" size="icon" className="collapse-button" onClick={toggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</Button></div>
    </div>
  </aside>;
}
