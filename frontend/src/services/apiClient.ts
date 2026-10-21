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
    throw new ApiError('Cannot reach the local API. Start the backend and try again.', 0);
  }
  if (!response.ok) {
    throw new ApiError(response.status === 404 ? 'The requested demo site or page was not found.' : `API request failed (${response.status}). Please try again.`, response.status);
  }
  return response.json() as Promise<T>;
}
