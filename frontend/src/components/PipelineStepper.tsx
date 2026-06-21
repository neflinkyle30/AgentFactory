import type { PhaseStatus } from '../hooks/useRuns';

interface PipelineStepperProps {
  phases: PhaseStatus[];
  /** Use compact variant (smaller circles, narrower spacing) */
  compact?: boolean;
}

const PHASE_NAMES = [
  'INTAKE',
  'SPEC',
  'DESIGN',
  'TASKS',
  'DEVELOP',
  'VERIFY',
  'REVIEW',
  'PR',
] as const;

const PHASE_LETTERS: Record<string, string> = {
  INTAKE: 'I',
  SPEC: 'S',
  DESIGN: 'D',
  TASKS: 'T',
  DEVELOP: 'V',
  VERIFY: 'R',
  REVIEW: 'W',
  PR: 'P',
};

function getPhaseState(phases: PhaseStatus[], phaseName: string): 'PASSED' | 'ACTIVE' | 'FAILED' | 'PENDING' {
  const phase = phases.find((p) => p.phase_name === phaseName);
  if (!phase) return 'PENDING';
  const s = phase.status.toUpperCase();
  if (s === 'PASSED' || s === 'COMPLETED') return 'PASSED';
  if (s === 'ACTIVE' || s === 'RUNNING' || s === 'IN_PROGRESS') return 'ACTIVE';
  if (s === 'FAILED') return 'FAILED';
  return 'PENDING';
}

function PhaseCircle({
  state,
  phaseName,
  compact,
}: {
  state: 'PASSED' | 'ACTIVE' | 'FAILED' | 'PENDING';
  phaseName: string;
  compact: boolean;
}) {
  const size = compact ? 24 : 32;
  const letter = PHASE_LETTERS[phaseName] || phaseName[0];

  const bgColor = {
    PASSED: 'var(--color-success)',
    ACTIVE: 'var(--color-cyan-accent)',
    FAILED: 'var(--color-danger)',
    PENDING: 'var(--bg-elevated)',
  }[state];

  const borderColor = {
    PASSED: 'var(--color-success)',
    ACTIVE: 'var(--color-cyan-accent)',
    FAILED: 'var(--color-danger)',
    PENDING: 'var(--border-default)',
  }[state];

  const textColor = {
    PASSED: 'var(--text-inverse)',
    ACTIVE: 'var(--text-inverse)',
    FAILED: 'var(--text-inverse)',
    PENDING: 'var(--text-tertiary)',
  }[state];

  return (
    <div
      className="flex items-center justify-center flex-shrink-0"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: bgColor,
        border: `2px solid ${borderColor}`,
        fontFamily: 'var(--font-mono)',
        fontSize: compact ? 'var(--text-xs)' : 'var(--text-sm)',
        fontWeight: 700,
        color: textColor,
        lineHeight: 1,
      }}
    >
      {state === 'PASSED' ? '✓' : state === 'FAILED' ? '✗' : letter}
    </div>
  );
}

function Connector({
  state,
  compact,
}: {
  state: 'PASSED' | 'PENDING';
  compact: boolean;
}) {
  return (
    <div
      className="flex-1 flex-shrink"
      style={{
        height: '2px',
        backgroundColor: state === 'PASSED' ? 'var(--color-success)' : 'var(--border-subtle)',
        marginTop: compact ? 12 : 16,
      }}
    />
  );
}

export function PipelineStepper({ phases, compact = false }: PipelineStepperProps) {
  const states = PHASE_NAMES.map((name) => getPhaseState(phases, name));

  return (
    <div
      style={{
        fontFamily: 'var(--font-mono)',
        padding: compact ? '8px 0' : '16px 0',
      }}
    >
      {/* Phase circles row */}
      <div className="flex items-start">
        {states.map((state, idx) => (
          <div key={PHASE_NAMES[idx]} className="flex items-start" style={{ flex: idx < states.length - 1 ? 1 : 'none' }}>
            <div
              className="flex flex-col items-center"
              style={{ minWidth: compact ? 40 : 56 }}
            >
              <PhaseCircle state={state} phaseName={PHASE_NAMES[idx]} compact={compact} />
              <span
                className="text-center mt-1 uppercase"
                style={{
                  fontSize: compact ? '0.5625rem' : 'var(--text-xs)',
                  color: state === 'PASSED'
                    ? 'var(--color-success)'
                    : state === 'ACTIVE'
                      ? 'var(--color-cyan-accent)'
                      : state === 'FAILED'
                        ? 'var(--color-danger)'
                        : 'var(--text-tertiary)',
                  fontWeight: state === 'ACTIVE' ? 600 : 400,
                  letterSpacing: '0.075em',
                  maxWidth: compact ? 40 : 56,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {PHASE_NAMES[idx]}
              </span>
            </div>
            {idx < states.length - 1 && (
              <Connector
                state={states[idx] === 'PASSED' ? 'PASSED' : 'PENDING'}
                compact={compact}
              />
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      {!compact && (
        <div
          className="flex items-center gap-6 mt-6 justify-center"
          style={{ fontSize: 'var(--text-xs)' }}
        >
          <LegendItem symbol="✓" label="PASSED" color="var(--color-success)" />
          <LegendItem symbol="●" label="ACTIVE" color="var(--color-cyan-accent)" />
          <LegendItem symbol="✗" label="FAILED" color="var(--color-danger)" />
          <LegendItem symbol="◌" label="PENDING" color="var(--text-tertiary)" />
        </div>
      )}
    </div>
  );
}

function LegendItem({ symbol, label, color }: { symbol: string; label: string; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span style={{ color, fontWeight: 700 }}>{symbol}</span>
      <span
        className="label-uppercase"
        style={{ fontSize: '0.5625rem' }}
      >
        {label}
      </span>
    </div>
  );
}
