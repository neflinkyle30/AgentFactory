import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';

const RunDetailPage = lazy(() => import('./pages/RunDetailPage'));
const TicketFormPage = lazy(() => import('./pages/TicketFormPage'));

function PageFallback() {
  return (
    <div className="flex items-center justify-center py-16">
      <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-mono)' }}>
        Loading…
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes — wrapped in Layout (sidebar + content shell) */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route
          path="/new"
          element={
            <Suspense fallback={<PageFallback />}>
              <TicketFormPage />
            </Suspense>
          }
        />
        <Route
          path="/runs/:runId"
          element={
            <Suspense fallback={<PageFallback />}>
              <RunDetailPage />
            </Suspense>
          }
        />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
