import { queryOptions } from "@tanstack/react-query";
import { api, mutate, ApiError } from "./apiClient";
export const keywordBase = "/keyword-tracking";
export function keywordQuery<T>(path: string, enabled = true) {
  return queryOptions({
    queryKey: ["keywords", path],
    queryFn: ({ signal }) => api<T>(keywordBase + path, signal),
    enabled,
    staleTime: 15000,
  });
}
export function keywordWrite<T>(
  path: string,
  body?: unknown,
  method: "POST" | "PATCH" = "POST",
) {
  return mutate<T>(keywordBase + path, body, method);
}
export async function keywordExport(
  params: URLSearchParams,
  format: "csv" | "xlsx",
) {
  const query = new URLSearchParams(params);
  query.delete("page");
  query.delete("page_size");
  query.set("format", format);
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || "/api"}${keywordBase}/export?${query}`,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.detail || "Không xuất được báo cáo. Thử lại sau.",
      response.status,
    );
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `keyword-tracking.${format}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
