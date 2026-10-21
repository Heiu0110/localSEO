import { ArrowLeft, Construction } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { modules } from '../components/layout/AppSidebar';
import { Button } from '../components/ui/button';

export function PlaceholderPage() {
  const { pathname, search } = useLocation();
  const module = modules.find(m => m.path === pathname);
  return <div className="placeholder-page"><div className="placeholder-icon"><Construction size={30} /></div><span className="badge badge-neutral">{module ? 'FUTURE RELEASE' : '404'}</span><h1>{module?.label ?? 'Page not found'}</h1><p>{module ? 'Module is planned for a future release.' : 'This page does not exist in your local workspace.'}</p><p className="muted">Your search performance dashboard is ready to explore.</p><Button asChild><Link to={{ pathname: '/', search }}><ArrowLeft size={16} />Back to Dashboard</Link></Button></div>;
}
