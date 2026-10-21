export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

// Default uses the local Vite proxy. No external requests, fonts, or analytics.
export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}${path}`, { signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('Không thể kết nối API cục bộ. Hãy khởi động backend và thử lại.', 0);
  }
  if (!response.ok) {
    throw new ApiError(response.status === 404 ? 'Không tìm thấy website hoặc trang mô phỏng đã yêu cầu.' : `Yêu cầu API thất bại (${response.status}). Vui lòng thử lại.`, response.status);
  }
  return response.json() as Promise<T>;
}
