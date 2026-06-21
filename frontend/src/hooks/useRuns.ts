/**
 * React Query hooks for the Runs API.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────────────

export interface PhaseStatus {
  phase_name: string;
  status: string; // PENDING, ACTIVE, PASSED, FAILED
  started_at: string | null;
  completed_at: string | null;
  retry_count: number;
  output: Record<string, unknown> | null;
}

export interface RunStatusResponse {
  id: string;
  status: string;
  current_phase: string | null;
  ticket_ref: string | null;
  total_cost_usd: number;
  budget_limit_usd: number | null;
  hitl_enabled: boolean;
  phases: PhaseStatus[];
  created_at: string | null;
  completed_at: string | null;
}

export interface RunListItem {
  id: string;
  status: string;
  current_phase: string | null;
  ticket_ref: string | null;
  total_cost_usd: number;
  created_at: string | null;
}

export interface RunListResponse {
  runs: RunListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AcceptanceCriterion {
  given: string;
  when: string;
  then: string;
}

export interface SubmitRunRequest {
  title: string;
  description?: string;
  acceptance_criteria?: AcceptanceCriterion[];
  priority?: string;
  components?: string[];
  ticket_source?: string;
  ticket_key?: string;
  budget_limit_usd?: number;
  hitl_enabled?: boolean;
}

export interface SubmitRunResponse {
  run_id: string;
  status: string;
  ticket_id: string | null;
  intake_score: number | null;
  intake_passed: boolean;
  message: string;
}

// ── Query keys ─────────────────────────────────────────────────────────

export const runKeys = {
  all: ['runs'] as const,
  lists: () => [...runKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...runKeys.lists(), filters] as const,
  details: () => [...runKeys.all, 'detail'] as const,
  detail: (id: string) => [...runKeys.details(), id] as const,
};

// ── Hooks ──────────────────────────────────────────────────────────────

/** List runs with optional filters */
export function useRuns(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit != null) searchParams.set('limit', String(params.limit));
  if (params?.offset != null) searchParams.set('offset', String(params.offset));

  const queryString = searchParams.toString();
  const path = `/api/runs${queryString ? `?${queryString}` : ''}`;

  return useQuery<RunListResponse>({
    queryKey: runKeys.list(params ?? {}),
    queryFn: () => api.get<RunListResponse>(path),
  });
}

/** Single run detail */
export function useRun(runId: string | undefined) {
  return useQuery<RunStatusResponse>({
    queryKey: runKeys.detail(runId!),
    queryFn: () => api.get<RunStatusResponse>(`/api/runs/${runId}`),
    enabled: !!runId,
  });
}

/** Submit a new ticket/run */
export function useSubmitRun() {
  const queryClient = useQueryClient();

  return useMutation<SubmitRunResponse, Error, SubmitRunRequest>({
    mutationFn: (body) => api.post<SubmitRunResponse>('/api/runs', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: runKeys.all });
    },
  });
}

/** Approve a HITL-paused run */
export function useApproveRun() {
  const queryClient = useQueryClient();

  return useMutation<{ status: string }, Error, string>({
    mutationFn: (runId) => api.post<{ status: string }>(`/api/runs/${runId}/approve`),
    onSuccess: (_data, runId) => {
      queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
      queryClient.invalidateQueries({ queryKey: runKeys.all });
    },
  });
}
