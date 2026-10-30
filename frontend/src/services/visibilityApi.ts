import { queryOptions } from "@tanstack/react-query";
import { api, mutate } from "./apiClient";
export const visibilityQuery = <T>(path: string, enabled = true) =>
  queryOptions({
    queryKey: ["visibility", path],
    queryFn: ({ signal }) => api<T>("/visibility" + path, signal),
    enabled,
    staleTime: 5000,
  });
export const visibilityWrite = <T>(
  path: string,
  body: unknown,
  method: "POST" | "PATCH" = "POST",
) => mutate<T>("/visibility" + path, body, method);
