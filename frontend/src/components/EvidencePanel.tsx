/** EvidencePanel — tabbed view for test results, API traces, screenshots, review findings.
 *
 * Blueprint Industrial: IBM Plex Mono, sharp tabs, 0px radius, CSS variables.
 */
import { useState } from 'react';
import type { PhaseStatus } from '../hooks/useRuns';

interface EvidencePanelProps {
  phases: PhaseStatus[];
}

type TabId = 'tests' | 'api' | 'screenshots' | 'review';

const TABS: { id: TabId; label: string }[] = [
  { id: 'tests', label: 'TESTS' },
  { id: 'api', label: 'API' },
  { id: 'screenshots', label: 'SCREENSHOTS' },
  { id: 'review', label: 'REVIEW' },
];

function extractEvidence(phases: PhaseStatus[]) {
  const verify = phases.find((p) => p.phase_name === 'VERIFY');
  const review = phases.find((p) => p.phase_name === 'REVIEW');

  const verifyOutput = (verify?.output ?? {}) as Record<string, unknown>;
  const reviewOutput = (review?.output ?? {}) as Record<string, unknown>;

  return {
    testResults: (verifyOutput.test_results as Array<Record<string, unknown>>) ?? [],
    apiTraces: (verifyOutput.api_traces as Array<Record<string, unknown>>) ?? [],
    screenshotPaths: (verifyOutput.screenshot_paths as string[]) ?? [],
    reviewFindings: (reviewOutput.findings as Array<Record<string, unknown>>) ?? [],
    reviewVerdict: (reviewOutput.verdict as string) ?? '—',
    reviewSummary: (reviewOutput.summary as string) ?? '',
  };
}

export function EvidencePanel({ phases }: EvidencePanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('tests');
  const evidence = extractEvidence(phases);

  const hasData = {
    tests: evidence.testResults.length > 0,
    api: evidence.apiTraces.length > 0,
    screenshots: evidence.screenshotPaths.length > 0,
    review: evidence.reviewFindings.length > 0,
  };

  return (
    <div>
      {/* Tab bar */}
      <div
        className="flex"
        style={{ borderBottom: '1px solid var(--border-default)' }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="label-uppercase px-3 py-2 text-xs border-0 bg-transparent cursor-pointer transition-colors"
            style={{
              fontSize: '0.5625rem',
              color:
                activeTab === tab.id
                  ? 'var(--color-cyan-accent)'
                  : 'var(--text-tertiary)',
              borderBottom:
                activeTab === tab.id
                  ? '2px solid var(--color-cyan-accent)'
                  : '2px solid transparent',
              marginBottom: '-1px',
              fontWeight: activeTab === tab.id ? 700 : 400,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.125em',
            }}
          >
            {tab.label}
            {hasData[tab.id] && (
              <span
                style={{
                  marginLeft: 4,
                  color: 'var(--color-success)',
                  fontSize: '0.5rem',
                }}
              >
                ●
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div
        className="p-4 overflow-auto"
        style={{
          maxHeight: '320px',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-sm)',
          lineHeight: 1.6,
        }}
      >
        {/* Tests tab */}
        {activeTab === 'tests' && (
          <div>
            {evidence.testResults.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)' }}>No test results yet.</p>
            ) : (
              <div className="space-y-2">
                {evidence.testResults.map((test, i) => (
                  <div
                    key={i}
                    className="p-2"
                    style={{
                      borderLeft: test.passed
                        ? '3px solid var(--color-success)'
                        : '3px solid var(--color-danger)',
                      backgroundColor: test.passed
                        ? 'var(--color-success-light-hex)'
                        : 'var(--color-danger-light-hex)',
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span
                        style={{
                          fontWeight: 600,
                          color: test.passed
                            ? 'var(--color-success)'
                            : 'var(--color-danger)',
                          fontSize: 'var(--text-xs)',
                        }}
                      >
                        {test.passed ? '✓' : '✗'} {test.test_name as string}
                      </span>
                      <span
                        className="label-uppercase"
                        style={{
                          fontSize: '0.5rem',
                          color: 'var(--text-tertiary)',
                        }}
                      >
                        AC #{test.ac_index as number}
                      </span>
                    </div>
                    {typeof test.output === 'string' && test.output.length > 0 && (
                      <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>
                        {test.output}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* API tab */}
        {activeTab === 'api' && (
          <div>
            {evidence.apiTraces.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)' }}>No API traces recorded.</p>
            ) : (
              <div className="space-y-2">
                {evidence.apiTraces.map((trace, i) => (
                  <pre
                    key={i}
                    className="p-2 text-xs"
                    style={{
                      backgroundColor: 'var(--bg-code)',
                      color: 'var(--text-code)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {JSON.stringify(trace, null, 2)}
                  </pre>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Screenshots tab */}
        {activeTab === 'screenshots' && (
          <div>
            {evidence.screenshotPaths.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)' }}>No screenshots captured.</p>
            ) : (
              <div className="space-y-1">
                {evidence.screenshotPaths.map((path, i) => (
                  <div
                    key={i}
                    className="text-xs"
                    style={{ color: 'var(--color-cyan-accent)' }}
                  >
                    {path}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Review tab */}
        {activeTab === 'review' && (
          <div>
            <div
              className="mb-2"
              style={{
                fontWeight: 700,
                color:
                  evidence.reviewVerdict === 'APPROVED'
                    ? 'var(--color-success)'
                    : evidence.reviewVerdict === 'APPROVED_WITH_SUGGESTIONS'
                      ? 'var(--color-warning)'
                      : evidence.reviewVerdict === 'REJECTED'
                        ? 'var(--color-danger)'
                        : 'var(--text-tertiary)',
                fontSize: 'var(--text-xs)',
                textTransform: 'uppercase',
                letterSpacing: '0.125em',
              }}
            >
              VERDICT: {evidence.reviewVerdict}
            </div>

            {evidence.reviewSummary && (
              <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
                {evidence.reviewSummary}
              </p>
            )}

            {evidence.reviewFindings.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)' }}>No review findings.</p>
            ) : (
              <div className="space-y-2">
                {evidence.reviewFindings.map((finding, i) => (
                  <div
                    key={i}
                    className="p-2"
                    style={{
                      borderLeft: `3px solid ${
                        finding.severity === 'CRITICAL'
                          ? 'var(--color-danger)'
                          : finding.severity === 'WARNING'
                            ? 'var(--color-warning)'
                            : 'var(--color-info)'
                      }`,
                    }}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span
                        className="label-uppercase"
                        style={{
                          fontSize: '0.5rem',
                          color:
                            finding.severity === 'CRITICAL'
                              ? 'var(--color-danger)'
                              : finding.severity === 'WARNING'
                                ? 'var(--color-warning)'
                                : 'var(--text-tertiary)',
                          fontWeight: 700,
                        }}
                      >
                        {finding.dimension as string} · {finding.severity as string}
                      </span>
                      <span style={{ fontSize: '0.5rem', color: 'var(--text-tertiary)' }}>
                        {finding.file as string}:{finding.line as number}
                      </span>
                    </div>
                    <p className="text-xs m-0" style={{ color: 'var(--text-primary)' }}>
                      {finding.description as string}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
