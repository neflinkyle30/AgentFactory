import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import type { RunListItem } from '../hooks/useRuns';

function getStatusSymbol(status: string): string {
  switch (status.toUpperCase()) {
    case 'DONE':
    case 'COMPLETED':
    case 'PASSED':
      return '✓';
    case 'ACTIVE':
    case 'RUNNING':
    case 'IN_PROGRESS':
      return '●';
    case 'FAILED':
      return '✗';
    case 'BOUNCED':
      return '⬒';
    default:
      return '◌';
  }
}

function getStatusColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'DONE':
    case 'COMPLETED':
    case 'PASSED':
      return 'var(--color-success)';
    case 'ACTIVE':
    case 'RUNNING':
    case 'IN_PROGRESS':
      return 'var(--color-cyan-accent)';
    case 'FAILED':
      return 'var(--color-danger)';
    case 'BOUNCED':
      return 'var(--color-warning)';
    default:
      return 'var(--text-tertiary)';
  }
}

function getStatusLabel(status: string): string {
  switch (status.toUpperCase()) {
    case 'DONE':
    case 'COMPLETED':
      return 'DONE';
    case 'ACTIVE':
    case 'RUNNING':
    case 'IN_PROGRESS':
      return 'ACTIVE';
    case 'FAILED':
      return 'FAILED';
    case 'BOUNCED':
      return 'BOUNCED';
    default:
      return 'QUEUED';
  }
}

