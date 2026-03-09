import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
import { serversAPI, peersAPI, metricsAPI } from "../services/api";
import ServerForm from "../components/ServerForm";
import ServerCard from "../components/ServerCard";
import ImportServerDialog from "../components/ImportServerDialog";
import MetricsModal from "../components/MetricsModal";
import ConfirmDialog from "../components/ConfirmDialog";
import AddMenuButton from "../components/AddMenuButton";
import BulkActionsButton from "../components/BulkActionsButton";
import type { Server } from "../types";
import type { FieldErrors } from "../utils/errorUtils";
import {
  parseValidationErrors,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from "../utils/errorUtils";

type TimeRange = 24 | 168 | 720;

export default function Servers() {
  const [activeTab, setActiveTab] = useState<"servers" | "traffic">("servers");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<Server | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [showMetrics, setShowMetrics] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>(24);
  const [bulkSelectMode, setBulkSelectMode] = useState<
    "none" | "delete" | "download" | "start" | "stop"
  >("none");
  const [selectedServerIds, setSelectedServerIds] = useState<Set<number>>(
    new Set(),
  );
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });
  const [operatingServerIds, setOperatingServerIds] = useState<{
    starting: Set<number>;
    stopping: Set<number>;
    reloading: Set<number>;
  }>({
    starting: new Set(),
    stopping: new Set(),
    reloading: new Set(),
  });
  const queryClient = useQueryClient();

  // Fetch servers
  const {
    data: servers = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["servers"],
    queryFn: serversAPI.list,
  });

  // Fetch servers aggregate metrics
  const { data: serversMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["servers-aggregate-metrics", timeRange],
    queryFn: () => metricsAPI.getServersAggregateMetrics(timeRange),
  });

  // Format bytes helper
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  // Prepare line chart data
  const chartData =
    serversMetrics?.hourly_metrics.map((metric: any) => {
      const date = new Date(metric.timestamp);
      const formatOptions =
        timeRange === 24
          ? ({ month: "short", day: "numeric", hour: "2-digit" } as const)
          : ({ month: "short", day: "numeric" } as const);

      return {
        time: date.toLocaleString("en-US", formatOptions),
        rx: metric.rx_bytes / (1024 * 1024),
        tx: metric.tx_bytes / (1024 * 1024),
      };
    }) || [];

  // Prepare bar chart data for server comparison
  const serverComparisonData =
    serversMetrics?.servers.map((server: any) => ({
      name:
        server.name.length > 15
          ? server.name.substring(0, 15) + "..."
          : server.name,
      fullName: server.name,
      rx: server.rx_bytes / (1024 * 1024),
      tx: server.tx_bytes / (1024 * 1024),
    })) || [];

  // Create server mutation
  const createMutation = useMutation({
    mutationFn: serversAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      setIsFormOpen(false);
      setEditingServer(null);
      setFieldErrors({});
      toast.success("Server created successfully");
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to create server"));
      }
    },
  });

  // Update server mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      serversAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      setIsFormOpen(false);
      setEditingServer(null);
      setFieldErrors({});
      toast.success("Server updated successfully");
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to update server"));
      }
    },
  });

  // Delete server mutation
  const deleteMutation = useMutation({
    mutationFn: serversAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      toast.success("Server deleted successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete server";
      toast.error(message);
    },
  });

  // Start server mutation
  const startMutation = useMutation({
    mutationFn: serversAPI.start,
    onMutate: (serverId) => {
      setOperatingServerIds((prev) => ({
        ...prev,
        starting: new Set(prev.starting).add(serverId),
      }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: (error: any, serverId) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to start server";
      toast.error(message);
    },
    onSettled: (data, error, serverId) => {
      setOperatingServerIds((prev) => {
        const newStarting = new Set(prev.starting);
        newStarting.delete(serverId);
        return { ...prev, starting: newStarting };
      });
    },
  });

  // Stop server mutation
  const stopMutation = useMutation({
    mutationFn: serversAPI.stop,
    onMutate: (serverId) => {
      setOperatingServerIds((prev) => ({
        ...prev,
        stopping: new Set(prev.stopping).add(serverId),
      }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: (error: any, serverId) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to stop server";
      toast.error(message);
    },
    onSettled: (data, error, serverId) => {
      setOperatingServerIds((prev) => {
        const newStopping = new Set(prev.stopping);
        newStopping.delete(serverId);
        return { ...prev, stopping: newStopping };
      });
    },
  });

  // Reload server mutation
  const reloadMutation = useMutation({
    mutationFn: serversAPI.reload,
    onMutate: (serverId) => {
      setOperatingServerIds((prev) => ({
        ...prev,
        reloading: new Set(prev.reloading).add(serverId),
      }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: (error: any, serverId) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to reload server";
      toast.error(message);
    },
    onSettled: (data, error, serverId) => {
      setOperatingServerIds((prev) => {
        const newReloading = new Set(prev.reloading);
        newReloading.delete(serverId);
        return { ...prev, reloading: newReloading };
      });
    },
  });

  // Import server mutation (using create endpoint)
  const importMutation = useMutation({
    mutationFn: serversAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servers"] });
      setIsImportOpen(false);
      toast.success("Server imported successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to import server";
      toast.error(message);
    },
  });

  const handleCreate = () => {
    setEditingServer(null);
    setFieldErrors({});
    setIsFormOpen(true);
  };

  const handleEdit = (server: Server) => {
    setEditingServer(server);
    setFieldErrors({});
    setIsFormOpen(true);
  };

  const handleDelete = async (id: number, name: string) => {
    console.log('handleDelete called with id:', id, 'name:', name);
    // Get peer count for this server
    try {
      console.log('Fetching peer count for server:', id);
      const peerCountResponse = await peersAPI.count(id);
      console.log('Peer count response:', peerCountResponse);
      const peerCount = peerCountResponse.total || 0;
      console.log('Peer count:', peerCount);
      
      setConfirmDialog({
        isOpen: true,
        title: "Delete Server",
        message: (
          <div className="space-y-3">
            <p>Are you sure you want to delete server <strong>"{name}"</strong>?</p>
            {peerCount > 0 && (
              <p className="text-yellow-600 dark:text-yellow-400">
                This server has <strong>{peerCount} peer{peerCount !== 1 ? 's' : ''}</strong> that will also be deleted. 
                Consider migrating peers to another server before deleting if you want to keep them.
              </p>
            )}
            <p className="font-bold">This action cannot be undone.</p>
          </div>
        ),
        onConfirm: () => {
          deleteMutation.mutate(id);
          setConfirmDialog({ ...confirmDialog, isOpen: false });
        },
      });
    } catch (error) {
      // If peer count fetch fails, show basic confirmation
      console.error("Failed to fetch peer count:", error);
      setConfirmDialog({
        isOpen: true,
        title: "Delete Server",
        message: (
          <div className="space-y-3">
            <p>Are you sure you want to delete server <strong>"{name}"</strong>?</p>
            <p className="text-yellow-600 dark:text-yellow-400">
              All associated peers will also be deleted.
            </p>
            <p className="font-bold">This action cannot be undone.</p>
          </div>
        ),
        onConfirm: () => {
          deleteMutation.mutate(id);
          setConfirmDialog({ ...confirmDialog, isOpen: false });
        },
      });
    }
  };

  const handleBulkDelete = async () => {
    if (bulkSelectMode === "none") {
      setBulkSelectMode("delete");
      setSelectedServerIds(new Set());
    } else if (bulkSelectMode === "delete") {
      if (selectedServerIds.size === 0) {
        setBulkSelectMode("none");
        return;
      }

      const serverNames = servers
        .filter((s: Server) => selectedServerIds.has(s.id))
        .map((s: Server) => s.name)
        .join(", ");

      // Get total peer count for all selected servers
      try {
        const peerCountPromises = Array.from(selectedServerIds).map((id) =>
          peersAPI.count(id)
        );
        const peerCounts = await Promise.all(peerCountPromises);
        const totalPeerCount = peerCounts.reduce((sum, response) => sum + (response.total || 0), 0);

        setConfirmDialog({
          isOpen: true,
          title: "Delete Servers",
          message: (
            <div className="space-y-3">
              <p>Are you sure you want to delete <strong>{selectedServerIds.size} server{selectedServerIds.size !== 1 ? 's' : ''}</strong>?</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">({serverNames})</p>
              {totalPeerCount > 0 && (
                <p className="text-yellow-600 dark:text-yellow-400">
                  This will also delete <strong>{totalPeerCount} peer{totalPeerCount !== 1 ? 's' : ''}</strong> across all selected servers. 
                  Consider migrating peers before deleting if you want to keep them.
                </p>
              )}
              <p className="font-bold">This action cannot be undone.</p>
            </div>
          ),
          onConfirm: async () => {
            const deletePromises = Array.from(selectedServerIds).map((id) =>
              deleteMutation.mutateAsync(id),
            );

            try {
              await Promise.all(deletePromises);
              toast.success(
                `${selectedServerIds.size} server(s) deleted successfully`,
              );
            } catch (error) {
              toast.error("Some servers failed to delete");
            }

            setBulkSelectMode("none");
            setSelectedServerIds(new Set());
            setConfirmDialog({ ...confirmDialog, isOpen: false });
          },
        });
      } catch (error) {
        // If peer count fetch fails, show basic confirmation
        console.error("Failed to fetch peer counts:", error);
        setConfirmDialog({
          isOpen: true,
          title: "Delete Servers",
          message: (
            <div className="space-y-3">
              <p>Are you sure you want to delete <strong>{selectedServerIds.size} server{selectedServerIds.size !== 1 ? 's' : ''}</strong>?</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">({serverNames})</p>
              <p className="text-yellow-600 dark:text-yellow-400">
                All associated peers will also be deleted.
              </p>
              <p className="font-bold">This action cannot be undone.</p>
            </div>
          ),
          onConfirm: async () => {
            const deletePromises = Array.from(selectedServerIds).map((id) =>
              deleteMutation.mutateAsync(id),
            );

            try {
              await Promise.all(deletePromises);
              toast.success(
                `${selectedServerIds.size} server(s) deleted successfully`,
              );
            } catch (error) {
              toast.error("Some servers failed to delete");
            }

            setBulkSelectMode("none");
            setSelectedServerIds(new Set());
            setConfirmDialog({ ...confirmDialog, isOpen: false });
          },
        });
      }
    }
  };

  const handleBulkDownload = async () => {
    if (bulkSelectMode === "none") {
      setBulkSelectMode("download");
      setSelectedServerIds(new Set());
    } else if (bulkSelectMode === "download") {
      if (selectedServerIds.size === 0) {
        setBulkSelectMode("none");
        return;
      }

      for (const serverId of selectedServerIds) {
        const server = servers.find((s: Server) => s.id === serverId);
        if (server) {
          await handleDownloadConfig(serverId, server.name);
        }
      }

      setBulkSelectMode("none");
      setSelectedServerIds(new Set());
    }
  };

  const handleBulkStart = async () => {
    if (bulkSelectMode === "none") {
      setBulkSelectMode("start");
      setSelectedServerIds(new Set());
    } else if (bulkSelectMode === "start") {
      if (selectedServerIds.size === 0) {
        setBulkSelectMode("none");
        return;
      }

      const startPromises = Array.from(selectedServerIds).map((id) =>
        startMutation.mutateAsync(id),
      );

      try {
        await Promise.all(startPromises);
        toast.success(
          `${selectedServerIds.size} server(s) started successfully`,
        );
      } catch (error) {
        toast.error("Some servers failed to start");
      }

      setBulkSelectMode("none");
      setSelectedServerIds(new Set());
    }
  };

  const handleBulkStop = async () => {
    if (bulkSelectMode === "none") {
      setBulkSelectMode("stop");
      setSelectedServerIds(new Set());
    } else if (bulkSelectMode === "stop") {
      if (selectedServerIds.size === 0) {
        setBulkSelectMode("none");
        return;
      }

      const stopPromises = Array.from(selectedServerIds).map((id) =>
        stopMutation.mutateAsync(id),
      );

      try {
        await Promise.all(stopPromises);
        toast.success(
          `${selectedServerIds.size} server(s) stopped successfully`,
        );
      } catch (error) {
        toast.error("Some servers failed to stop");
      }

      setBulkSelectMode("none");
      setSelectedServerIds(new Set());
    }
  };

  const handleCancelBulkOperation = () => {
    setBulkSelectMode("none");
    setSelectedServerIds(new Set());
  };

  const handleConfirmBulkOperation = () => {
    switch (bulkSelectMode) {
      case "delete":
        handleBulkDelete();
        break;
      case "download":
        handleBulkDownload();
        break;
      case "start":
        handleBulkStart();
        break;
      case "stop":
        handleBulkStop();
        break;
    }
  };

  const toggleServerSelection = (serverId: number) => {
    const newSelected = new Set(selectedServerIds);
    if (newSelected.has(serverId)) {
      newSelected.delete(serverId);
    } else {
      newSelected.add(serverId);
    }
    setSelectedServerIds(newSelected);
  };

  const handleSubmit = (data: any) => {
    if (editingServer) {
      updateMutation.mutate({ id: editingServer.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleStart = (id: number) => {
    startMutation.mutate(id);
  };

  const handleStop = (id: number) => {
    stopMutation.mutate(id);
  };

  const handleReload = (id: number) => {
    reloadMutation.mutate(id);
  };

  const handleDownloadConfig = async (id: number, name: string) => {
    try {
      const config = await serversAPI.getConfig(id);
      const blob = new Blob([config], { type: "text/plain" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}.conf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Failed to download config:", error);
      toast.error("Failed to download configuration file");
    }
  };

  const handleShowMetrics = (id: number, name: string) => {
    setShowMetrics({ id, name });
  };

  const handleImport = (data: any) => {
    importMutation.mutate(data);
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500 dark:text-gray-400">
            Loading servers...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          Error loading servers: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
          Servers
        </h1>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab("servers")}
              className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "servers"
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300"
              }`}
            >
              <div className="flex items-center gap-2">
                <svg
                  className="w-5 h-5"
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
                Servers
              </div>
            </button>
            <button
              onClick={() => setActiveTab("traffic")}
              className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "traffic"
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300"
              }`}
            >
              <div className="flex items-center gap-2">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                Traffic Overview
              </div>
            </button>
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "servers" && (
        <>
          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-start gap-2 sm:gap-3 mb-6">
            {bulkSelectMode !== "none" ? (
              /* Selection Mode - Show Cancel and Confirm buttons */
              <>
                <button
                  onClick={handleCancelBulkOperation}
                  className="bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm"
                >
                  <svg
                    className="w-4 h-4 sm:w-5 sm:h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                  <span className="hidden xs:inline">Cancel</span>
                </button>
                <button
                  onClick={handleConfirmBulkOperation}
                  disabled={selectedServerIds.size === 0}
                  className={`${
                    bulkSelectMode === "delete"
                      ? "bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600"
                      : bulkSelectMode === "download"
                        ? "bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-600"
                        : bulkSelectMode === "start"
                          ? "bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600"
                          : "bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600"
                  } disabled:bg-gray-400 disabled:cursor-not-allowed text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm`}
                >
                  {bulkSelectMode === "delete" && (
                    <svg
                      className="w-4 h-4 sm:w-5 sm:h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  )}
                  {bulkSelectMode === "download" && (
                    <svg
                      className="w-4 h-4 sm:w-5 sm:h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                  )}
                  {bulkSelectMode === "start" && (
                    <svg
                      className="w-4 h-4 sm:w-5 sm:h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  )}
                  {bulkSelectMode === "stop" && (
                    <svg
                      className="w-4 h-4 sm:w-5 sm:h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
                      />
                    </svg>
                  )}
                  <span>
                    {bulkSelectMode === "delete" &&
                      `Delete${selectedServerIds.size > 0 ? ` (${selectedServerIds.size})` : ""}`}
                    {bulkSelectMode === "download" &&
                      `Download${selectedServerIds.size > 0 ? ` (${selectedServerIds.size})` : ""}`}
                    {bulkSelectMode === "start" &&
                      `Start${selectedServerIds.size > 0 ? ` (${selectedServerIds.size})` : ""}`}
                    {bulkSelectMode === "stop" &&
                      `Stop${selectedServerIds.size > 0 ? ` (${selectedServerIds.size})` : ""}`}
                  </span>
                </button>
              </>
            ) : (
              /* Normal Mode - Show Add and Bulk Actions buttons */
              <>
                {servers.length > 0 && (
                  <>
                    <AddMenuButton
                      onAdd={handleCreate}
                      onImport={() => setIsImportOpen(true)}
                      isImportDisabled={importMutation.isPending}
                    />
                    <BulkActionsButton
                      onStart={handleBulkStart}
                      onStop={handleBulkStop}
                      onDownload={handleBulkDownload}
                      onDelete={handleBulkDelete}
                    />
                  </>
                )}
              </>
            )}
          </div>

          {/* Stats Overview - Hidden during selection mode */}
          {bulkSelectMode === "none" && servers.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-blue-600 dark:text-blue-300"
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
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Total Servers
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {servers.length}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 dark:bg-green-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-green-600 dark:text-green-300"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Running
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {servers.filter((s: Server) => s.status === "running").length}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-red-100 dark:bg-red-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-red-600 dark:text-red-300"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Stopped
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {servers.filter((s: Server) => s.status === "stopped").length}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-purple-600 dark:text-purple-300"
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
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Total Peers
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {servers.reduce((sum, s: Server) => sum + (s.peer_count || 0), 0)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Servers List */}
          {servers.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:border dark:border-gray-700 p-12 text-center">
              <svg
                className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-500 mb-4"
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
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                No servers yet
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                Get started by creating your first WireGuard server.
              </p>
              <button
                onClick={handleCreate}
                className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
              >
                Create Server
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
              {servers.map((server: Server) => (
                <ServerCard
                  key={server.id}
                  server={server}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  onStart={handleStart}
                  onStop={handleStop}
                  onReload={handleReload}
                  onDownloadConfig={handleDownloadConfig}
                  onShowMetrics={handleShowMetrics}
                  isStarting={operatingServerIds.starting.has(server.id)}
                  isStopping={operatingServerIds.stopping.has(server.id)}
                  isReloading={operatingServerIds.reloading.has(server.id)}
                  isSelectable={bulkSelectMode !== "none"}
                  isSelected={selectedServerIds.has(server.id)}
                  onToggleSelect={() => toggleServerSelection(server.id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === "traffic" && (
        <>
          {/* Traffic Overview */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Traffic Overview
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
                        serversMetrics?.current_totals?.total_rx_bytes || 0,
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
                        serversMetrics?.current_totals?.total_tx_bytes || 0,
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
            ) : chartData.length === 0 ? (
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
                    No traffic data available
                  </p>
                  <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                    Metrics will appear here once collected
                  </p>
                </div>
              </div>
            ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-3 gap-6">
                {/* Line Chart - Traffic Over Time */}
                <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                    Traffic Over Time
                  </h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart
                      data={chartData}
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
                      <Legend
                        wrapperStyle={{ color: "#9CA3AF" }}
                        iconType="line"
                      />
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
                        formatter={(
                          value: number,
                          name: string,
                          props: any,
                        ) => [
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
        </>
      )}

      {isFormOpen && (
        <ServerForm
          server={editingServer}
          servers={servers}
          onSubmit={handleSubmit}
          onCancel={() => {
            setIsFormOpen(false);
            setEditingServer(null);
            setFieldErrors({});
          }}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          fieldErrors={fieldErrors}
        />
      )}

      {isImportOpen && (
        <ImportServerDialog
          servers={servers}
          onImport={handleImport}
          onClose={() => setIsImportOpen(false)}
          isPending={importMutation.isPending}
        />
      )}

      {showMetrics && (
        <MetricsModal
          type="server"
          id={showMetrics.id}
          name={showMetrics.name}
          onClose={() => setShowMetrics(null)}
        />
      )}

      {confirmDialog.isOpen && (
        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={confirmDialog.onConfirm}
          onCancel={() => setConfirmDialog({ ...confirmDialog, isOpen: false })}
          type="danger"
        />
      )}
    </div>
  );
}
