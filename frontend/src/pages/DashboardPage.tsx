/**
 * Pencil Fidelity Audit — dashboard.pen (Blueprint Industrial) vs Implementation
 * ============================================================================
 * Last reviewed: 2026-06-21 against frontend/designs/dashboard.pen (S1 — Run List)
 *
 * ALIGNED:
 *   ✓ Blueprint grid background (horizontal + vertical grid lines at 40px intervals)
 *   ✓ Document header annotation ("AF-OS-001 · RUN SCHEDULE · REV 2.1")
 *   ✓ Bold horizontal rule separator (3px, primary color) after page title
 *   ✓ Stats row with dividers (ACTIVE RUNS, COMPLETED, FAILED, BOUNCED)
 *   ✓ Table column headers (STATUS, TICKET, PHASE, ACTIONS) with uppercase mono labels
 *   ✓ Status symbols (✓/●/✗/⬒/◌) and color coding (success/cyan/danger/warning/tertiary)
 *   ✓ Alternating row backgrounds (zebra stripe)
 *   ✓ "VIEW →" action links with cyan accent and mono font weight 600
 *   ✓ FIG annotation below table
 *   ✓ Footer with "AGENT FACTORY OSS · DEEPSEEK AI · 8 HARD GATES · ZERO HALLUCINATION CASCADE"
 *
 * GAPS (noted — no code changes required for MVP):
 *   △ Design uses IBM Plex Mono exclusively; implementation uses Fraunces (display) + Inter (body)
 *     via the Hallmark design system. This is intentional — the Hallmark type pair supersedes
 *     the pen file's mono-only palette. The pen was an early wireframe.
 *   △ Design includes a 240px sidebar nav (BlueprintNav) with RUNS/TICKETS/SETTINGS items.
 *     Implementation has Layout.tsx providing a header nav, not a sidebar. The dashboard page
 *     is embedded inside the layout; the sidebar lives in a separate component context.
 *   △ Design shows "DURATION" column in table; implementation shows "CREATED" (date).
 *     Duration tracking requires per-phase timing data not yet available in the MVP run list API.
 *   △ Design shows "AVG DURATION" as a 4th stat box (value "6m 12s"). Implementation has only
 *     4 stat boxes total (Active/Completed/Failed/Bounced) — no average metric yet.
 *   △ Design shows edge marks (vertical tick lines on left gutter at specific Y positions).
 *     Implementation has a continuous vertical line instead of discrete ticks.
 *   △ Design positions "NEW RUN" button at bottom-right (x=1100, y=540). Implementation puts
 *     it in the table header bar for better UX on variable viewport widths.
 *   △ Design uses explicit pixel coordinates (Blueprint layout: 1440×900 canvas). Implementation
 *     is responsive and uses CSS flexbox/grid — exact pixel positions are not feasible.
 *   △ Design shows phase as "PHASE 3/8 · SPEC" with progress fraction. Implementation shows
 *     "PHASE · SPEC" without the fraction (fraction data not in current run list API).
 *   △ Design uses hardcoded color values (#4A9FD8 accent, #E8EEF4 sidebar, #C8D6E5 borders).
 *     Implementation uses CSS custom properties from tokens.css for theme consistency.
 *   △ Design corner markers (TR corner at x=1340, y=580) are missing from current implementation.
 *
 * RESOLVED:
 *   - The "NEW RUN" button placement difference is a deliberate UX improvement for scrolling.
 *   - Font family divergence is by design (Hallmark overrides early pen wireframes).
 *   - Grid line stroke widths and colors are a close approximation (0.5px #D4E0EC → subtler CSS).
 */
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
