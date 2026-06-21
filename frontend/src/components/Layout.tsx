import { useState, useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const THEME_KEY = 'agent_factory_theme';

function useTheme() {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored) return stored === 'dark';
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
  }, [isDark]);

  return { isDark, toggle: () => setIsDark((prev) => !prev) };
}

/**
 * Main application shell: sidebar + content area.
 * Renders child routes via <Outlet />.
 */
export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const { isDark, toggle: toggleTheme } = useTheme();

  const navItems = [
    { label: 'Dashboard', path: '/' },
    { label: 'Runs', path: '/', activeOn: ['/', '/runs'] },
  ];

  const isActive = (item: (typeof navItems)[0]) => {
    if (item.activeOn) {
      return item.activeOn.some(
        (p) => location.pathname === p || location.pathname.startsWith(p + '/'),
      );
    }
    return location.pathname === item.path;
  };

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col w-[240px] flex-shrink-0 min-h-screen border-r"
        style={{
          backgroundColor: 'var(--bg-sidebar)',
          borderColor: 'var(--blueprint-grid)',
        }}
      >
        {/* Logo */}
        <div className="px-6 py-8">
          <Link
            to="/"
            className="heading-display text-sm tracking-[0.15em] uppercase"
            style={{ color: 'var(--text-primary)', letterSpacing: '0.15em' }}
          >
            Agent{'\n'}Factory
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-link ${isActive(item) ? 'active' : ''}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* User section */}
        <div
          className="px-6 py-4 border-t"
          style={{ borderColor: 'var(--blueprint-grid)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <p
              className="text-xs font-semibold tracking-wider uppercase"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {user?.email}
            </p>
            <button
              onClick={toggleTheme}
              className="theme-toggle"
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? '☀' : '☾'}
            </button>
          </div>
          <button
            onClick={logout}
            className="text-xs opacity-60 hover:opacity-100 transition-opacity"
            style={{ color: 'var(--text-secondary)' }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main Content ────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0">
        <div
          className="mx-auto py-8"
          style={{
            maxWidth: 'var(--content-max-width)',
            paddingLeft: 'var(--content-padding)',
            paddingRight: 'var(--content-padding)',
          }}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}
