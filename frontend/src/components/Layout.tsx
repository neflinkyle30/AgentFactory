import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

/**
 * Main application shell: sidebar + content area.
 * Renders child routes via <Outlet />.
 */
export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

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
          <p
            className="text-xs mb-1 font-semibold tracking-wider uppercase"
            style={{ color: 'var(--text-tertiary)' }}
          >
            {user?.email}
          </p>
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
