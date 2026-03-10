import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { serversAPI, peersAPI, metricsAPI, healthAPI } from "../services/api";
import { useWebSocket, type MetricsData, type ServerStatusChangeData, type HealthData } from "../hooks/useWebSocket";
import type { Server, Peer } from "../types";

type TimeRange = 24 | 168 | 720;

export default function Dashboard() {
  const [timeRange, setTimeRange] = useState<TimeRange>(24);
  const [realtimeMetrics, setRealtimeMetrics] = useState<MetricsData | null>(
    null,
  );
  const [realtimeHealth, setRealtimeHealth] = useState<HealthData | null>(null);
  const [showHealthModal, setShowHealthModal] = useState(false);
  const queryClient = useQueryClient();

  // Fetch servers
  const { data: servers = [], isLoading: serversLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: serversAPI.list,
  });

  // Fetch peers
  const { data: peers = [], isLoading: peersLoading } = useQuery({
    queryKey: ["peers"],
    queryFn: peersAPI.list,
  });

  // Fetch dashboard metrics (no polling, just initial load)
  const { data: dashboardMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["dashboard-metrics", timeRange],
    queryFn: () => metricsAPI.getDashboardMetrics(timeRange),
  });

  // Fetch health status (fallback polling every 5 minutes if WebSocket disconnected)
  const { data: healthData, isLoading: healthLoading, isFetching: healthFetching, refetch: refetchHealth } = useQuery<HealthData>({
    queryKey: ["health"],
    queryFn: healthAPI.check,
    refetchInterval: 300000, // Refetch every 5 minutes as fallback
  });

  // Use realtime health data from WebSocket if available, otherwise fall back to HTTP polling
  const currentHealthData = realtimeHealth || healthData;

  // Start server mutation
  const startServerMutation = useMutation({
    mutationFn: serversAPI.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      toast.success("Server started successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to start server");
    },
  });

  // Reload server mutation
  const reloadServerMutation = useMutation({
    mutationFn: serversAPI.reload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      toast.success("Server reloaded successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to reload server");
    },
  });

  // Stop server mutation
  const stopServerMutation = useMutation({
    mutationFn: serversAPI.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      toast.success("Server stopped successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to stop server");
    },
  });

  // Test health on demand
  const handleTestHealth = async () => {
    const result = await refetchHealth();
    // Update realtime health state to show the fresh data immediately
    if (result.data) {
      setRealtimeHealth(result.data);
    }
  };

  // Count warnings in health checks
  const getWarningCount = () => {
    if (!currentHealthData?.checks) return 0;
    return Object.values(currentHealthData.checks).filter(check => check.status === 'warning').length;
  };

  // WebSocket: Handle real-time metrics updates
  const handleMetricsUpdate = useCallback((data: MetricsData) => {
    console.log("Realtime metrics update:", data);
    setRealtimeMetrics(data);
  }, []);

  // WebSocket: Handle server status changes
  const handleServerStatusChange = useCallback((data: ServerStatusChangeData) => {
    console.log("Server status change:", data);
    
    // Invalidate servers query to refresh the list
    queryClient.invalidateQueries({ queryKey: ["servers"] });
    
    // Show toast notification if auto-detected
    if (data.detected) {
      const statusText = data.status === 'running' ? 'started' : 'stopped';
      toast.info(`Server "${data.name}" was detected as ${statusText}`, {
        autoClose: 5000,
      });
    }
  }, [queryClient]);

  // WebSocket: Handle health status updates
  const handleHealthUpdate = useCallback((data: HealthData) => {
    console.log("Realtime health update:", data);
    setRealtimeHealth(data);
    
    // Also update the query cache to keep it in sync
    queryClient.setQueryData(["health"], data);
  }, [queryClient]);

  // Connect to WebSocket for real-time updates
  useWebSocket({
    enabled: true,
    onMetricsUpdate: handleMetricsUpdate,
    onServerStatusChange: handleServerStatusChange,
    onHealthUpdate: handleHealthUpdate,
  });

  const activeServers = servers.filter((s: Server) => s.status === 'running').length;
  const enabledPeers = peers.filter((p: Peer) => p.enabled).length;
  const connectedPeers = peers.filter((p: Peer) => p.is_online).length;
  const totalServers = servers.length;
  const totalPeers = peers.length;

  const isLoading = serversLoading || peersLoading;

  // Format bytes helper
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  // Prepare chart data for servers
  const serverChartData =
    dashboardMetrics?.servers?.hourly_metrics.map((metric: any) => {
      const date = new Date(metric.timestamp);
      const formatOptions =
        timeRange === 24
          ? ({ month: "short", day: "numeric", hour: "2-digit" } as const)
          : ({ month: "short", day: "numeric" } as const);

      return {
        time: date.toLocaleString("en-US", formatOptions),
        rx: metric.rx_bytes / (1024 * 1024), // Convert to MB
        tx: metric.tx_bytes / (1024 * 1024),
      };
    }) || [];

  // Prepare bar chart data for server comparison
  const serverComparisonData =
    dashboardMetrics?.servers?.top_servers?.map((server: any) => ({
      name:
        server.name.length > 15
          ? server.name.substring(0, 15) + "..."
          : server.name,
      fullName: server.name,
      rx: server.rx_bytes / (1024 * 1024),
      tx: server.tx_bytes / (1024 * 1024),
    })) || [];

  // Prepare chart data for peers
  const peerChartData =
    dashboardMetrics?.peers?.hourly_metrics.map((metric: any) => {
      const date = new Date(metric.timestamp);
      const formatOptions =
        timeRange === 24
          ? ({ month: "short", day: "numeric", hour: "2-digit" } as const)
          : ({ month: "short", day: "numeric" } as const);

      return {
        time: date.toLocaleString("en-US", formatOptions),
        rx: metric.rx_bytes / (1024 * 1024), // Convert to MB
        tx: metric.tx_bytes / (1024 * 1024),
      };
    }) || [];

  // Prepare bar chart data for peer comparison
  const peerComparisonData =
    dashboardMetrics?.peers?.top_peers?.map((peer: any) => ({
      name:
        peer.name.length > 15 ? peer.name.substring(0, 15) + "..." : peer.name,
      fullName: peer.name,
      rx: peer.rx_bytes / (1024 * 1024),
      tx: peer.tx_bytes / (1024 * 1024),
    })) || [];

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
        Dashboard
      </h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Link
          to={"/servers"}
          className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow hover:shadow-lg transition-shadow"
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400">
              Total Servers
            </h3>
            <svg
              className="w-8 h-8 text-blue-500 dark:text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {isLoading ? "-" : totalServers}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {isLoading ? "Loading..." : `${activeServers} active`}
          </p>
        </Link>

        <Link
          to={"/peers"}
          className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow hover:shadow-lg transition-shadow"
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400">
              Total Peers
            </h3>
            <svg
              className="w-8 h-8 text-green-500 dark:text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {isLoading ? "-" : totalPeers}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {isLoading ? "Loading..." : `${connectedPeers} connected`}
          </p>
        </Link>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400">
              Active Connections
            </h3>
            <svg
              className="w-8 h-8 text-purple-500 dark:text-purple-400"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fillRule="evenodd" d="M17.778 8.222c-4.296-4.296-11.26-4.296-15.556 0A1 1 0 01.808 6.808c5.076-5.077 13.308-5.077 18.384 0a1 1 0 01-1.414 1.414zM14.95 11.05a7 7 0 00-9.9 0 1 1 0 01-1.414-1.414 9 9 0 0112.728 0 1 1 0 01-1.414 1.414zM12.12 13.88a3 3 0 00-4.242 0 1 1 0 01-1.415-1.415 5 5 0 017.072 0 1 1 0 01-1.415 1.415zM9 16a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {isLoading ? "-" : connectedPeers}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Live connections
          </p>
        </div>

        <div 
          className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => setShowHealthModal(true)}
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400">
              System Health
            </h3>
            {healthLoading ? (
              <div className="w-8 h-8 animate-pulse bg-gray-300 dark:bg-gray-600 rounded-full"></div>
            ) : currentHealthData?.status === 'healthy' ? (
              <svg
                className="w-8 h-8 text-emerald-500 dark:text-emerald-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            ) : currentHealthData?.status === 'warning' ? (
              <svg
                className="w-8 h-8 text-yellow-500 dark:text-yellow-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            ) : (
              <svg
                className="w-8 h-8 text-red-500 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            )}
          </div>
          <p className={`text-3xl font-bold ${
            healthLoading 
              ? 'text-gray-400 dark:text-gray-500' 
              : currentHealthData?.status === 'healthy' 
                ? 'text-emerald-600 dark:text-emerald-400'
                : currentHealthData?.status === 'warning'
                ? 'text-yellow-600 dark:text-yellow-400'
                : 'text-red-600 dark:text-red-400'
          }`}>
            {healthLoading ? 'Checking...' : currentHealthData?.status === 'healthy' ? 'Healthy' : currentHealthData?.status === 'warning' ? 'Warning' : 'Unhealthy'}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {healthLoading 
              ? 'Loading status...' 
              : currentHealthData?.status === 'healthy'
                ? getWarningCount() > 0
                  ? (
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4 text-yellow-500 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      {getWarningCount()} {getWarningCount() === 1 ? 'warning' : 'warnings'}
                    </span>
                  )
                  : 'All systems operational'
                : 'Click for details'}
          </p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Quick Actions
          </h2>
          <div className="space-y-3">
            <Link
              to="/servers"
              className="flex items-center justify-between p-4 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-lg transition-colors group"
            >
              <div className="flex items-center gap-3">
                <svg
                  className="w-6 h-6 text-blue-600 dark:text-blue-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-white">
                  Create New Server
                </span>
              </div>
              <svg
                className="w-5 h-5 text-gray-400 dark:text-gray-500 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>

            <Link
              to="/peers"
              className={`flex items-center justify-between p-4 rounded-lg transition-colors group ${
                totalServers === 0
                  ? "bg-gray-100 dark:bg-gray-700 cursor-not-allowed opacity-60"
                  : "bg-green-50 dark:bg-green-900/30 hover:bg-green-100 dark:hover:bg-green-900/50"
              }`}
              onClick={(e) => {
                if (totalServers === 0) {
                  e.preventDefault();
                }
              }}
              title={
                totalServers === 0
                  ? "Create a server first before adding peers"
                  : ""
              }
            >
              <div className="flex items-center gap-3">
                <svg
                  className="w-6 h-6 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-white">
                  Add New Peer
                </span>
              </div>
              <svg
                className={`w-5 h-5 transition-colors ${
                  totalServers === 0
                    ? "text-gray-400 dark:text-gray-500"
                    : "text-gray-400 dark:text-gray-500 group-hover:text-green-600 dark:group-hover:text-green-400"
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>

            <Link
              to="/settings"
              className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
            >
              <div className="flex items-center gap-3">
                <svg
                  className="w-6 h-6 text-gray-600 dark:text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-white">
                  Configure Settings
                </span>
              </div>
              <svg
                className="w-5 h-5 text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Recent Servers
          </h2>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              Loading...
            </div>
          ) : servers.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                No servers configured yet
              </p>
              <Link
                to="/servers"
                className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
              >
                Create your first server →
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {servers.slice(0, 5).map((server: Server) => {
                const needsReload = server.status === 'running' && server.needs_reload;
                const isInactive = server.status !== 'running';
                
                return (
                  <div
                    key={server.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                  >
                    <Link 
                      to="/servers"
                      className="flex items-center gap-3 flex-1 hover:opacity-80 transition-opacity"
                    >
                      <div
                        className={`w-2 h-2 rounded-full ${
                          needsReload 
                            ? "bg-orange-500" 
                            : server.status === 'running' 
                              ? "bg-green-500" 
                              : "bg-gray-400"
                        }`}
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {server.name}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {server.endpoint}:{server.listen_port}
                        </p>
                      </div>
                    </Link>
                    <div className="flex items-center gap-2">
                      {needsReload && (
                        <span className="text-xs px-2 py-1 rounded-full bg-orange-100 dark:bg-orange-900/50 text-orange-800 dark:text-orange-300">
                          Needs Reload
                        </span>
                      )}
                      {/* Running servers: show Reload and Stop icon buttons */}
                      {server.status === 'running' && (
                        <>
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              reloadServerMutation.mutate(server.id);
                            }}
                            disabled={reloadServerMutation.isPending}
                            className={`p-2 ${
                              needsReload 
                                ? "text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/30" 
                                : "text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                            } rounded transition-colors disabled:opacity-50`}
                            title="Reload server configuration"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              stopServerMutation.mutate(server.id);
                            }}
                            disabled={stopServerMutation.isPending}
                            className="p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors disabled:opacity-50"
                            title="Stop server"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                            </svg>
                          </button>
                        </>
                      )}
                      {/* Inactive servers: show Start icon button */}
                      {isInactive && (
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            startServerMutation.mutate(server.id);
                          }}
                          disabled={startServerMutation.isPending}
                          className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors disabled:opacity-50"
                          title="Start server"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Server Traffic Overview */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow mb-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Server Traffic Overview
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setTimeRange(24)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 24
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setTimeRange(168)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 168
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              7d
            </button>
            <button
              onClick={() => setTimeRange(720)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 720
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              30d
            </button>
          </div>
        </div>

        {/* Traffic Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-2 mb-2">
              <svg
                className="w-5 h-5 text-green-600 dark:text-green-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 14l-7 7m0 0l-7-7m7 7V3"
                />
              </svg>
              <span className="text-sm font-medium text-green-700 dark:text-green-300">
                Total Received (Servers)
              </span>
            </div>
            <p className="text-2xl font-bold text-green-900 dark:text-green-100">
              {metricsLoading
                ? "Loading..."
                : formatBytes(
                    dashboardMetrics?.servers?.current_totals?.total_rx_bytes ||
                      0,
                  )}
            </p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-2 mb-2">
              <svg
                className="w-5 h-5 text-blue-600 dark:text-blue-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 10l7-7m0 0l7 7m-7-7v18"
                />
              </svg>
              <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                Total Transmitted (Servers)
              </span>
            </div>
            <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">
              {metricsLoading
                ? "Loading..."
                : formatBytes(
                    dashboardMetrics?.servers?.current_totals?.total_tx_bytes ||
                      0,
                  )}
            </p>
          </div>
        </div>

        {/* Charts Grid */}
        {metricsLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-500 dark:text-gray-400">
              Loading metrics...
            </div>
          </div>
        ) : serverChartData.length === 0 ? (
          <div className="flex items-center justify-center h-64 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
            <div className="text-center">
              <svg
                className="w-12 h-12 text-gray-400 mx-auto mb-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              <p className="text-gray-700 dark:text-gray-300 font-medium">
                No server traffic data available
              </p>
              <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                Metrics will appear here once collected
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Line Chart - Traffic Over Time */}
            <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Traffic Over Time
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={serverChartData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#374151"
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="time"
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                  />
                  <YAxis
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                    label={{
                      value: "Traffic (MB)",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#9CA3AF",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1F2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                      color: "#F9FAFB",
                    }}
                    formatter={(value: number) => [
                      `${value.toFixed(2)} MB`,
                      "",
                    ]}
                  />
                  <Legend wrapperStyle={{ color: "#9CA3AF" }} iconType="line" />
                  <Line
                    type="monotone"
                    dataKey="rx"
                    stroke="#10B981"
                    strokeWidth={2}
                    name="Received"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="tx"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    name="Transmitted"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Bar Chart - Server Comparison */}
            <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Traffic by Server
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={serverComparisonData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#374151"
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="name"
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 11 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                  />
                  <YAxis
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                    label={{
                      value: "Traffic (MB)",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#9CA3AF",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1F2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                      color: "#F9FAFB",
                    }}
                    formatter={(value: number, name: string, props: any) => [
                      `${value.toFixed(2)} MB`,
                      name === "rx" ? "Received" : "Transmitted",
                    ]}
                    labelFormatter={(label) => {
                      const item = serverComparisonData.find(
                        (d) => d.name === label,
                      );
                      return item?.fullName || label;
                    }}
                  />
                  <Legend wrapperStyle={{ color: "#9CA3AF" }} />
                  <Bar
                    dataKey="rx"
                    fill="#10B981"
                    name="Received"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="tx"
                    fill="#3B82F6"
                    name="Transmitted"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Peer Traffic Overview */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow mb-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Peer Traffic Overview
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setTimeRange(24)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 24
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setTimeRange(168)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 168
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              7d
            </button>
            <button
              onClick={() => setTimeRange(720)}
              className={`px-3 py-1 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 720
                  ? "bg-cyan-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              30d
            </button>
          </div>
        </div>

        {/* Traffic Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-2 mb-2">
              <svg
                className="w-5 h-5 text-green-600 dark:text-green-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 14l-7 7m0 0l-7-7m7 7V3"
                />
              </svg>
              <span className="text-sm font-medium text-green-700 dark:text-green-300">
                Total Received (Peers)
              </span>
            </div>
            <p className="text-2xl font-bold text-green-900 dark:text-green-100">
              {metricsLoading
                ? "Loading..."
                : formatBytes(
                    dashboardMetrics?.peers?.current_totals?.total_rx_bytes ||
                      0,
                  )}
            </p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-2 mb-2">
              <svg
                className="w-5 h-5 text-blue-600 dark:text-blue-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 10l7-7m0 0l7 7m-7-7v18"
                />
              </svg>
              <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                Total Transmitted (Peers)
              </span>
            </div>
            <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">
              {metricsLoading
                ? "Loading..."
                : formatBytes(
                    dashboardMetrics?.peers?.current_totals?.total_tx_bytes ||
                      0,
                  )}
            </p>
          </div>
        </div>

        {/* Charts Grid */}
        {metricsLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-500 dark:text-gray-400">
              Loading metrics...
            </div>
          </div>
        ) : peerChartData.length === 0 ? (
          <div className="flex items-center justify-center h-64 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
            <div className="text-center">
              <svg
                className="w-12 h-12 text-gray-400 mx-auto mb-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              <p className="text-gray-700 dark:text-gray-300 font-medium">
                No peer traffic data available
              </p>
              <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                Metrics will appear here once collected
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Line Chart - Traffic Over Time */}
            <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Traffic Over Time
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={peerChartData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#374151"
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="time"
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                  />
                  <YAxis
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                    label={{
                      value: "Traffic (MB)",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#9CA3AF",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1F2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                      color: "#F9FAFB",
                    }}
                    formatter={(value: number) => [
                      `${value.toFixed(2)} MB`,
                      "",
                    ]}
                  />
                  <Legend wrapperStyle={{ color: "#9CA3AF" }} iconType="line" />
                  <Line
                    type="monotone"
                    dataKey="rx"
                    stroke="#10B981"
                    strokeWidth={2}
                    name="Received"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="tx"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    name="Transmitted"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Bar Chart - Peer Comparison */}
            <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Traffic by Peer
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={peerComparisonData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#374151"
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="name"
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 11 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                  />
                  <YAxis
                    stroke="#9CA3AF"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                    tickLine={{ stroke: "#9CA3AF" }}
                    label={{
                      value: "Traffic (MB)",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#9CA3AF",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1F2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                      color: "#F9FAFB",
                    }}
                    formatter={(value: number, name: string, props: any) => [
                      `${value.toFixed(2)} MB`,
                      name === "rx" ? "Received" : "Transmitted",
                    ]}
                    labelFormatter={(label) => {
                      const item = peerComparisonData.find(
                        (d) => d.name === label,
                      );
                      return item?.fullName || label;
                    }}
                  />
                  <Legend wrapperStyle={{ color: "#9CA3AF" }} />
                  <Bar
                    dataKey="rx"
                    fill="#10B981"
                    name="Received"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="tx"
                    fill="#3B82F6"
                    name="Transmitted"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Health Details Modal */}
      {showHealthModal && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
          onClick={() => setShowHealthModal(false)}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                System Health Details
              </h2>
              <button
                onClick={() => setShowHealthModal(false)}
                className="p-2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {healthLoading ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                Loading health status...
              </div>
            ) : (
              <div className="space-y-4">
                {/* Overall Status */}
                <div className={`p-4 rounded-lg border-2 ${
                  currentHealthData?.status === 'healthy'
                    ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-500 dark:border-emerald-500'
                    : currentHealthData?.status === 'warning'
                    ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-500 dark:border-yellow-500'
                    : 'bg-red-50 dark:bg-red-900/20 border-red-500 dark:border-red-500'
                }`}>
                  <div className="flex items-center gap-3">
                    {currentHealthData?.status === 'healthy' ? (
                      <svg className="w-8 h-8 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    ) : currentHealthData?.status === 'warning' ? (
                      <svg className="w-8 h-8 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    ) : (
                      <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    )}
                    <div>
                      <h3 className={`text-xl font-bold ${
                        currentHealthData?.status === 'healthy'
                          ? 'text-emerald-900 dark:text-emerald-100'
                          : currentHealthData?.status === 'warning'
                          ? 'text-yellow-900 dark:text-yellow-100'
                          : 'text-red-900 dark:text-red-100'
                      }`}>
                        System Status: {currentHealthData?.status?.toUpperCase()}
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Last checked: {currentHealthData?.timestamp ? new Date(currentHealthData.timestamp).toLocaleString() : 'Unknown'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Component Checks */}
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Component Status</h3>
                  
                  {/* Database Check */}
                  <div className={`p-4 rounded-lg border ${
                    currentHealthData?.checks?.database?.status === 'healthy'
                      ? 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}>
                    <div className="flex items-start gap-3">
                      {currentHealthData?.checks?.database?.status === 'healthy' ? (
                        <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                       <div className="flex-1">
                         <h4 className="font-semibold text-gray-900 dark:text-white">Database</h4>
                         <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                           {currentHealthData?.checks?.database?.message}
                         </p>
                       </div>
                     </div>
                  </div>

                  {/* WireGuard Check */}
                  <div className={`p-4 rounded-lg border ${
                    currentHealthData?.checks?.wireguard?.status === 'healthy'
                      ? 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}>
                    <div className="flex items-start gap-3">
                      {currentHealthData?.checks?.wireguard?.status === 'healthy' ? (
                        <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 dark:text-white">WireGuard</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {currentHealthData?.checks?.wireguard?.message || 'No message available'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* IP Forwarding Check */}
                  <div className={`p-4 rounded-lg border ${
                    currentHealthData?.checks?.ip_forwarding?.status === 'healthy'
                      ? 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
                      : currentHealthData?.checks?.ip_forwarding?.status === 'warning'
                      ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}>
                    <div className="flex items-start gap-3">
                      {currentHealthData?.checks?.ip_forwarding?.status === 'healthy' ? (
                        <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : currentHealthData?.checks?.ip_forwarding?.status === 'warning' ? (
                        <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      ) : (
                        <svg className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 dark:text-white">IP Forwarding</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {currentHealthData?.checks?.ip_forwarding?.message || 'No message available'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Firewall Check */}
                  <div className={`p-4 rounded-lg border ${
                    currentHealthData?.checks?.firewall?.status === 'healthy'
                      ? 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}>
                    <div className="flex items-start gap-3">
                      {currentHealthData?.checks?.firewall?.status === 'healthy' ? (
                        <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900 dark:text-white">Firewall/NAT</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {currentHealthData?.checks?.firewall?.message || 'No message available'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-4">
                  <button
                    onClick={handleTestHealth}
                    disabled={healthFetching}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 dark:bg-emerald-700 dark:hover:bg-emerald-600 dark:disabled:bg-emerald-800 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {healthFetching && (
                      <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    )}
                    {healthFetching ? 'Testing...' : 'Test Health Now'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
