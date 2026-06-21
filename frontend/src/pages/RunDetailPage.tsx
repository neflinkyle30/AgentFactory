import { useParams, Link } from 'react-router-dom';
import { useRun } from '../hooks/useRuns';
import { useRunStream } from '../hooks/useRunStream';
import { PipelineStepper } from '../components/PipelineStepper';

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function activePhaseNumber(phases: PhaseStatus[]): number {
  const activeIdx = phases.findIndex(
    (p) => p.status === 'ACTIVE' || p.status === 'RUNNING' || p.status === 'IN_PROGRESS',
  );
  if (activeIdx >= 0) return activeIdx + 1;
  // Return last phase that has a status
  for (let i = phases.length - 1; i >= 0; i--) {
    if (phases[i].status !== 'PENDING') return i + 1;
  }
  return 1;
}

import type { PhaseStatus } from '../hooks/useRuns';

function getPhaseSymbol(status: string): string {
  switch (status.toUpperCase()) {
    case 'PASSED':
    case 'COMPLETED':
      return '✓';
    case 'ACTIVE':
    case 'RUNNING':
    case 'IN_PROGRESS':
      return '●';
    case 'FAILED':
      return '✗';
    default:
      return '◌';
  }
}

function getPhaseSymbolColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'PASSED':
    case 'COMPLETED':
      return 'var(--color-success)';
    case 'ACTIVE':
    case 'RUNNING':
    case 'IN_PROGRESS':
      return 'var(--color-cyan-accent)';
    case 'FAILED':
      return 'var(--color-danger)';
    default:
      return 'var(--text-tertiary)';
  }
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, isError, error } = useRun(runId);
  const { connectionState } = useRunStream(runId);

  if (isLoading) {
    return (
      <div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
          Loading run {runId}…
        </p>
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-1 mb-4 text-xs"
          style={{ color: 'var(--color-cyan-accent)' }}
        >
          &larr; RETURN TO SCHEDULE
        </Link>
        <div
          className="px-4 py-3 mb-6 text-sm"
          style={{
            backgroundColor: 'var(--color-danger-light-hex)',
            color: 'var(--color-danger-hex)',
            border: '1px solid var(--color-danger-hex)',
          }}
        >
          {error instanceof Error ? error.message : 'Failed to load run.'}
        </div>
      </div>
    );
  }

  const streamIndicator = {
    connecting: 'CONNECTING',
    connected: 'LIVE',
    disconnected: 'RECONNECTING',
    error: 'ERROR',
  }[connectionState];

  const streamColor = {
    connecting: 'var(--color-warning)',
    connected: 'var(--color-success)',
    disconnected: 'var(--color-warning)',
    error: 'var(--color-danger)',
  }[connectionState];

  return (
    <div>
      {/* Top bar: back link + metadata */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-xs"
          style={{ color: 'var(--color-cyan-accent)' }}
        >
          &larr; RETURN TO SCHEDULE
        </Link>

        <div className="flex items-center gap-4" style={{ fontSize: 'var(--text-xs)' }}>
          <span style={{ color: 'var(--text-tertiary)' }}>
            RUN <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>#{run.id.slice(0, 8)}</span>
          </span>
          <span style={{ color: 'var(--text-tertiary)' }}>
            CREATED <span style={{ color: 'var(--text-primary)' }}>{timeAgo(run.created_at)}</span>
          </span>
          <span style={{ color: 'var(--text-tertiary)' }}>
            PHASE{' '}
            <span style={{ color: 'var(--text-primary)' }}>
              {activePhaseNumber(run.phases)}/8 {run.current_phase || '—'}
            </span>
          </span>
          {connectionState !== 'disconnected' && (
            <span
              className="label-uppercase"
              style={{ color: streamColor, fontSize: '0.5625rem' }}
            >
              {streamIndicator}
            </span>
          )}
        </div>
      </div>

      {/* Compact Pipeline Stepper */}
      <div
        className="mb-8 px-6 py-4"
        style={{
          backgroundColor: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
        }}
      >
        <PipelineStepper phases={run.phases} compact />
      </div>

      {/* Two-column layout */}
      <div className="flex flex-col lg:flex-row gap-6 mb-8">
        {/* Left: Phase Output */}
        <div className="flex-1 min-w-0">
          <h2
            className="label-uppercase mb-3"
            style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
          >
            PHASE OUTPUT
          </h2>
          <div
            className="p-6 overflow-auto"
            style={{
              backgroundColor: 'var(--bg-code)',
              color: 'var(--text-code)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-sm)',
              lineHeight: 1.6,
              minHeight: '300px',
              maxHeight: '500px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {run.phases
              .filter((p) => p.output)
              .map((p) => (
                <div key={p.phase_name} className="mb-4">
                  <div
                    style={{ color: 'var(--color-cyan-accent)', fontWeight: 600, marginBottom: 4 }}
                  >
                    // {'>'} {p.phase_name}
                  </div>
                  <div>{JSON.stringify(p.output, null, 2)}</div>
                </div>
              ))}
            {run.phases.filter((p) => p.output).length === 0 && (
              <span style={{ color: 'var(--text-tertiary)' }}>
                Waiting for phase output…
              </span>
            )}
          </div>
        </div>

        {/* Right: Gate Status + Evidence */}
        <div className="flex-shrink-0" style={{ width: '320px' }}>
          {/* Gate Status */}
          <div
            className="mb-6 p-6"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
            }}
          >
            <h2
              className="label-uppercase mb-4"
              style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
            >
              GATE STATUS
            </h2>
            <div style={{ fontSize: 'var(--text-sm)' }}>
              <div className="flex items-center justify-between mb-2">
                <span style={{ color: 'var(--text-tertiary)' }}>Status</span>
                <span
                  style={{
                    color:
                      run.status === 'DONE' || run.status === 'COMPLETED'
                        ? 'var(--color-success)'
                        : run.status === 'FAILED'
                          ? 'var(--color-danger)'
                          : run.status === 'ACTIVE' || run.status === 'RUNNING'
                            ? 'var(--color-cyan-accent)'
                            : 'var(--text-secondary)',
                    fontWeight: 600,
                  }}
                >
                  {run.status}
                </span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span style={{ color: 'var(--text-tertiary)' }}>Current Phase</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                  {run.current_phase || '—'}
                </span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span style={{ color: 'var(--text-tertiary)' }}>Cost</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                  ${run.total_cost_usd.toFixed(4)}
                </span>
              </div>
              {run.budget_limit_usd != null && (
                <div className="flex items-center justify-between">
                  <span style={{ color: 'var(--text-tertiary)' }}>Budget Limit</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                    ${run.budget_limit_usd.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Evidence panel placeholder */}
          <div
            className="p-6"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
            }}
          >
            <h2
              className="label-uppercase mb-4"
              style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
            >
              EVIDENCE
            </h2>
            <p
              className="text-xs"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Evidence panel (Tests · API · Screenshots · Review) will be available in a future update.
            </p>
          </div>
        </div>
      </div>

      {/* All Phases List */}
      <div
        className="p-6"
        style={{
          backgroundColor: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
        }}
      >
        <h2
          className="label-uppercase mb-4"
          style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
        >
          ALL PHASES
        </h2>
        <div className="space-y-0">
          {run.phases.length === 0 && (
            <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>
              No phase data available yet.
            </p>
          )}
          {run.phases.map((phase, idx) => (
            <div
              key={phase.phase_name}
              className="flex items-center justify-between py-2.5"
              style={{
                borderBottom:
                  idx < run.phases.length - 1
                    ? `1px solid var(--border-subtle)`
                    : 'none',
              }}
            >
              <div className="flex items-center gap-3">
                <span
                  style={{
                    color: getPhaseSymbolColor(phase.status),
                    fontWeight: 700,
                    fontSize: 'var(--text-sm)',
                  }}
                >
                  {getPhaseSymbol(phase.status)}
                </span>
                <span
                  className="font-semibold uppercase"
                  style={{ fontSize: 'var(--text-sm)', letterSpacing: '0.075em' }}
                >
                  {phase.phase_name}
                </span>
                {phase.retry_count > 0 && (
                  <span
                    style={{
                      backgroundColor: 'var(--color-warning-light-hex)',
                      color: 'var(--color-warning)',
                      fontSize: 'var(--text-xs)',
                      padding: '1px 6px',
                    }}
                  >
                    RETRY &times;{phase.retry_count}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4" style={{ fontSize: 'var(--text-xs)' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>
                  {phase.started_at
                    ? new Date(phase.started_at).toLocaleTimeString()
                    : '—'}
                </span>
                <span
                  className="label-uppercase"
                  style={{
                    color: phase.status === 'PASSED' || phase.status === 'COMPLETED'
                      ? 'var(--color-success)'
                      : phase.status === 'ACTIVE' || phase.status === 'RUNNING'
                        ? 'var(--color-cyan-accent)'
                        : phase.status === 'FAILED'
                          ? 'var(--color-danger)'
                          : 'var(--text-tertiary)',
                    fontSize: '0.5625rem',
                  }}
                >
                  {phase.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
