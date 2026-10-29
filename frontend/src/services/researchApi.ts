import { queryOptions } from "@tanstack/react-query";
import { api, mutate, ApiError } from "./apiClient";
export const researchQuery = <T>(path: string, enabled = true) =>
  queryOptions({
    queryKey: ["research", path],
    queryFn: ({ signal }) => api<T>("/research" + path, signal),
    enabled,
    staleTime: 10000,
  });
export const researchWrite = <T>(
  path: string,
  body?: unknown,
  method: "POST" | "PATCH" = "POST",
) => mutate<T>("/research" + path, body, method);
export async function researchExport(
  project: string,
  kind: string,
  format: string,
  snapshot?: string,
) {
  const query = new URLSearchParams({ project_id: project, kind, format });
  if (snapshot) query.set("snapshot_id", snapshot);
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || "/api"}/research/export?${query}`,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.detail || "Không xuất được Research.",
      response.status,
    );
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `research-${kind}.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
