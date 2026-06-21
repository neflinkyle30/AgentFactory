import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Email and password are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Login failed. Please check your credentials.';
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
        <h1
          className="heading-display text-3xl mb-2"
          style={{ textAlign: 'left' }}
        >
          Agent Factory
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
          Sign in to manage your pipeline runs
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
              placeholder="Your password"
              autoComplete="current-password"
              disabled={isSubmitting}
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="btn-primary w-full py-3 text-base"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {/* Footer */}
        <p className="mt-6 text-sm text-center" style={{ color: 'var(--text-secondary)' }}>
          Don&apos;t have an account?{' '}
          <Link
            to="/register"
            style={{ color: 'var(--text-link)', fontWeight: 500 }}
          >
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
