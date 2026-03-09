import { useState, useRef, useEffect } from "react";
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "react-toastify";
import {
  trafficTriggersAPI,
  serversAPI,
  peersAPI,
  integrationsAPI,
} from "../services/api";
import type { TrafficTrigger, Server, Peer, Integration } from "../types";
import TrafficTriggerForm from "../components/TrafficTriggerForm";
import ConfirmDialog from "../components/ConfirmDialog";
import ToggleSwitch from "../components/ToggleSwitch";

export default function TrafficTriggers() {
  const [showForm, setShowForm] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState<TrafficTrigger | null>(
    null,
  );
  const [testingTrigger, setTestingTrigger] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    isOpen: boolean;
    trigger: TrafficTrigger | null;
  }>({
    isOpen: false,
    trigger: null,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const queryClient = useQueryClient();
  const observerTarget = useRef<HTMLDivElement>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput);
    }, 500); // Wait 500ms after user stops typing

    return () => clearTimeout(timer);
  }, [searchInput]);

  // Fetch traffic triggers with infinite scroll
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery({
      queryKey: ["traffic-triggers", searchQuery],
      queryFn: ({ pageParam = 0 }) =>
        trafficTriggersAPI.list({
          search: searchQuery || undefined,
          skip: pageParam,
          limit: 50,
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage, allPages) => {
        const currentCount = allPages.reduce(
          (acc, page) => acc + page.length,
          0,
        );
        return lastPage.length === 50 ? currentCount : undefined;
      },
    });

  // Flatten all pages into a single array
  const triggers = data?.pages.flat() || [];

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 },
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Fetch servers and peers for the form
  const { data: servers = [] } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => serversAPI.list(),
  });

  const { data: peers = [] } = useQuery<Peer[]>({
    queryKey: ["peers"],
    queryFn: () => peersAPI.list(),
  });

  const { data: integrations = [] } = useQuery<Integration[]>({
    queryKey: ["integrations"],
    queryFn: () => integrationsAPI.list(),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => trafficTriggersAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traffic-triggers"] });
      toast.success("Traffic trigger deleted successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete trigger";
      toast.error(message);
    },
  });

  // Toggle enabled mutation
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      trafficTriggersAPI.update(id, { enabled }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["traffic-triggers"] });
      toast.success(`Trigger ${variables.enabled ? "enabled" : "disabled"}`);
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to update trigger";
      toast.error(message);
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: (id: number) => trafficTriggersAPI.test(id),
    onSuccess: (data) => {
      setTestingTrigger(null);
      if (data.would_fire) {
        const currentGb = (data.current_bytes / 1024 ** 3).toFixed(2);
        const thresholdGb = (data.threshold_bytes / 1024 ** 3).toFixed(2);
        toast.success(
          `Would fire! Current: ${currentGb} GB / Threshold: ${thresholdGb} GB (${data.exceeded_by_percent?.toFixed(1)}% over)`,
          { autoClose: 5000 },
        );
      } else if (data.in_cooldown) {
        toast.info(
          `In cooldown period. ${data.cooldown_remaining_minutes} minutes remaining.`,
          { autoClose: 4000 },
        );
      } else {
        const currentGb = (data.current_bytes / 1024 ** 3).toFixed(2);
        const thresholdGb = (data.threshold_bytes / 1024 ** 3).toFixed(2);
        toast.info(
          `Would not fire. Current: ${currentGb} GB / Threshold: ${thresholdGb} GB`,
          { autoClose: 4000 },
        );
      }
    },
    onError: (error: any) => {
      setTestingTrigger(null);
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to test trigger";
      toast.error(message);
    },
  });

  const handleAddClick = () => {
    setEditingTrigger(null);
    setShowForm(true);
  };

  const handleEditClick = (trigger: TrafficTrigger) => {
    setEditingTrigger(trigger);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingTrigger(null);
  };

  const handleDelete = (trigger: TrafficTrigger) => {
    setDeleteConfirm({
      isOpen: true,
      trigger,
    });
  };

  const handleConfirmDelete = () => {
    if (deleteConfirm.trigger) {
      deleteMutation.mutate(deleteConfirm.trigger.id);
      setDeleteConfirm({ isOpen: false, trigger: null });
    }
  };

  const handleCancelDelete = () => {
    setDeleteConfirm({ isOpen: false, trigger: null });
  };

  const handleTest = (id: number) => {
    setTestingTrigger(id);
    testMutation.mutate(id);
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const getScopeIcon = (scope: string) => {
    if (scope === "peer") {
      return (
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
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
          />
        </svg>
      );
    } else if (scope === "server") {
      return (
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
      );
    } else {
      return (
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
            d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      );
    }
  };

  const getWindowLabel = (window: string): string => {
    const labels: Record<string, string> = {
      last_hour: "Last Hour",
      last_24_hours: "Last 24 Hours",
      last_7_days: "Last 7 Days",
      last_30_days: "Last 30 Days",
    };
    return labels[window] || window;
  };

  const getDirectionLabel = (direction: string): string => {
    const labels: Record<string, string> = {
      rx_only: "Download (RX)",
      tx_only: "Upload (TX)",
      combined: "Combined (RX+TX)",
    };
    return labels[direction] || direction;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">
          Loading traffic triggers...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Traffic-Based Triggers
          </h1>
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-300 mt-1">
            Monitor traffic usage and trigger notifications when thresholds are
            exceeded
          </p>
        </div>
        <button
          type="button"
          onClick={handleAddClick}
          className="bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base self-start sm:self-auto"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          <span className="hidden sm:inline">Add Trigger</span>
          <span className="sm:hidden">Add</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <input
            type="text"
            placeholder="Search triggers by name, peer, or server..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full px-4 py-2 pl-10 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
          />
          <svg
            className="w-5 h-5 text-gray-400 dark:text-gray-500 absolute left-3 top-1/2 -translate-y-1/2"
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
          {searchInput && (
            <button
              type="button"
              onClick={() => setSearchInput("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
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
      </div>

      {/* Stats Overview */}
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
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Total Triggers
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {triggers.length}
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
                Active Triggers
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {triggers.filter((t) => t.enabled).length}
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
                  d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Total Fired
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {triggers.reduce((sum, t) => sum + t.total_triggers, 0)}
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
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Linked Integrations
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {new Set(triggers.flatMap((t) => t.integration_ids)).size}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Triggers List */}
      {triggers.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center">
          {searchQuery ? (
            // No search results
            <>
              <svg
                className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4"
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
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                No triggers match your search
              </h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                Try adjusting your search terms or clear the search to see all
                triggers.
              </p>
              <button
                type="button"
                onClick={() => setSearchInput("")}
                className="inline-flex items-center gap-2 bg-gray-600 hover:bg-gray-700 dark:hover:bg-gray-500 text-white px-4 py-2 rounded-lg transition-colors"
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
                Clear Search
              </button>
            </>
          ) : (
            // No triggers at all
            <>
              <svg
                className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                No traffic triggers yet
              </h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                Set up your first traffic trigger to monitor bandwidth usage and
                receive alerts when thresholds are exceeded.
              </p>
              <button
                type="button"
                onClick={handleAddClick}
                className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors"
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
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Add Your First Trigger
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {triggers.map((trigger) => (
            <div
              key={trigger.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow border border-transparent dark:border-gray-700"
            >
              <div className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className={`p-2 rounded-lg ${
                        trigger.enabled
                          ? "bg-blue-100 dark:bg-blue-900/50"
                          : "bg-gray-100 dark:bg-gray-700"
                      }`}
                    >
                      <div
                        className={
                          trigger.enabled
                            ? "text-blue-600 dark:text-blue-300"
                            : "text-gray-400 dark:text-gray-500"
                        }
                      >
                        {getScopeIcon(trigger.scope)}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {trigger.name}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                        {trigger.scope}
                        {trigger.peer_name && ` - ${trigger.peer_name}`}
                        {trigger.server_name && ` - ${trigger.server_name}`}
                      </p>
                    </div>
                  </div>
                  <ToggleSwitch
                    checked={trigger.enabled}
                    onChange={(enabled) =>
                      toggleEnabledMutation.mutate({
                        id: trigger.id,
                        enabled,
                      })
                    }
                    label=""
                  />
                </div>

                {/* Threshold Info */}
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <div className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-800">
                    <div className="w-7 h-7 bg-blue-100 dark:bg-blue-900/50 rounded flex items-center justify-center flex-shrink-0">
                      <svg
                        className="w-3.5 h-3.5 text-blue-600 dark:text-blue-300"
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
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Threshold
                      </p>
                      <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                        {formatBytes(trigger.threshold_bytes)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-800">
                    <div className="w-7 h-7 bg-purple-100 dark:bg-purple-900/50 rounded flex items-center justify-center flex-shrink-0">
                      <svg
                        className="w-3.5 h-3.5 text-purple-600 dark:text-purple-300"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Window
                      </p>
                      <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                        {getWindowLabel(trigger.window)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-800">
                    <div className="w-7 h-7 bg-orange-100 dark:bg-orange-900/50 rounded flex items-center justify-center flex-shrink-0">
                      <svg
                        className="w-3.5 h-3.5 text-orange-600 dark:text-orange-300"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                        />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Direction
                      </p>
                      <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                        {getDirectionLabel(trigger.direction)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-800">
                    <div className="w-7 h-7 bg-green-100 dark:bg-green-900/50 rounded flex items-center justify-center flex-shrink-0">
                      <svg
                        className="w-3.5 h-3.5 text-green-600 dark:text-green-300"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 5l7 7-7 7M5 5l7 7-7 7"
                        />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Cooldown
                      </p>
                      <p className="text-xs font-semibold text-gray-900 dark:text-white">
                        {trigger.cooldown_minutes}m
                      </p>
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 mb-4">
                  <div className="flex items-center gap-1">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"
                      />
                    </svg>
                    <span>{trigger.integration_ids.length} integrations</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                      />
                    </svg>
                    <span>{trigger.total_triggers} times fired</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    type="button"
                    onClick={() => handleTest(trigger.id)}
                    disabled={testingTrigger === trigger.id}
                    className="flex-1 px-3 py-2 text-sm font-medium text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {testingTrigger === trigger.id ? "Testing..." : "Test"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleEditClick(trigger)}
                    className="flex-1 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(trigger)}
                    className="flex-1 px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Infinite scroll trigger */}
          <div ref={observerTarget} className="col-span-full h-4" />
        </div>
      )}

      {/* Loading indicator */}
      {isFetchingNextPage && (
        <div className="py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
          Loading more triggers...
        </div>
      )}

      {/* How it Works */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mt-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          How Traffic Triggers Work
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="text-center">
            <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-blue-600 dark:text-blue-300">
                1
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Monitor Traffic
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              System monitors network traffic over rolling time windows
            </p>
          </div>

          <div className="text-center">
            <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-purple-600 dark:text-purple-300">
                2
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Check Thresholds
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Compares usage against configured thresholds automatically
            </p>
          </div>

          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 dark:bg-green-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-green-600 dark:text-green-300">
                3
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Fire Integrations
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Triggers notifications when thresholds exceeded (respects
              cooldown)
            </p>
          </div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
            Example Scenarios:
          </h3>
          <ul className="text-sm text-gray-600 dark:text-gray-300 space-y-2">
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              <span>Alert when a peer uses more than 5 GB in 24 hours</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              <span>
                Notify when server traffic exceeds 100 GB in the last hour
                (spike detection)
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">•</span>
              <span>
                Track global VPN usage and alert when weekly total exceeds 1 TB
              </span>
            </li>
          </ul>
        </div>
      </div>

      {/* Trigger Form Modal */}
      {showForm && (
        <TrafficTriggerForm
          trigger={editingTrigger}
          servers={servers}
          peers={peers}
          integrations={integrations}
          onClose={handleFormClose}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm.isOpen && deleteConfirm.trigger && (
        <ConfirmDialog
          isOpen={deleteConfirm.isOpen}
          title="Delete Traffic Trigger"
          message={`Are you sure you want to delete "${deleteConfirm.trigger.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
          type="danger"
        />
      )}
    </div>
  );
}
