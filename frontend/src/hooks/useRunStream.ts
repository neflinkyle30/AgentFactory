import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  createSSEClient,
  type SSEConnectionState,
  type SSEEventHandlers,
} from '../lib/sse';

// ── Types ──────────────────────────────────────────────────────────────

export interface UseRunStreamOptions {
  /** Enable auto-reconnect (default: true) */
  autoReconnect?: boolean;
  /** Callback for connection state changes */
  onConnectionChange?: (state: SSEConnectionState) => void;
  /** Callback for budget updates */
  onBudgetUpdate?: (tokens: number, costUsd: number) => void;
}

export interface UseRunStreamResult {
  /** Current SSE connection state */
  connectionState: SSEConnectionState;
  /** Manually reconnect */
  reconnect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
}

// ── Hook ───────────────────────────────────────────────────────────────

/**
 * React hook for streaming run events via SSE.
 *
 * Connects to GET /api/runs/{runId}/stream and updates React Query
 * cache for the run on each event. Auto-reconnects on disconnect.
 *
 * @param runId  - The run UUID to stream
 * @param options - Optional callbacks and config
 * @returns Connection state and control functions
 */
export function useRunStream(
  runId: string | undefined,
  options: UseRunStreamOptions = {},
): UseRunStreamResult {
  const { onConnectionChange, onBudgetUpdate } = options;
  const queryClient = useQueryClient();
  const clientRef = useRef<ReturnType<typeof createSSEClient> | null>(null);
  const [connectionState, setConnectionState] = useState<SSEConnectionState>('disconnected');

  // Build event handlers — stable refs via useRef to avoid reconnecting on every render
  const handlersRef = useRef<SSEEventHandlers>({});

  handlersRef.current = {
    onConnectionChange: (state: SSEConnectionState) => {
      setConnectionState(state);
      onConnectionChange?.(state);
    },

    onEvent: (_event) => {
      // Invalidate the run cache to trigger a refetch when the user views the run
      if (runId) {
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
        queryClient.invalidateQueries({ queryKey: ['runs'] });
      }
    },

    onPhaseStarted: (_event) => {
      if (runId) {
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
      }
    },

    onPhaseCompleted: (_event) => {
      if (runId) {
        // Refetch full run detail on phase completion
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
      }
    },

    onBudgetUpdate: (event) => {
      const data = event.data;
      onBudgetUpdate?.(data.tokens as number, data.cost_usd as number);
    },
  };

  // Connect / reconnect when runId changes
  useEffect(() => {
    if (!runId) {
      return;
    }

    const client = createSSEClient(runId, {
      onConnectionChange: (state) => {
        setConnectionState(state);
        onConnectionChange?.(state);
      },
      onEvent: () => {
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
        queryClient.invalidateQueries({ queryKey: ['runs'] });
      },
      onPhaseStarted: () => {
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
      },
      onPhaseCompleted: () => {
        queryClient.invalidateQueries({ queryKey: ['run', runId] });
      },
      onBudgetUpdate: (event) => {
        const data = event.data;
        onBudgetUpdate?.(data.tokens as number, data.cost_usd as number);
      },
    });

    clientRef.current = client;

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const reconnect = useCallback(() => {
    clientRef.current?.reconnect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  return { connectionState, reconnect, disconnect };
}

// ── Re-export for convenience ─────────────────────────────────────────

export type { SSEConnectionState };
