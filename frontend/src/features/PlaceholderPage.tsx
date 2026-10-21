import { ArrowLeft, Construction } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { modules } from '../components/layout/AppSidebar';
import { Button } from '../components/ui/button';

export function PlaceholderPage() {
  const { pathname, search } = useLocation();
  const module = modules.find(m => m.path === pathname);
  return <div className="placeholder-page"><div className="placeholder-icon"><Construction size={30} /></div><span className="badge badge-neutral">{module ? 'PHIÊN BẢN TƯƠNG LAI' : '404'}</span><h1>{module?.label ?? 'Không tìm thấy trang'}</h1><p>{module ? 'Chức năng này dự kiến có trong phiên bản tương lai.' : 'Trang này không tồn tại trong không gian làm việc của bạn.'}</p><p className="muted">Bạn có thể xem hiệu suất tìm kiếm tại trang Tổng quan.</p><Button asChild><Link to={{ pathname: '/', search }}><ArrowLeft size={16} />Về trang Tổng quan</Link></Button></div>;
}
