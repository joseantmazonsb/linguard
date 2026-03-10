import { useState, useRef, useEffect } from "react";
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
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
import { peersAPI, serversAPI, metricsAPI, healthAPI } from "../services/api";
import PeerForm from "../components/PeerForm";
import PeerCard from "../components/PeerCard";
import CustomSelect from "../components/CustomSelect";
import MigratePeerDialog from "../components/MigratePeerDialog";
import ImportPeerDialog from "../components/ImportPeerDialog";
import MetricsModal from "../components/MetricsModal";
import ConfirmDialog from "../components/ConfirmDialog";
import AddMenuButton from "../components/AddMenuButton";
import BulkActionsButton from "../components/BulkActionsButton";
import type { Server, Peer } from "../types";
import type { FieldErrors } from "../utils/errorUtils";
import {
  parseValidationErrors,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from "../utils/errorUtils";

type TimeRange = 24 | 168 | 720;

export default function Peers() {
  const [activeTab, setActiveTab] = useState<"peers" | "traffic">("peers");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [editingPeer, setEditingPeer] = useState<Peer | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [selectedServerId, setSelectedServerId] = useState<number | null>(null);
  const [showQRCode, setShowQRCode] = useState<{
    peerId: number;
    peerName: string;
    imageDataUrl: string;
  } | null>(null);
  const [migratingPeer, setMigratingPeer] = useState<Peer | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showMetrics, setShowMetrics] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>(24);
  const [bulkSelectMode, setBulkSelectMode] = useState<
    "none" | "delete" | "download"
  >("none");
  const [selectedPeerIds, setSelectedPeerIds] = useState<Set<number>>(
    new Set(),
  );
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string | React.ReactNode;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });
  const queryClient = useQueryClient();

  // Cleanup blob URL when QR code modal is closed
  useEffect(() => {
    return () => {
      if (showQRCode?.imageDataUrl) {
        URL.revokeObjectURL(showQRCode.imageDataUrl);
      }
    };
  }, [showQRCode?.imageDataUrl]);

  // Fetch peers with infinite scroll
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
  } = useInfiniteQuery({
    queryKey: ["peers", selectedServerId],
    queryFn: ({ pageParam = 0 }) =>
      peersAPI.list(selectedServerId || undefined, pageParam, 50),
    getNextPageParam: (lastPage, allPages) => {
      // If last page has 50 items, there might be more
      if (lastPage.length === 50) {
        return allPages.length * 50; // skip = pages * limit
      }
      return undefined; // No more pages
    },
    initialPageParam: 0,
  });

  // Flatten pages into single array
  const peers = data?.pages.flat() || [];

  // Create ref for infinite scroll sentinel
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!loadMoreRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Fetch servers for filtering
  const { data: servers = [] } = useQuery({
    queryKey: ["servers"],
    queryFn: serversAPI.list,
  });

  // Fetch peers aggregate metrics
  const { data: peersMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["peers-aggregate-metrics", timeRange],
    queryFn: () => metricsAPI.getPeersAggregateMetrics(timeRange),
  });

  // Fetch health status to gate WireGuard-dependent actions
  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: healthAPI.check,
    refetchInterval: 30000,
  });
  const wgUnavailable = healthData?.checks?.wireguard?.status !== "healthy";

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
    peersMetrics?.hourly_metrics.map((metric: any) => {
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

  // Prepare bar chart data for peer comparison
  const peerComparisonData =
    peersMetrics?.peers.map((peer: any) => ({
      name:
        peer.name.length > 15 ? peer.name.substring(0, 15) + "..." : peer.name,
      fullName: peer.name,
      rx: peer.rx_bytes / (1024 * 1024),
      tx: peer.tx_bytes / (1024 * 1024),
    })) || [];

  // Create peer mutation
  const createMutation = useMutation({
    mutationFn: peersAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      setIsFormOpen(false);
      setEditingPeer(null);
      setFieldErrors({});
      toast.success("Peer created successfully");
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to create peer"));
      }
    },
  });

  // Update peer mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      peersAPI.update(id, data),
    onSuccess: (updatedPeer) => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      setIsFormOpen(false);
      setEditingPeer(null);
      setFieldErrors({});
      toast.success("Peer updated successfully");
      
      // Check if the peer's server is running and show reload warning
      const server = servers?.find((s: Server) => s.id === updatedPeer.server_id);
      if (server && server.status === "running") {
        toast.warning(
          `Server "${server.name}" is running. Reload the server to apply changes.`,
          {
            autoClose: 8000,
            onClick: () => {
              // Reload the server when notification is clicked
              serversAPI.reload(server.id)
                .then(() => {
                  queryClient.invalidateQueries({ queryKey: ["servers"] });
                  toast.success(`Server "${server.name}" reloaded successfully`);
                })
                .catch((error: any) => {
                  const message = error.response?.data?.detail || "Failed to reload server";
                  toast.error(message);
                });
            },
          }
        );
      }
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to update peer"));
      }
    },
  });

  // Delete peer mutation
  const deleteMutation = useMutation({
    mutationFn: peersAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      toast.success("Peer deleted successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete peer";
      toast.error(message);
    },
  });

  // Migrate peer mutation
  const migrateMutation = useMutation({
    mutationFn: ({ id, migrationData }: { id: number; migrationData: any }) =>
      peersAPI.migrate(id, migrationData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      setMigratingPeer(null);
      toast.success(
        "Peer migrated successfully! Please update the client configuration.",
      );
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to migrate peer";
      toast.error(message);
    },
  });

  // Import peer mutation
  const importMutation = useMutation({
    mutationFn: (data: any) => peersAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      setIsImportOpen(false);
      toast.success("Peer imported successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to import peer";
      toast.error(message);
    },
  });

  // Toggle enabled mutation
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      peersAPI.update(id, { enabled }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["peers"] });
      toast.success(
        `Peer ${variables.enabled ? "enabled" : "disabled"} successfully`,
      );
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to update peer";
      toast.error(message);
    },
  });

  const handleCreate = () => {
    setEditingPeer(null);
    setFieldErrors({});
    setIsFormOpen(true);
  };

  const handleEdit = (peer: Peer) => {
    setEditingPeer(peer);
    setFieldErrors({});
    setIsFormOpen(true);
  };

  const handleDelete = async (id: number, name: string) => {
    setConfirmDialog({
      isOpen: true,
      title: "Delete Peer",
      message: (
        <div className="space-y-3">
          <p>Are you sure you want to delete peer <strong>"{name}"</strong>?</p>
          <p className="font-bold">This action cannot be undone.</p>
        </div>
      ),
      onConfirm: () => {
        deleteMutation.mutate(id);
        setConfirmDialog({ ...confirmDialog, isOpen: false });
      },
    });
  };

  const togglePeerSelection = (peerId: number) => {
    const newSelected = new Set(selectedPeerIds);
    if (newSelected.has(peerId)) {
      newSelected.delete(peerId);
    } else {
      newSelected.add(peerId);
    }
    setSelectedPeerIds(newSelected);
  };

  const handleBulkDelete = () => {
    if (bulkSelectMode === "none") {
      // Enter selection mode
      setBulkSelectMode("delete");
      setSelectedPeerIds(new Set());
    } else if (bulkSelectMode === "delete") {
      if (selectedPeerIds.size === 0) {
        // Exit if nothing selected
        setBulkSelectMode("none");
        return;
      }

      // Get names of selected peers for display
      const peerNames = peers
        .filter((p: Peer) => selectedPeerIds.has(p.id))
        .map((p: Peer) => p.name)
        .join(", ");

      // Show confirmation
      setConfirmDialog({
        isOpen: true,
        title: "Delete Peers",
        message: (
          <div className="space-y-3">
            <p>Are you sure you want to delete <strong>{selectedPeerIds.size} peer{selectedPeerIds.size !== 1 ? 's' : ''}</strong>?</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">({peerNames})</p>
            <p className="font-bold">This action cannot be undone.</p>
          </div>
        ),
        onConfirm: async () => {
          const deletePromises = Array.from(selectedPeerIds).map((id) =>
            deleteMutation.mutateAsync(id),
          );
          await Promise.all(deletePromises);
          toast.success(`${selectedPeerIds.size} peer(s) deleted`);
          setBulkSelectMode("none");
          setSelectedPeerIds(new Set());
          setConfirmDialog({ ...confirmDialog, isOpen: false });
        },
      });
    }
  };

  const handleBulkDownload = async () => {
    if (bulkSelectMode === "none") {
      // Enter selection mode
      setBulkSelectMode("download");
      setSelectedPeerIds(new Set());
    } else if (bulkSelectMode === "download") {
      if (selectedPeerIds.size === 0) {
        // Exit if nothing selected
        setBulkSelectMode("none");
        return;
      }

      // Download all selected configs
      const downloadPromises = Array.from(selectedPeerIds).map(async (id) => {
        const peer = peers.find((p: Peer) => p.id === id);
        if (peer) {
          await handleDownloadConfig(id, peer.name);
        }
      });
      await Promise.all(downloadPromises);
      toast.success(`${selectedPeerIds.size} config(s) downloaded`);
      setBulkSelectMode("none");
      setSelectedPeerIds(new Set());
    }
  };

  const handleCancelBulkOperation = () => {
    setBulkSelectMode("none");
    setSelectedPeerIds(new Set());
  };

  const handleConfirmBulkOperation = () => {
    switch (bulkSelectMode) {
      case "delete":
        handleBulkDelete();
        break;
      case "download":
        handleBulkDownload();
        break;
    }
  };

  const handleSubmit = (data: any) => {
    if (editingPeer) {
      updateMutation.mutate({ id: editingPeer.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleMigrate = (peer: Peer) => {
    setMigratingPeer(peer);
  };

  const handleMigrateConfirm = (
    peerId: number,
    migrationData: any,
    onSuccess?: () => void,
    onError?: (error: any) => void
  ) => {
    migrateMutation.mutate(
      { id: peerId, migrationData },
      {
        onSuccess: () => {
          onSuccess?.();
        },
        onError: (error: any) => {
          onError?.(error);
        },
      }
    );
  };

  const handleToggleEnabled = (id: number, enabled: boolean) => {
    toggleEnabledMutation.mutate({ id, enabled });
  };

  const handleShowQRCode = async (peerId: number, peerName: string) => {
    try {
      const qrCodeBlob = await peersAPI.getQRCode(peerId);
      const imageDataUrl = URL.createObjectURL(qrCodeBlob);
      setShowQRCode({ peerId, peerName, imageDataUrl });
    } catch (error) {
      console.error("Failed to load QR code:", error);
      toast.error("Failed to load QR code");
    }
  };

  const handleDownloadConfig = async (id: number, name: string) => {
    try {
      const config = await peersAPI.getConfig(id);
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

  const getServerName = (serverId: number) => {
    const server = servers.find((s: Server) => s.id === serverId);
    return server?.name || "Unknown";
  };

  // Filter peers based on search query
  const filteredPeers = peers.filter((peer: Peer) => {
    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    const searchableFields = [
      peer.name?.toLowerCase() || "",
      peer.description?.toLowerCase() || "",
      peer.ipv4_address?.toLowerCase() || "",
      peer.ipv6_address?.toLowerCase() || "",
      peer.allowed_ips?.toLowerCase() || "",
    ];

    return searchableFields.some((field) => field.includes(query));
  });

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500 dark:text-gray-400">
            Loading peers...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          Error loading peers: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
          Peers
        </h1>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab("peers")}
              className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "peers"
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
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
                Peers
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
      {activeTab === "peers" && (
        <>
          {/* Action Buttons */}
          <div className="flex items-center justify-start gap-3 mb-4">
            {bulkSelectMode !== "none" ? (
              /* Selection Mode - Show Cancel and Confirm buttons */
              <>
                <button
                  onClick={handleCancelBulkOperation}
                  className="bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base"
                >
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
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                  <span>Cancel</span>
                </button>
                <button
                  onClick={handleConfirmBulkOperation}
                  disabled={selectedPeerIds.size === 0}
                  className={`${
                    bulkSelectMode === "delete"
                      ? "bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600"
                      : "bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-600"
                  } disabled:bg-gray-400 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base`}
                >
                  {bulkSelectMode === "delete" && (
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
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  )}
                  {bulkSelectMode === "download" && (
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
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                  )}
                  <span>
                    {bulkSelectMode === "delete" &&
                      `Delete${selectedPeerIds.size > 0 ? ` (${selectedPeerIds.size})` : ""}`}
                    {bulkSelectMode === "download" &&
                      `Download${selectedPeerIds.size > 0 ? ` (${selectedPeerIds.size})` : ""}`}
                  </span>
                </button>
              </>
            ) : (
              /* Normal Mode - Show Add and Bulk Actions buttons */
              <>
                <AddMenuButton
                  onAdd={handleCreate}
                  onImport={() => setIsImportOpen(true)}
                  isDisabled={servers.length === 0 || wgUnavailable}
                  disabledTitle={wgUnavailable ? "WireGuard is not installed" : "Create a server first before adding peers"}
                  isImportDisabled={
                    servers.length === 0 || wgUnavailable || importMutation.isPending
                  }
                  importDisabledTitle={wgUnavailable ? "WireGuard is not installed" : "Create a server first before importing peers"}
                />
                {peers.length > 0 && (
                  <BulkActionsButton
                    onDownload={handleBulkDownload}
                    onDelete={handleBulkDelete}
                  />
                )}
              </>
            )}
          </div>

          {/* WireGuard unavailable warning banner */}
          {wgUnavailable && (
            <div className="mb-6 flex items-start gap-3 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-yellow-800 dark:border-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300">
              <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <div>
                <p className="font-semibold">WireGuard unavailable — peers cannot be created or imported</p>
                {healthData?.checks?.wireguard?.message && (
                  <p className="mt-0.5 text-sm">{healthData.checks.wireguard.message}</p>
                )}
              </div>
            </div>
          )}

          {/* Stats Overview - Hidden during selection mode */}
          {bulkSelectMode === "none" && (
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
                        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Total Peers
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {peers.length}
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
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Active
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {peers.filter((p: Peer) => p.enabled).length}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-purple-600 dark:text-purple-300"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path fillRule="evenodd" d="M17.778 8.222c-4.296-4.296-11.26-4.296-15.556 0A1 1 0 01.808 6.808c5.076-5.077 13.308-5.077 18.384 0a1 1 0 01-1.414 1.414zM14.95 11.05a7 7 0 00-9.9 0 1 1 0 01-1.414-1.414 9 9 0 0112.728 0 1 1 0 01-1.414 1.414zM12.12 13.88a3 3 0 00-4.242 0 1 1 0 01-1.415-1.415 5 5 0 017.072 0 1 1 0 01-1.415 1.415zM9 16a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Connected
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {peers.filter((p: Peer) => p.is_online).length}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-orange-100 dark:bg-orange-900/50 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-orange-600 dark:text-orange-300"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Offline
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {peers.filter((p: Peer) => !p.is_online).length}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Server Filter - Hidden during selection mode */}
          {bulkSelectMode === "none" && (
            <div className="mb-6">
              <CustomSelect
                value={selectedServerId || ""}
                onChange={(value) =>
                  setSelectedServerId(value ? Number(value) : null)
                }
                options={[
                  { value: "", label: "All Servers" },
                  ...servers.map((server: Server) => ({
                    value: server.id,
                    label: server.name,
                  })),
                ]}
                placeholder="Filter by server"
                className="w-full sm:w-64"
              />
            </div>
          )}

          {/* Search Bar - Hidden during selection mode */}
          {bulkSelectMode === "none" && peers.length > 0 && (
            <div className="mb-6">
              <div className="relative max-w-md">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg
                    className="w-5 h-5 text-gray-400 dark:text-gray-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name, IP, or description..."
                  className="w-full pl-10 pr-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600 focus:border-transparent"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
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
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>
              {searchQuery && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  Found {filteredPeers.length} peer
                  {filteredPeers.length !== 1 ? "s" : ""} matching "
                  {searchQuery}"
                </p>
              )}
            </div>
          )}

          {/* Peers List */}
          {peers.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900/50 p-12 text-center border dark:border-gray-700">
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
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                No peers yet
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                {selectedServerId
                  ? "No peers on this server."
                  : servers.length === 0
                    ? "Create a server first before adding peers."
                    : wgUnavailable
                      ? "WireGuard is not installed. Install it to create peers."
                      : "Get started by creating your first WireGuard peer."}
              </p>
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={handleCreate}
                  disabled={servers.length === 0 || wgUnavailable}
                  className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg transition-colors"
                  title={
                    wgUnavailable
                      ? "WireGuard is not installed"
                      : servers.length === 0
                        ? "Create a server first before adding peers"
                        : undefined
                  }
                >
                  Create
                </button>
                <button
                  onClick={() => setIsImportOpen(true)}
                  disabled={servers.length === 0 || wgUnavailable || importMutation.isPending}
                  className="bg-white hover:bg-gray-50 dark:bg-gray-700 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 px-6 py-2 rounded-lg transition-colors"
                  title={
                    wgUnavailable
                      ? "WireGuard is not installed"
                      : servers.length === 0
                        ? "Create a server first before importing peers"
                        : undefined
                  }
                >
                  Import
                </button>
              </div>
            </div>
          ) : filteredPeers.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900/50 p-12 text-center border dark:border-gray-700">
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
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                No peers found
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                No peers match your search "{searchQuery}". Try a different
                search term.
              </p>
              <button
                onClick={() => setSearchQuery("")}
                className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
              >
                Clear Search
              </button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {filteredPeers.map((peer: Peer) => (
                  <PeerCard
                    key={peer.id}
                    peer={peer}
                    serverName={getServerName(peer.server_id)}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    onMigrate={handleMigrate}
                    onShowQRCode={handleShowQRCode}
                    onDownloadConfig={handleDownloadConfig}
                    onShowMetrics={handleShowMetrics}
                    onToggleEnabled={handleToggleEnabled}
                    isSelectable={bulkSelectMode !== "none"}
                    isSelected={selectedPeerIds.has(peer.id)}
                    onToggleSelect={() => togglePeerSelection(peer.id)}
                  />
                ))}
              </div>

              {/* Infinite Scroll Sentinel */}
              {!searchQuery && peers.length > 0 && (
                <div ref={loadMoreRef} className="py-8 text-center">
                  {isFetchingNextPage ? (
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-6 h-6 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      <span className="text-gray-600 dark:text-gray-400">
                        Loading more peers...
                      </span>
                    </div>
                  ) : hasNextPage ? (
                    <span className="text-gray-500 dark:text-gray-400">
                      Scroll for more
                    </span>
                  ) : peers.length >= 50 ? (
                    <span className="text-gray-500 dark:text-gray-400">
                      No more peers
                    </span>
                  ) : null}
                </div>
              )}
            </>
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
                    Total Received (Peers)
                  </span>
                </div>
                <p className="text-2xl font-bold text-green-900 dark:text-green-100">
                  {metricsLoading
                    ? "Loading..."
                    : formatBytes(
                        peersMetrics?.current_totals?.total_rx_bytes || 0,
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
                        peersMetrics?.current_totals?.total_tx_bytes || 0,
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
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                        formatter={(
                          value: number,
                          name: string,
                          props: any,
                        ) => [
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
        </>
      )}

      {isFormOpen && (
        <PeerForm
          peer={editingPeer}
          servers={servers}
          onSubmit={handleSubmit}
          onCancel={() => {
            setIsFormOpen(false);
            setEditingPeer(null);
            setFieldErrors({});
          }}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          fieldErrors={fieldErrors}
        />
      )}

      {showQRCode && (
        <div
          className="fixed inset-0 bg-black/30 dark:bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowQRCode(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl dark:shadow-gray-900/50 max-w-md w-full p-6 border dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                QR Code - {showQRCode.peerName}
              </h2>
              <button
                onClick={() => setShowQRCode(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg
                  className="w-6 h-6"
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
              </button>
            </div>
            <div className="flex justify-center bg-white dark:bg-white p-4 rounded">
              <img
                src={showQRCode.imageDataUrl}
                alt="QR Code"
                className="max-w-full h-auto bg-white"
              />
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 text-center mt-4">
              Scan this QR code with the WireGuard mobile app to import the
              configuration.
            </p>
          </div>
        </div>
      )}

      {migratingPeer && (
        <MigratePeerDialog
          peer={migratingPeer}
          currentServer={
            servers.find((s: Server) => s.id === migratingPeer.server_id)!
          }
          availableServers={servers}
          onMigrate={handleMigrateConfirm}
          onClose={() => setMigratingPeer(null)}
          isPending={migrateMutation.isPending}
        />
      )}

      {isImportOpen && (
        <ImportPeerDialog
          servers={servers}
          selectedServerId={selectedServerId || undefined}
          onImport={handleImport}
          onClose={() => setIsImportOpen(false)}
          isPending={importMutation.isPending}
        />
      )}

      {showMetrics && (
        <MetricsModal
          type="peer"
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
