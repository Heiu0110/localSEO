import { queryOptions } from "@tanstack/react-query";
import { api, mutate } from "./apiClient";
export function aiQuery<T>(path: string, enabled = true) {
  return queryOptions({
    queryKey: ["ai", path],
    queryFn: ({ signal }) => api<T>("/ai" + path, signal),
    enabled,
    staleTime: 10000,
  });
}
export function aiWrite<T>(
  path: string,
  body?: unknown,
  method: "POST" | "PATCH" = "POST",
) {
  return mutate<T>("/ai" + path, body, method);
}
