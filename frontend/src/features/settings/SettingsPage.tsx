import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Database, ExternalLink, Link2, ShieldCheck, Upload } from 'lucide-react';
import { integrationQuery, propertiesQuery } from '../../services/gscApi';
import { mutate } from '../../services/apiClient';
import { Button } from '../../components/ui/button';
import { EmptyState, ErrorState } from '../../components/ui/states';
import { SourceBadge } from '../../components/dashboard/SourceBadge';
import { SyncPanel, jobLabels } from '../../components/gsc/SyncPanel';
import { date, timestamp } from '../../lib/format';
import type { GSCProperty } from '../../types/gsc';

const states: Record<string, string> = { not_configured: 'Chưa cấu hình', ready: 'Sẵn sàng kết nối', connected: 'Đã kết nối',
  disconnected: 'Đã ngắt kết nối', reauthorization_required: 'Cần xác thực lại', connection_error: 'Lỗi kết nối' };

export function SettingsPage() {
  const client = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [authUrl, setAuthUrl] = useState('');
  const [notice, setNotice] = useState('');
  const [params, setParams] = useSearchParams();
  const status = useQuery({ ...integrationQuery, refetchInterval: authUrl ? 2000 : false });
  const properties = useQuery(propertiesQuery);
  const active = properties.data?.filter(p => p.is_active) ?? [];
  const selected = active.find(p => p.id === params.get('site')) ?? active[0];
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => mutate<{ authorization_url?: string; message?: string }>(path, body),
    onMutate: ({ path, body }) => {
      if (path !== '/integrations/gsc/properties') return undefined;
      const selection = body as { property_id: string; is_active: boolean };
      const previous = client.getQueryData<GSCProperty[]>(['gsc-properties']);
      void client.cancelQueries({ queryKey: ['gsc-properties'] });
      client.setQueryData<GSCProperty[]>(['gsc-properties'], current => current?.map(p => p.id === selection.property_id ? { ...p, is_active: selection.is_active } : p));
      return previous;
    },
    onError: (_error, _variables, previous) => {
      if (previous) client.setQueryData(['gsc-properties'], previous);
    },
    onSuccess: result => {
      if (result.authorization_url) { setAuthUrl(result.authorization_url); window.open(result.authorization_url, '_blank', 'noopener,noreferrer'); }
      if (result.message) setNotice(result.message);
      void client.invalidateQueries();
    },
  });
  useEffect(() => {
    if (authUrl && status.data?.status === 'connected' && !status.data.pending_authorization) {
      setAuthUrl('');
      action.mutate({ path: '/integrations/gsc/properties/refresh' });
    }
    if (authUrl && status.data?.status === 'connection_error' && !status.data.pending_authorization) setAuthUrl('');
  }, [authUrl, status.data?.status, status.data?.pending_authorization, action.mutate]);
  function configure(file?: File) {
    if (!file) return;
    if (file.size > 64 * 1024) { setNotice('Tệp OAuth JSON tối đa 64 KB.'); return; }
    const body = new FormData(); body.append('file', file);
    action.mutate({ path: '/integrations/gsc/configure', body });
  }
  return <div className="settings-page"><div className="page-title-row"><div><div className="eyebrow">NGUỒN DỮ LIỆU VÀ ĐỒNG BỘ</div><h1>Cài đặt</h1><p>Kết nối Google Search Console, quản lý property và dữ liệu cục bộ.</p></div></div>
    <section className="card integration-card"><div className="card-heading"><div><h2><Link2 size={17} />Tích hợp Google Search Console</h2><p>Chỉ quyền đọc · OAuth Desktop · lưu token trong kho khóa hệ điều hành.</p></div><span className="badge badge-neutral">{status.isPending ? 'Đang kiểm tra…' : states[status.data?.status ?? ''] ?? 'Chưa kết nối'}</span></div><div className="integration-body">
      {status.isError ? <ErrorState message={status.error.message} onRetry={() => void status.refetch()} /> : <>
        {status.data?.message && <div className="report-warning"><ShieldCheck size={17} /><p>{status.data.message} Bạn vẫn dùng được Demo và dữ liệu SQLite đã lưu.</p></div>}
        <ol className="setup-steps"><li>Tạo OAuth client loại <strong>Desktop app</strong> trong Google Cloud; bật Search Console API và thêm test user nếu ứng dụng còn ở chế độ Testing.</li><li>Nhập credentials JSON bên dưới, rồi cấp quyền Google bằng tài khoản có quyền truy cập property.</li><li>Làm mới danh sách, thêm property vào workspace và đồng bộ lịch sử. Không cần sửa mã nguồn.</li></ol>
        <div className="integration-actions"><input ref={fileInput} className="sr-only" aria-label="Tệp OAuth Desktop JSON" type="file" accept=".json,application/json" onChange={e => { configure(e.target.files?.[0]); e.target.value = ''; }} /><Button variant="outline" disabled={action.isPending || status.data?.status === 'connected'} onClick={() => fileInput.current?.click()}><Upload size={15} />Nhập tệp OAuth JSON</Button>
          {status.data?.configured && status.data.status !== 'connected' && <Button disabled={action.isPending || !status.data.secure_storage_available} onClick={() => action.mutate({ path: '/integrations/gsc/oauth/start' })}><Link2 size={15} />{status.data.status === 'reauthorization_required' || status.data.status === 'disconnected' ? 'Kết nối lại Google' : 'Kết nối Google'}</Button>}
          {status.data?.status === 'connected' && <><Button variant="outline" disabled={action.isPending} onClick={() => action.mutate({ path: '/integrations/gsc/properties/refresh' })}>Làm mới properties</Button><Button variant="outline" disabled={action.isPending} onClick={() => { if (window.confirm('Ngắt kết nối và yêu cầu thu hồi quyền Google? Dữ liệu SQLite vẫn được giữ.')) action.mutate({ path: '/integrations/gsc/disconnect', body: { revoke: true } }); }}>Ngắt kết nối Google</Button></>}
          <Button asChild variant="ghost"><a href="https://console.cloud.google.com/apis/library/searchconsole.googleapis.com" target="_blank" rel="noreferrer">Google Cloud<ExternalLink size={13} /></a></Button></div>
        {authUrl && <p className="muted-copy">Đang chờ xác thực trong trình duyệt. Nếu cửa sổ chưa mở, <a href={authUrl} target="_blank" rel="noreferrer">tiếp tục kết nối Google</a>. Phiên có hiệu lực 10 phút.</p>}
        <p className="muted-copy">Chỉ dùng scope webmasters.readonly. Không yêu cầu quyền Gmail, Drive hoặc hồ sơ cá nhân. Hướng dẫn đầy đủ: docs/GOOGLE_GSC_SETUP.md.</p>
      </>}
      {action.isError && <p role="alert" className="action-error">{action.error.message}</p>}{notice && <p role="status" className="muted-copy">{notice}</p>}
    </div></section>
    <section className="card integration-card"><div className="card-heading"><div><h2><Database size={17} />Properties trong workspace</h2><p>Giữ nguyên Domain và URL-prefix identifiers. Bỏ chọn chỉ ẩn property, không xóa lịch sử.</p></div></div><div className="integration-body">
      {properties.isPending ? <p className="muted-copy">Đang tải properties…</p> : properties.isError ? <ErrorState message={properties.error.message} onRetry={() => void properties.refetch()} /> : !properties.data.length ? <EmptyState title="Chưa có property" detail="Kết nối Google để lấy danh sách, hoặc tạo bộ thử nghiệm SQLite ở bên dưới." /> : <div className="property-list">{properties.data.map(property => <div className="property-item" key={property.id}><div><strong>{property.site_url}</strong><div className="property-meta"><SourceBadge source={property.source_type} /><span>{property.property_type === 'domain' ? 'Domain property' : 'URL-prefix property'} · {property.permission_level}</span><span>{jobLabels[property.sync_status] ?? property.sync_status}</span></div><p className="muted-copy">Web đã lưu: {property.local_start && property.local_end ? `${date(property.local_start)} – ${date(property.local_end)}` : 'Chưa có dữ liệu'} · Đồng bộ gần nhất: {property.last_synced_at ? timestamp(property.last_synced_at) : 'Chưa đồng bộ'}</p></div><label className="property-check"><input type="checkbox" aria-label={`Thêm ${property.site_url} vào workspace`} checked={property.is_active} disabled={action.isPending || ['queued','running'].includes(property.sync_status)} onChange={e => action.mutate({ path: '/integrations/gsc/properties', body: { property_id: property.id, is_active: e.target.checked } })} />Trong workspace</label></div>)}</div>}
      <div className="fixture-tools"><p className="muted-copy">Kiểm tra SQLite và đồng bộ mà không cần Google: tạo properties dành riêng cho thử nghiệm. Chúng luôn được ghi nhãn, không phải dữ liệu GSC thật và không thay thế hai website demo.</p><Button variant="outline" disabled={action.isPending} onClick={() => action.mutate({ path: '/integrations/gsc/fixtures' })}>Tạo bộ thử nghiệm SQLite</Button></div>
    </div></section>
    {active.length > 0 && <label className="sync-property-label">Property cần đồng bộ<select aria-label="Property cần đồng bộ" value={selected?.id} onChange={e => setParams(old => { old.set('site', e.target.value); return old; })}>{active.map(p => <option key={p.id} value={p.id}>{p.site_url}</option>)}</select></label>}
    <SyncPanel key={selected?.id ?? 'none'} property={selected} />
  </div>;
}
