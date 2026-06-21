/** PRSummaryCard — shows PR title, body preview, branch name, and HITL approve button.
 *
 * Visible when phase is PR_READY or PR_OPENED.
 * Blueprint Industrial: black card, monospace, sharp.
 */
import { useApproveRun } from '../hooks/useRuns';
import type { PhaseStatus } from '../hooks/useRuns';

interface PRSummaryCardProps {
  runId: string;
  phases: PhaseStatus[];
  hitlEnabled: boolean;
  currentStatus: string;
}

function extractPRData(phases: PhaseStatus[]) {
  const prPhase = phases.find((p) => p.phase_name === 'PR');
  const prOutput = (prPhase?.output ?? {}) as Record<string, unknown>;

  return {
    prTitle: (prOutput.pr_title as string) ?? '',
    prBody: (prOutput.pr_body as string) ?? '',
    branchName: (prOutput.branch_name as string) ?? '',
    commitMessage: (prOutput.commit_message as string) ?? '',
  };
}

export function PRSummaryCard({
  runId,
  phases,
  hitlEnabled,
  currentStatus,
}: PRSummaryCardProps) {
  const prData = extractPRData(phases);
  const approve = useApproveRun();

  const isAwaitingHITL = currentStatus === 'AWAITING_HITL';
  const isPROpened = currentStatus === 'PR_OPENED';
  const showCard = isAwaitingHITL || isPROpened;

  if (!showCard) return null;

  const statusLabel = isAwaitingHITL ? 'AWAITING APPROVAL' : 'PR OPENED';
  const statusColor = isAwaitingHITL ? 'var(--color-warning)' : 'var(--color-success)';

  return (
    <div
      className="mb-6 p-6"
      style={{
        backgroundColor: 'var(--bg-elevated)',
        border: '1px solid var(--border-default)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2
          className="label-uppercase"
          style={{ fontSize: 'var(--text-xs)', letterSpacing: '0.125em' }}
        >
          PR SUMMARY
        </h2>
        <span
          className="label-uppercase"
          style={{
            fontSize: '0.5rem',
            color: statusColor,
            fontWeight: 700,
          }}
        >
          {statusLabel}
        </span>
      </div>

      {/* PR Title */}
      <div className="mb-3">
        <div
          className="label-uppercase mb-1"
          style={{ fontSize: '0.5rem', color: 'var(--text-tertiary)' }}
        >
          TITLE
        </div>
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            color: 'var(--text-primary)',
            margin: 0,
            wordBreak: 'break-word',
          }}
        >
          {prData.prTitle || '—'}
        </p>
      </div>

      {/* Branch name */}
      <div className="mb-3">
        <div
          className="label-uppercase mb-1"
          style={{ fontSize: '0.5rem', color: 'var(--text-tertiary)' }}
        >
          BRANCH
        </div>
        <code
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-cyan-accent)',
            backgroundColor: 'var(--bg-code)',
            padding: '1px 6px',
            wordBreak: 'break-all',
          }}
        >
          {prData.branchName || '—'}
        </code>
      </div>

      {/* Commit message */}
      <div className="mb-4">
        <div
          className="label-uppercase mb-1"
          style={{ fontSize: '0.5rem', color: 'var(--text-tertiary)' }}
        >
          COMMIT
        </div>
        <code
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            wordBreak: 'break-all',
          }}
        >
          {prData.commitMessage || '—'}
        </code>
      </div>

      {/* PR Body Preview */}
      {prData.prBody && (
        <div className="mb-4">
          <div
            className="label-uppercase mb-1"
            style={{ fontSize: '0.5rem', color: 'var(--text-tertiary)' }}
          >
            BODY PREVIEW
          </div>
          <div
            className="p-3 overflow-auto"
            style={{
              backgroundColor: 'var(--bg-code)',
              color: 'var(--text-code)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              lineHeight: 1.5,
              maxHeight: '200px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {prData.prBody.slice(0, 800)}
            {prData.prBody.length > 800 && '…'}
          </div>
        </div>
      )}

      {/* HITL Approve button */}
      {isAwaitingHITL && hitlEnabled && (
        <button
          onClick={() => approve.mutate(runId)}
          disabled={approve.isPending}
          className="btn-primary w-full"
          style={{
            backgroundColor: 'var(--color-success)',
            color: 'var(--text-inverse)',
          }}
        >
          {approve.isPending ? 'APPROVING…' : 'APPROVE & OPEN PR'}
        </button>
      )}

      {approve.isError && (
        <div
          className="mt-2 px-3 py-2 text-xs"
          style={{
            backgroundColor: 'var(--color-danger-light-hex)',
            color: 'var(--color-danger-hex)',
            border: '1px solid var(--color-danger-hex)',
          }}
        >
          {approve.error instanceof Error ? approve.error.message : 'Approval failed.'}
        </div>
      )}
    </div>
  );
}
