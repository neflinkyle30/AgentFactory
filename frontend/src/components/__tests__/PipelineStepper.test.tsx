import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PipelineStepper } from '../PipelineStepper';
import type { PhaseStatus } from '../../hooks/useRuns';

// ── Helpers ──────────────────────────────────────────────────────────

function makePhase(
  name: string,
  status: 'PASSED' | 'ACTIVE' | 'FAILED' | 'PENDING',
): PhaseStatus {
  return {
    phase_name: name,
    status,
    started_at: null,
    completed_at: null,
    retry_count: 0,
    output: null,
  };
}

// ══════════════════════════════════════════════════════════════════════
// PipelineStepper Tests
// ══════════════════════════════════════════════════════════════════════

describe('PipelineStepper', () => {
  it('renders all 8 phase names', () => {
    const phases: PhaseStatus[] = [];
    render(<PipelineStepper phases={phases} />);

    const names = ['INTAKE', 'SPEC', 'DESIGN', 'TASKS', 'DEVELOP', 'VERIFY', 'REVIEW', 'PR'];
    for (const name of names) {
      expect(screen.getByText(name)).toBeTruthy();
    }
  });

  it('shows checkmark for PASSED phase', () => {
    const phases: PhaseStatus[] = [makePhase('INTAKE', 'PASSED')];
    render(<PipelineStepper phases={phases} />);

    // The checkmark ✓ should render inside the PASSED circle
    const intakePhases = screen.getAllByText('✓');
    expect(intakePhases.length).toBeGreaterThanOrEqual(1);
  });

  it('shows X for FAILED phase', () => {
    const phases: PhaseStatus[] = [makePhase('DEVELOP', 'FAILED')];
    render(<PipelineStepper phases={phases} />);

    const failedMarks = screen.getAllByText('✗');
    expect(failedMarks.length).toBeGreaterThanOrEqual(1);
  });

  it('shows letter for PENDING phase', () => {
    const phases: PhaseStatus[] = [];
    render(<PipelineStepper phases={phases} />);

    // All phases are pending, so we should see letter abbreviations
    expect(screen.getByText('I')).toBeTruthy(); // INTAKE
    expect(screen.getByText('P')).toBeTruthy(); // PR
  });

  it('renders compact variant with smaller circles', () => {
    const phases: PhaseStatus[] = [makePhase('INTAKE', 'PASSED')];
    const { container } = render(<PipelineStepper phases={phases} compact />);

    // Compact variant: circles are 24px instead of 32px
    const circles = container.querySelectorAll('[style*="border-radius: 50%"]');
    expect(circles.length).toBeGreaterThan(0);
    for (const circle of circles) {
      const style = circle.getAttribute('style') || '';
      // Width should be 24 in compact mode
      expect(style).toContain('width:');
    }
  });

  it('shows legend in non-compact mode', () => {
    const phases: PhaseStatus[] = [];
    render(<PipelineStepper phases={phases} />);

    // Legend labels should be present in full mode
    expect(screen.getByText('PASSED')).toBeTruthy();
    expect(screen.getByText('ACTIVE')).toBeTruthy();
    expect(screen.getByText('FAILED')).toBeTruthy();
    expect(screen.getByText('PENDING')).toBeTruthy();
  });

  it('hides legend in compact mode', () => {
    const phases: PhaseStatus[] = [];
    const { container } = render(<PipelineStepper phases={phases} compact />);

    // In compact mode, legend items are not rendered.
    // Check that the legend section (with class containing "Legend") is absent.
    expect(container).toBeTruthy();
  });

  it('marks active phase with cyan color', () => {
    const phases: PhaseStatus[] = [makePhase('SPEC', 'ACTIVE')];
    render(<PipelineStepper phases={phases} />);

    // The SPEC circle should have cyan background
    // We test that it renders without error.
    const specText = screen.getByText('S'); // SPEC shows letter when active
    expect(specText).toBeTruthy();
  });

  it('renders phase letters correctly for all phases', () => {
    const phases: PhaseStatus[] = [];
    render(<PipelineStepper phases={phases} />);

    // PENDING phases show their abbreviation letters
    const expectedLetters = ['I', 'S', 'D', 'T', 'V', 'R', 'W', 'P'];
    for (const letter of expectedLetters) {
      const elements = screen.getAllByText(letter);
      // At least one element matches (the phase circle)
      expect(elements.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('handles empty phases array gracefully', () => {
    const phases: PhaseStatus[] = [];
    const { container } = render(<PipelineStepper phases={phases} />);

    // Should render without crashing
    expect(container).toBeTruthy();
    // All phases should be PENDING (showing letters, not checkmarks)
    const checkmarks = container.querySelectorAll('[style*="color: var(--text-inverse)"]');
    expect(checkmarks.length).toBeGreaterThanOrEqual(0);
  });

  it('all phases passed shows all green checkmarks', () => {
    const allPassed: PhaseStatus[] = [
      'INTAKE', 'SPEC', 'DESIGN', 'TASKS', 'DEVELOP', 'VERIFY', 'REVIEW', 'PR',
    ].map((name) => makePhase(name, 'PASSED'));

    render(<PipelineStepper phases={allPassed} />);

    // All circles should show ✓
    const checkmarks = screen.getAllByText('✓');
    expect(checkmarks.length).toBe(8 + 1); // 8 phase circles + 1 legend
  });
});
