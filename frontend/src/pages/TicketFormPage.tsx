import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSubmitRun } from '../hooks/useRuns';
import type { AcceptanceCriterion } from '../hooks/useRuns';

interface ACRow {
  id: string;
  given: string;
  when: string;
  then: string;
}

const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'] as const;

let acIdCounter = 0;
function nextAcId(): string {
  acIdCounter += 1;
  return `ac-${acIdCounter}`;
}

function emptyAcRow(): ACRow {
  return { id: nextAcId(), given: '', when: '', then: '' };
}

export default function TicketFormPage() {
  const navigate = useNavigate();
  const submitRun = useSubmitRun();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [acRows, setAcRows] = useState<ACRow[]>([emptyAcRow()]);
  const [priority, setPriority] = useState<string>('Medium');
  const [components, setComponents] = useState('');
  const [error, setError] = useState<string | null>(null);

  const addAcRow = () => {
    setAcRows((prev) => [...prev, emptyAcRow()]);
  };

  const removeAcRow = (id: string) => {
    if (acRows.length <= 1) return;
    setAcRows((prev) => prev.filter((r) => r.id !== id));
  };

  const updateAcRow = (id: string, field: keyof Omit<ACRow, 'id'>, value: string) => {
    setAcRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)),
    );
  };

  const handleAcKeyDown = (e: KeyboardEvent<HTMLInputElement>, rowId: string, field: keyof Omit<ACRow, 'id'>) => {
    // Tab from 'then' field → auto-add new row
    if (e.key === 'Tab' && field === 'then' && !e.shiftKey) {
      const rowIndex = acRows.findIndex((r) => r.id === rowId);
      const row = acRows[rowIndex];
      if (row && row.given.trim() && row.when.trim() && row.then.trim() && rowIndex === acRows.length - 1) {
        e.preventDefault();
        addAcRow();
      }
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate title
    if (!title.trim()) {
      setError('Title is required.');
      return;
    }

    // Validate at least one complete AC row
    const completeAcs = acRows.filter(
      (r) => r.given.trim() && r.when.trim() && r.then.trim(),
    );

    if (completeAcs.length === 0) {
      setError('At least one complete acceptance criterion is required. Each row needs Given, When, and Then.');
      return;
    }

    // Check for incomplete rows (partial fill)
    const partialRows = acRows.filter((r) => {
      const fields = [r.given.trim(), r.when.trim(), r.then.trim()];
      const filled = fields.filter(Boolean).length;
      return filled > 0 && filled < 3;
    });

    if (partialRows.length > 0) {
      setError('Each acceptance criterion row must have all three fields (Given, When, Then) filled. Complete or remove incomplete rows.');
      return;
    }

    const acceptanceCriteria: AcceptanceCriterion[] = completeAcs.map((r) => ({
      given: r.given.trim(),
      when: r.when.trim(),
      then: r.then.trim(),
    }));

    const componentsList = components
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);

    try {
      const result = await submitRun.mutateAsync({
        title: title.trim(),
        description: description.trim() || undefined,
        acceptance_criteria: acceptanceCriteria,
        priority,
        components: componentsList.length > 0 ? componentsList : undefined,
      });

      navigate(`/runs/${result.run_id}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to submit ticket. Please try again.';
      setError(message);
    }
  };

  return (
    <div>
      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h1 className="heading-display" style={{ fontSize: 'var(--text-4xl)' }}>
            New Ticket
          </h1>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="btn-secondary text-xs"
          >
            &larr; BACK TO SCHEDULE
          </button>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
          Submit a new pipeline run. Fill in the ticket details below.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div
          className="px-4 py-3 mb-6 text-sm"
          style={{
            backgroundColor: 'var(--color-danger-light-hex)',
            color: 'var(--color-danger-hex)',
            border: '1px solid var(--color-danger-hex)',
          }}
        >
          {error}
        </div>
      )}

      {/* API error from mutation */}
      {submitRun.isError && submitRun.error && !error && (
        <div
          className="px-4 py-3 mb-6 text-sm"
          style={{
            backgroundColor: 'var(--color-danger-light-hex)',
            color: 'var(--color-danger-hex)',
            border: '1px solid var(--color-danger-hex)',
          }}
        >
          {submitRun.error instanceof Error ? submitRun.error.message : 'Submission failed.'}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Title */}
        <div>
          <label className="label-uppercase block mb-1">Title *</label>
          <input
            className="input-field"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Add user authentication with JWT"
            autoFocus
            disabled={submitRun.isPending}
          />
        </div>

        {/* Description */}
        <div>
          <label className="label-uppercase block mb-1">Description</label>
          <textarea
            className="input-field"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what this change accomplishes and why..."
            rows={4}
            style={{ resize: 'vertical' }}
            disabled={submitRun.isPending}
          />
        </div>

        {/* Acceptance Criteria */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label-uppercase">Acceptance Criteria *</label>
            <button
              type="button"
              onClick={addAcRow}
              className="btn-secondary text-xs py-1 px-3"
              disabled={submitRun.isPending}
            >
              + ADD CRITERION
            </button>
          </div>

          <div className="space-y-3">
            {/* Column headers */}
            <div
              className="grid gap-2 px-1"
              style={{ gridTemplateColumns: '1fr 1fr 1fr auto' }}
            >
              <span className="label-uppercase">Given</span>
              <span className="label-uppercase">When</span>
              <span className="label-uppercase">Then</span>
              <span className="w-8" />
            </div>

            {acRows.map((row) => (
              <div
                key={row.id}
                className="grid gap-2"
                style={{ gridTemplateColumns: '1fr 1fr 1fr auto' }}
              >
                <input
                  className="input-field"
                  type="text"
                  value={row.given}
                  onChange={(e) => updateAcRow(row.id, 'given', e.target.value)}
                  onKeyDown={(e) => handleAcKeyDown(e, row.id, 'given')}
                  placeholder={`e.g. a user is on the login page`}
                  disabled={submitRun.isPending}
                />
                <input
                  className="input-field"
                  type="text"
                  value={row.when}
                  onChange={(e) => updateAcRow(row.id, 'when', e.target.value)}
                  onKeyDown={(e) => handleAcKeyDown(e, row.id, 'when')}
                  placeholder={`e.g. they enter valid credentials`}
                  disabled={submitRun.isPending}
                />
                <input
                  className="input-field"
                  type="text"
                  value={row.then}
                  onChange={(e) => updateAcRow(row.id, 'then', e.target.value)}
                  onKeyDown={(e) => handleAcKeyDown(e, row.id, 'then')}
                  placeholder={`e.g. they are redirected to the dashboard`}
                  disabled={submitRun.isPending}
                />
                <button
                  type="button"
                  onClick={() => removeAcRow(row.id)}
                  className="btn-ghost text-xs px-2"
                  title="Remove row"
                  disabled={submitRun.isPending || acRows.length <= 1}
                  style={{
                    color: acRows.length <= 1 ? 'var(--text-tertiary)' : 'var(--text-secondary)',
                    opacity: acRows.length <= 1 ? 0.4 : 1,
                    cursor: acRows.length <= 1 ? 'default' : 'pointer',
                  }}
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Priority */}
        <div>
          <label className="label-uppercase block mb-1">Priority</label>
          <select
            className="input-field"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            disabled={submitRun.isPending}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Components */}
        <div>
          <label className="label-uppercase block mb-1">Components</label>
          <input
            className="input-field"
            type="text"
            value={components}
            onChange={(e) => setComponents(e.target.value)}
            placeholder="frontend, auth, api"
            disabled={submitRun.isPending}
          />
          <p className="mt-1" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
            Comma-separated list of affected components
          </p>
        </div>

        {/* Divider */}
        <hr
          className="border-0"
          style={{ height: '1px', backgroundColor: 'var(--border-default)' }}
        />

        {/* Submit */}
        <button
          type="submit"
          className="btn-primary w-full py-3 text-base"
          disabled={submitRun.isPending}
        >
          {submitRun.isPending ? 'SUBMITTING…' : 'SUBMIT TICKET'}
        </button>
      </form>
    </div>
  );
}
