import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useTheme } from './contexts/ThemeContext';
import { useMetricsCollection } from './hooks/useMetricsCollection';
import { useAuthStore } from './store/auth';
import Login from './pages/Login';
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
import { setupAPI } from './services/api';

const queryClient = new QueryClient();

function App() {
  const { theme } = useTheme();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const initialize = useAuthStore((state) => state.initialize);
  const [setupStatus, setSetupStatus] = useState<{ loading: boolean; requiresSetup: boolean; setupCompleted: boolean }>({
    loading: true,
    requiresSetup: false,
    setupCompleted: false,
  });

  // TODO: Replace polling with WebSocket-based metrics collection
  // Temporarily disabled to prevent infinite loops and improve performance
  // useMetricsCollection(!setupStatus.requiresSetup && !setupStatus.loading && isAuthenticated);

  useEffect(() => {
    // Initialize auth state from localStorage
    initialize();
    
    // Check setup status on mount
    const checkSetup = async () => {
      try {
        const status = await setupAPI.getStatus();
        console.log('Setup status:', status);
        // Show setup wizard if setup is not completed OR if setup is required
        const needsSetup = !status.setup_completed || status.requires_setup;
        setSetupStatus({ 
          loading: false, 
          requiresSetup: needsSetup,
          setupCompleted: status.setup_completed 
        });
      } catch (error) {
        console.error('Setup status check failed:', error);
        // If API fails, assume setup might be needed
        setSetupStatus({ loading: false, requiresSetup: true, setupCompleted: false });
      }
    };
    checkSetup();
  }, []);

  if (setupStatus.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  // If setup is required, redirect to setup wizard
  if (setupStatus.requiresSetup) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/setup" element={<SetupWizard />} />
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
          <Route path="/setup" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Layout>
                  <Dashboard />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/servers"
            element={
              <ProtectedRoute>
                <Layout>
                  <Servers />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/peers"
            element={
              <ProtectedRoute>
                <Layout>
                  <Peers />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Layout>
                  <Settings />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLog />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/backup"
            element={
              <ProtectedRoute>
                <Layout>
                  <Backup />
                </Layout>
              </ProtectedRoute>
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
              <ProtectedRoute>
                <Layout>
                  <Integrations />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/traffic-triggers"
            element={
              <ProtectedRoute>
                <Layout>
                  <TrafficTriggers />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/logs"
            element={
              <ProtectedRoute>
                <Layout>
                  <Logs />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/plugins"
            element={
              <ProtectedRoute>
                <Layout>
                  <Plugins />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/system-info"
            element={
              <ProtectedRoute>
                <Layout>
                  <About />
                </Layout>
              </ProtectedRoute>
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
