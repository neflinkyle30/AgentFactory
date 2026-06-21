/** BudgetTracker — shows token usage and cost with progress bar.
 *
 * Blueprint Industrial: IBM Plex Mono, sharp, no shadows.
 * Positioned in RunDetailPage sidebar.
 */
interface BudgetTrackerProps {
  totalCostUsd: number;
  budgetLimitUsd: number | null;
}

export function BudgetTracker({ totalCostUsd, budgetLimitUsd }: BudgetTrackerProps) {
  const hasLimit = budgetLimitUsd != null && budgetLimitUsd > 0;
  const pct = hasLimit ? Math.min((totalCostUsd / budgetLimitUsd!) * 100, 100) : 0;
  const overBudget = hasLimit && totalCostUsd > budgetLimitUsd!;
  const nearBudget = hasLimit && !overBudget && pct >= 80;

  const barColor = overBudget
    ? 'var(--color-danger)'
    : nearBudget
      ? 'var(--color-warning)'
      : 'var(--color-success)';

  return (
    <div
      className="p-6 mb-6"
      style={{
        backgroundColor: 'var(--bg-elevated)',
        border: '1px solid var(--border-default)',
      }}
    >
      <h2
        className="label-uppercase mb-4"
        style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
      >
        BUDGET
      </h2>

      {/* Cost display */}
      <div className="flex items-center justify-between mb-2">
        <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>
          COST
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: overBudget ? 'var(--color-danger)' : 'var(--text-primary)',
          }}
        >
          ${totalCostUsd.toFixed(4)}
        </span>
      </div>

      {hasLimit && (
        <>
          <div className="flex items-center justify-between mb-3">
            <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>
              LIMIT
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-sm)',
                color: 'var(--text-primary)',
              }}
            >
              ${budgetLimitUsd.toFixed(2)}
            </span>
          </div>

          {/* Progress bar */}
          <div
            style={{
              height: '6px',
              backgroundColor: 'var(--border-subtle)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${pct}%`,
                backgroundColor: barColor,
                transition: 'width var(--duration-slow) var(--ease-out-expo)',
              }}
            />
          </div>

          {/* Percentage */}
          <div className="flex justify-between mt-1">
            <span
              className="label-uppercase"
              style={{
                fontSize: '0.5rem',
                color: barColor,
                fontWeight: 700,
              }}
            >
              {pct.toFixed(1)}%
            </span>
            {overBudget && (
              <span
                className="label-uppercase"
                style={{
                  fontSize: '0.5rem',
                  color: 'var(--color-danger)',
                  fontWeight: 700,
                }}
              >
                OVER BUDGET
              </span>
            )}
            {nearBudget && !overBudget && (
              <span
                className="label-uppercase"
                style={{
                  fontSize: '0.5rem',
                  color: 'var(--color-warning)',
                  fontWeight: 700,
                }}
              >
                NEAR LIMIT
              </span>
            )}
          </div>
        </>
      )}

      {!hasLimit && (
        <p className="text-xs m-0" style={{ color: 'var(--text-tertiary)' }}>
          No budget limit set.
        </p>
      )}
    </div>
  );
}
