export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}

const base = import.meta.env.VITE_API_BASE_URL || '/api';
let csrf: string | null = null;
export async function mutate<T>(path: string, body?: unknown, method: 'POST' | 'PATCH' = 'POST'): Promise<T> {
  if (!csrf) {
    const session = await api<{ csrf_token: string }>('/session');
    csrf = session.csrf_token;
  }
  const form = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { method, headers: { 'X-CSRF-Token': csrf, ...(form ? {} : { 'Content-Type': 'application/json' }) }, body: form ? body : JSON.stringify(body ?? {}) });
  } catch {
    throw new ApiError('Không thể kết nối backend cục bộ. Kiểm tra tiến trình backend rồi thử lại.', 0);
  }
  const result = await response.json().catch(() => ({ detail: 'API chưa trả phản hồi hợp lệ. Hãy kiểm tra backend và thử lại.' }));
  if (!response.ok) {
    if (result.code === 'csrf_required') csrf = null;
    throw new ApiError(typeof result.detail === 'string' ? result.detail : 'Yêu cầu chưa hợp lệ. Kiểm tra dữ liệu đã nhập.', response.status, result.code);
  }
  return result as T;
}

// Default uses the local Vite proxy. No external requests, fonts, or analytics.
export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('Không thể kết nối API cục bộ. Hãy khởi động backend và thử lại.', 0);
  }
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new ApiError(response.status === 404 ? 'Không tìm thấy website hoặc trang đã yêu cầu.' : typeof result?.detail === 'string' && (response.status < 500 || result.code) ? result.detail : `Yêu cầu API thất bại (${response.status}). Vui lòng thử lại.`, response.status, result?.code);
  }
  return response.json() as Promise<T>;
}