function calcStats(runs: RunListItem[]) {
  const active = runs.filter((r) =>
    ['ACTIVE', 'RUNNING', 'IN_PROGRESS'].includes(r.status.toUpperCase()),
  ).length;
  const completed = runs.filter((r) =>
    ['DONE', 'COMPLETED', 'PASSED'].includes(r.status.toUpperCase()),
  ).length;
  const failed = runs.filter((r) =>
    r.status.toUpperCase() === 'FAILED',
  ).length;
  const bounced = runs.filter((r) =>
    r.status.toUpperCase() === 'BOUNCED',
  ).length;

  return { active, completed, failed, bounced, total: runs.length };
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function DashboardPage() {
  const { data, isLoading, isError } = useRuns({ limit: 50 });
  const runs = data?.runs ?? [];
  const stats = calcStats(runs);

  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="blueprint-bg" style={{ margin: '-2rem -2rem 0 -2rem', padding: '2rem' }}>
      {/* Document header */}
      <div className="mb-1">
        <p
          className="tech-annotation"
          style={{ fontSize: '0.625rem', letterSpacing: '0.15em', color: 'var(--text-tertiary)' }}
        >
          AF-OS-001 &middot; RUN SCHEDULE &middot; REV 2.1
        </p>
      </div>

      {/* Page title */}
      <h1
        className="heading-display mb-6"
        style={{ fontSize: 'var(--text-4xl)', letterSpacing: '-0.01em' }}
      >
        Pipeline Run Schedule
      </h1>

      {/* Bold horizontal rule */}
      <hr
        className="mb-8"
        style={{ border: 'none', height: '3px', backgroundColor: 'var(--color-primary)' }}
      />

      {/* Stats row */}
      <div
        className="flex gap-0 mb-8"
        style={{
          border: '1px solid var(--border-default)',
          backgroundColor: 'var(--bg-elevated)',
        }}
      >
        <StatBox label="ACTIVE RUNS" value={stats.active} color="var(--color-cyan-accent)" />
        <StatDivider />
        <StatBox label="COMPLETED" value={stats.completed} color="var(--color-success)" />
        <StatDivider />
        <StatBox label="FAILED" value={stats.failed} color="var(--color-danger)" />
        <StatDivider />
        <StatBox label="BOUNCED" value={stats.bounced} color="var(--color-warning)" />
      </div>

      {/* Table section */}
      <div className="flex gap-0">
        {/* Left edge mark column */}
        <div
          className="flex-shrink-0 flex flex-col items-center pt-0"
          style={{ width: 20 }}
        >
          <div
            style={{
              width: 2,
              flex: 1,
              backgroundColor: 'var(--color-cyan-accent)',
              opacity: 0.6,
            }}
          />
        </div>

        {/* Table content */}
        <div className="flex-1 min-w-0">
          {/* Table header bar */}
          <div
            className="flex items-center justify-between mb-0 px-6 py-3"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderBottom: '1px solid var(--border-default)',
            }}
          >
            <span
              className="label-uppercase"
              style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
            >
              RUNS
            </span>
            <Link to="/new" className="btn-primary text-xs py-1.5 px-4">
              NEW RUN
            </Link>
          </div>

          {/* Column headers */}
          <div
            className="grid px-6 py-2"
            style={{
              gridTemplateColumns: '100px 1fr 180px 120px 100px',
              backgroundColor: 'var(--bg-elevated)',
              borderLeft: '1px solid var(--border-default)',
              borderRight: '1px solid var(--border-default)',
              borderBottom: '1px solid var(--border-strong)',
            }}
          >
            <span className="label-uppercase">STATUS</span>
            <span className="label-uppercase">TICKET</span>
            <span className="label-uppercase">PHASE</span>
            <span className="label-uppercase">CREATED</span>
            <span className="label-uppercase text-right">ACTIONS</span>
          </div>

          {/* Loading state */}
          {isLoading && (
            <div
              className="px-6 py-8 text-center"
              style={{
                backgroundColor: 'var(--bg-elevated)',
                borderLeft: '1px solid var(--border-default)',
                borderRight: '1px solid var(--border-default)',
                borderBottom: '1px solid var(--border-default)',
              }}
            >
              <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>
                Loading runs…
              </p>
            </div>
          )}

          {/* Error state */}
          {isError && (
            <div
              className="px-6 py-8 text-center"
              style={{
                backgroundColor: 'var(--color-danger-light-hex)',
                borderLeft: '1px solid var(--border-default)',
                borderRight: '1px solid var(--border-default)',
                borderBottom: '1px solid var(--border-default)',
              }}
            >
              <p style={{ color: 'var(--color-danger-hex)', fontSize: 'var(--text-sm)' }}>
                Failed to load runs. Please try again.
              </p>
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !isError && runs.length === 0 && (
            <div
              className="px-6 py-12 text-center"
              style={{
                backgroundColor: 'var(--bg-elevated)',
                borderLeft: '1px solid var(--border-default)',
                borderRight: '1px solid var(--border-default)',
                borderBottom: '1px solid var(--border-default)',
              }}
            >
              <p
                className="mb-4"
                style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}
              >
                No runs yet. Submit a ticket to start your first pipeline run.
              </p>
              <Link to="/new" className="btn-primary text-xs py-2 px-6">
                CREATE FIRST RUN
              </Link>
            </div>
          )}

          {/* Table rows */}
          {runs.map((run, idx) => (
            <div
              key={run.id}
              className="grid px-6 py-3 items-center"
              style={{
                gridTemplateColumns: '100px 1fr 180px 120px 100px',
                backgroundColor: idx % 2 === 0 ? 'var(--bg-elevated)' : 'transparent',
                borderLeft: '1px solid var(--border-default)',
                borderRight: '1px solid var(--border-default)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              {/* Status */}
              <div className="flex items-center gap-2">
                <span style={{ color: getStatusColor(run.status), fontWeight: 700 }}>
                  {getStatusSymbol(run.status)}
                </span>
                <span
                  className="label-uppercase"
                  style={{
                    color: getStatusColor(run.status),
                    fontSize: '0.5625rem',
                  }}
                >
                  {getStatusLabel(run.status)}
                </span>
              </div>

              {/* Ticket */}
              <span
                className="truncate"
                style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}
              >
                {run.ticket_ref || `Run #${run.id.slice(0, 8)}`}
              </span>

              {/* Phase */}
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                {run.current_phase
                  ? `PHASE · ${run.current_phase}`
                  : '—'}
              </span>

              {/* Created */}
              <span
                className="text-xs"
                style={{ color: 'var(--text-tertiary)', fontSize: '0.6875rem' }}
              >
                {formatDate(run.created_at)}
              </span>

              {/* Actions */}
              <div className="text-right">
                <Link
                  to={`/runs/${run.id}`}
                  className="text-xs"
                  style={{
                    color: 'var(--color-cyan-accent)',
                    fontWeight: 600,
                    letterSpacing: '0.05em',
                  }}
                >
                  VIEW &rarr;
                </Link>
              </div>
            </div>
          ))}

          {/* Table bottom border */}
          <div
            style={{
              height: '1px',
              backgroundColor: 'var(--border-default)',
            }}
          />
        </div>

        {/* Right edge mark column */}
        <div
          className="flex-shrink-0 flex flex-col items-center pt-0"
          style={{ width: 20 }}
        >
          <div
            style={{
              width: 2,
              flex: 1,
              backgroundColor: 'var(--color-cyan-accent)',
              opacity: 0.6,
            }}
          />
        </div>
      </div>

      {/* FIG annotation */}
      <p
        className="tech-annotation mt-3 mb-8"
        style={{
          fontSize: '0.5625rem',
          color: 'var(--text-tertiary)',
          fontStyle: 'italic',
        }}
      >
        FIG 1.1 &mdash; Active pipeline runs as of {today}
      </p>

      {/* Footer */}
      <div
        className="pt-8 mt-8"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <p
          className="tech-annotation text-center"
          style={{ fontSize: '0.5625rem', color: 'var(--text-tertiary)', letterSpacing: '0.1em' }}
        >
          AGENT FACTORY OSS &middot; DEEPSEEK AI &middot; 8 HARD GATES &middot; ZERO HALLUCINATION CASCADE
        </p>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex-1 px-6 py-5 text-center">
      <p
        className="heading-display mb-1"
        style={{ fontSize: 'var(--text-3xl)', color }}
      >
        {value}
      </p>
      <p className="label-uppercase" style={{ fontSize: '0.5625rem' }}>
        {label}
      </p>
    </div>
  );
}

function StatDivider() {
  return (
    <div
      className="flex-shrink-0"
      style={{
        width: 1,
        backgroundColor: 'var(--border-subtle)',
      }}
    />
  );
}
