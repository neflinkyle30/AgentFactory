/**
 * SSE (Server-Sent Events) client for Agent Factory run streaming.
 *
 * Connects to GET /api/runs/{runId}/stream and parses typed events.
 * Includes auto-reconnect with exponential backoff.
 */

// ── Types ──────────────────────────────────────────────────────────────

/** Known SSE event types emitted by the backend */
export type SSEEventType =
  | 'phase_started'
  | 'phase_completed'
  | 'gate_passed'
  | 'gate_failed'
  | 'log'
  | 'chunk'
  | 'error'
  | 'budget_update';

/** Parsed SSE event */
export interface SSEEvent {
  event: SSEEventType;
  run_id: string;
  data: Record<string, unknown>;
}

/** Connection state */
export type SSEConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

/** Callbacks for SSE events */
export interface SSEEventHandlers {
  onEvent?: (event: SSEEvent) => void;
  onPhaseStarted?: (event: SSEEvent) => void;
  onPhaseCompleted?: (event: SSEEvent) => void;
  onGatePassed?: (event: SSEEvent) => void;
  onGateFailed?: (event: SSEEvent) => void;
  onLog?: (event: SSEEvent) => void;
  onChunk?: (event: SSEEvent) => void;
  onError?: (event: SSEEvent) => void;
  onBudgetUpdate?: (event: SSEEvent) => void;
  onConnectionChange?: (state: SSEConnectionState) => void;
}

// ── Options ────────────────────────────────────────────────────────────

export interface SSEClientOptions {
  /** Base URL for the API (default: '' for proxy) */
  baseUrl?: string;
  /** Maximum reconnection attempts before giving up (default: 10) */
  maxReconnectAttempts?: number;
  /** Initial delay in ms before first reconnect (default: 1000) */
  reconnectDelay?: number;
  /** Maximum delay cap in ms (default: 30000) */
  maxReconnectDelay?: number;
  /** Auth token override (by default reads from localStorage) */
  getAccessToken?: () => string | null;
}

// ── SSE Client ─────────────────────────────────────────────────────────

export function createSSEClient(
  runId: string,
  handlers: SSEEventHandlers,
  options: SSEClientOptions = {},
) {
  const {
    baseUrl = '',
    maxReconnectAttempts = 10,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    getAccessToken: getToken = () => localStorage.getItem('agent_factory_access_token'),
  } = options;

  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  const setConnectionState = (state: SSEConnectionState) => {
    if (!destroyed) {
      handlers.onConnectionChange?.(state);
    }
  };

  const connect = () => {
    if (destroyed) return;

    setConnectionState('connecting');

    const token = getToken();
    const url = new URL(`${baseUrl}/api/runs/${encodeURIComponent(runId)}/stream`, window.location.origin);

    // EventSource doesn't support custom headers.
    // Pass the token as a query parameter for auth in SSE connections.
    // The backend should accept ?token=... as a fallback auth mechanism.
    if (token) {
      url.searchParams.set('token', token);
    }

    eventSource = new EventSource(url.toString());

    eventSource.onopen = () => {
      reconnectAttempts = 0;
      setConnectionState('connected');
    };

    eventSource.onmessage = (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data) as SSEEvent;
        handlers.onEvent?.(parsed);

        // Dispatch to type-specific handlers
        switch (parsed.event) {
          case 'phase_started':
            handlers.onPhaseStarted?.(parsed);
            break;
          case 'phase_completed':
            handlers.onPhaseCompleted?.(parsed);
            break;
          case 'gate_passed':
            handlers.onGatePassed?.(parsed);
            break;
          case 'gate_failed':
            handlers.onGateFailed?.(parsed);
            break;
          case 'log':
            handlers.onLog?.(parsed);
            break;
          case 'chunk':
            handlers.onChunk?.(parsed);
            break;
          case 'error':
            handlers.onError?.(parsed);
            break;
          case 'budget_update':
            handlers.onBudgetUpdate?.(parsed);
            break;
        }
      } catch {
        // Ignore malformed JSON events
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;

      if (destroyed) return;

      setConnectionState(reconnectAttempts >= maxReconnectAttempts ? 'error' : 'disconnected');

      // Attempt reconnect with exponential backoff
      if (reconnectAttempts < maxReconnectAttempts) {
        const delay = Math.min(
          reconnectDelay * Math.pow(2, reconnectAttempts),
          maxReconnectDelay,
        );
        reconnectAttempts += 1;
        reconnectTimer = setTimeout(connect, delay);
      }
    };
  };

  const disconnect = () => {
    destroyed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    eventSource?.close();
    eventSource = null;
    setConnectionState('disconnected');
  };

  // Start
  connect();

  return { disconnect, reconnect: connect };
}
