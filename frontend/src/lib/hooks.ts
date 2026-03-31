import { useQuery, useMutation, keepPreviousData } from "@tanstack/react-query";
import { get, post } from "./api";
import type {
  PaginatedResponse,
  StatsResponse,
  AskResponse,
  AskRequest,
  DigestResponse,
  AlertsCheckResponse,
  ConfigResponse,
  ResearchItem,
} from "./types";

export function useItems(
  source?: string,
  offset: number = 0,
  limit: number = 20,
) {
  return useQuery<PaginatedResponse>({
    queryKey: ["items", source, offset, limit],
    queryFn: () =>
      get<PaginatedResponse>("/api/items", {
        ...(source && source !== "all" ? { source } : {}),
        offset,
        limit,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useItem(id: number) {
  return useQuery<ResearchItem>({
    queryKey: ["item", id],
    queryFn: () => get<ResearchItem>(`/api/items/${id}`),
    enabled: !!id,
  });
}

export function useStats() {
  return useQuery<StatsResponse>({
    queryKey: ["stats"],
    queryFn: () => get<StatsResponse>("/api/stats"),
  });
}

export function useAsk() {
  return useMutation<AskResponse, Error, AskRequest>({
    mutationFn: (data) => post<AskResponse>("/api/ask", data),
  });
}

export function useDigest(frequency: string = "daily", format: string = "markdown") {
  return useQuery<DigestResponse>({
    queryKey: ["digest", frequency, format],
    queryFn: () =>
      get<DigestResponse>("/api/digest", { frequency, fmt: format }),
    enabled: false, // Only fetch on manual trigger
  });
}

export function useAlerts() {
  return useQuery<AlertsCheckResponse>({
    queryKey: ["alerts"],
    queryFn: () => post<AlertsCheckResponse>("/api/alerts/check", []),
  });
}

export function useConfig() {
  return useQuery<ConfigResponse>({
    queryKey: ["config"],
    queryFn: () => get<ConfigResponse>("/api/config"),
  });
}
