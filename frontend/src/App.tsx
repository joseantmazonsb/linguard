import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useTheme } from './contexts/ThemeContext';
import { useMetricsCollection } from './hooks/useMetricsCollection';
import { useAuthStore } from './store/auth';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Forbidden from './pages/Forbidden';
import Dashboard from './pages/Dashboard';
import Servers from './pages/Servers';
import Peers from './pages/Peers';
import Settings from './pages/Settings';
import AuditLog from './pages/AuditLog';
import Backup from './pages/Backup';
import Logs from './pages/Logs';
import Profile from './pages/Profile';
import Integrations from './pages/Integrations';
import TrafficTriggers from './pages/TrafficTriggers';
import Plugins from './pages/Plugins';
import About from './pages/SystemInfo';
import SetupWizard from './pages/Setup/SetupWizard';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import { setupAPI } from './services/apiClient';
import { queryClient } from './queryClient';

/** Admin-only page wrapper: ProtectedRoute with role check + Layout. */
function AdminPage({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute requireAdmin>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

function App() {
  const { theme } = useTheme();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const initialize = useAuthStore((state) => state.initialize);
  const [setupStatus, setSetupStatus] = useState<{ loading: boolean; requiresSetup: boolean; setupCompleted: boolean; currentStep: string | null }>({
    loading: true,
    requiresSetup: false,
    setupCompleted: false,
    currentStep: null,
  });
  const [setupError, setSetupError] = useState(false);

  // TODO: Replace polling with WebSocket-based metrics collection
  // Temporarily disabled to prevent infinite loops and improve performance
  // useMetricsCollection(!setupStatus.requiresSetup && !setupStatus.loading && isAuthenticated);

  const checkSetup = async () => {
    setSetupError(false);
    setSetupStatus((previous) => ({ ...previous, loading: true }));
    try {
      const status = await setupAPI.getStatus();
      if (status.current_step != null && !['welcome', 'database', 'account', 'globals', 'auth', 'server', 'peer', 'complete'].includes(status.current_step)) {
        throw new Error('Unrecognized setup step');
      }
      console.log('Setup status:', status);
      const needsSetup = !status.setup_completed || status.requires_setup;
      setSetupStatus({
        loading: false,
        requiresSetup: needsSetup,
        setupCompleted: status.setup_completed,
        currentStep: status.current_step ?? null,
      });
    } catch (error) {
      console.error('Setup status check failed:', error);
      setSetupStatus((previous) => ({ ...previous, loading: false }));
      setSetupError(true);
    }
  };

  useEffect(() => {
    initialize();
    checkSetup();
  }, []);

  if (setupStatus.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  if (setupError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-4">
        <div className="text-center space-y-4">
          <p role="alert" className="text-red-700 dark:text-red-400">Unable to check setup status. Check the connection and try again.</p>
          <button type="button" onClick={checkSetup} className="rounded-lg bg-blue-600 dark:bg-blue-500 px-6 py-2 text-white">Retry</button>
        </div>
      </div>
    );
  }

  // If setup is required, redirect to setup wizard
  if (setupStatus.requiresSetup) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/setup" element={<SetupWizard serverStep={setupStatus.currentStep} />} />
            <Route path="*" element={<Navigate to="/setup" replace />} />
          </Routes>
          <ToastContainer 
            position="top-right" 
            autoClose={4000}
            theme={theme}
            hideProgressBar={false}
            newestOnTop
            closeOnClick
            pauseOnFocusLoss
            draggable
            pauseOnHover
          />
        </BrowserRouter>
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/oidc-callback" element={<AuthCallback />} />
          <Route path="/forbidden" element={<Forbidden />} />
          <Route path="/setup" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <AdminPage>
                <Dashboard />
              </AdminPage>
            }
          />
          <Route
            path="/servers"
            element={
              <AdminPage>
                <Servers />
              </AdminPage>
            }
          />
          <Route
            path="/peers"
            element={
              <AdminPage>
                <Peers />
              </AdminPage>
            }
          />
          <Route
            path="/settings"
            element={
              <AdminPage>
                <Settings />
              </AdminPage>
            }
          />
          <Route
            path="/audit"
            element={
              <AdminPage>
                <AuditLog />
              </AdminPage>
            }
          />
          <Route
            path="/backup"
            element={
              <AdminPage>
                <Backup />
              </AdminPage>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Layout>
                  <Profile />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/integrations"
            element={
              <AdminPage>
                <Integrations />
              </AdminPage>
            }
          />
          <Route
            path="/traffic-triggers"
            element={
              <AdminPage>
                <TrafficTriggers />
              </AdminPage>
            }
          />
          <Route
            path="/logs"
            element={
              <AdminPage>
                <Logs />
              </AdminPage>
            }
          />
          <Route
            path="/plugins"
            element={
              <AdminPage>
                <Plugins />
              </AdminPage>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/system-info"
            element={
              <AdminPage>
                <About />
              </AdminPage>
            }
          />
        </Routes>
        <ToastContainer 
          position="top-right" 
          autoClose={4000}
          theme={theme}
          hideProgressBar={false}
          newestOnTop
          closeOnClick
          pauseOnFocusLoss
          draggable
          pauseOnHover
        />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
