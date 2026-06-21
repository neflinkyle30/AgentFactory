import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState(''); // team name
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Email and password are required.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      await register(email.trim(), password, name.trim() || undefined);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Registration failed. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ backgroundColor: 'var(--bg-surface)' }}
    >
      <div
        className="w-full max-w-md p-8"
        style={{
          backgroundColor: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-lg)',
        }}
      >
        {/* Header */}
        <h1 className="heading-display text-3xl mb-2">Create Account</h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
          Set up your Agent Factory workspace
        </p>

        {/* Error */}
        {error && (
          <div
            className="px-4 py-3 rounded-md mb-6 text-sm"
            style={{
              backgroundColor: 'var(--color-danger-light-hex)',
              color: 'var(--color-danger-hex)',
              border: '1px solid var(--color-danger-hex)',
            }}
          >
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Team name */}
          <div>
            <label className="label-uppercase block mb-1">Team Name</label>
            <input
              className="input-field"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Team (optional)"
              disabled={isSubmitting}
            />
          </div>

          {/* Email */}
          <div>
            <label className="label-uppercase block mb-1">Email</label>
            <input
              className="input-field"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
              disabled={isSubmitting}
            />
          </div>

          {/* Password */}
          <div>
            <label className="label-uppercase block mb-1">Password</label>
            <input
              className="input-field"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              autoComplete="new-password"
              disabled={isSubmitting}
            />
          </div>

          {/* Confirm Password */}
          <div>
            <label className="label-uppercase block mb-1">Confirm Password</label>
            <input
              className="input-field"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repeat your password"
              autoComplete="new-password"
              disabled={isSubmitting}
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="btn-primary w-full py-3 text-base"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        {/* Footer */}
        <p className="mt-6 text-sm text-center" style={{ color: 'var(--text-secondary)' }}>
          Already have an account?{' '}
          <Link
            to="/login"
            style={{ color: 'var(--text-link)', fontWeight: 500 }}
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
