import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { pluginsAPI } from "../services/api";
import ConfirmDialog from "../components/ConfirmDialog";

interface Plugin {
  id: number;
  name: string;
  version: string;
  description: string | null;
  author: string | null;
  module_name: string;
  file_path: string;
  config_schema: any;
  config: any;
  enabled: boolean;
  loaded: boolean;
  subscribed_events: string[] | null;
  requirements: string[] | null;
  total_invocations: number;
  total_errors: number;
  last_invoked_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
  created_at: string;
  updated_at: string | null;
}

interface PluginListResponse {
  plugins: Plugin[];
  total: number;
}

export default function Plugins() {
  const [deleteConfirm, setDeleteConfirm] = useState<{
    isOpen: boolean;
    plugin: Plugin | null;
  }>({
    isOpen: false,
    plugin: null,
  });
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const queryClient = useQueryClient();

  // Fetch plugins
  const { data, isLoading } = useQuery<PluginListResponse>({
    queryKey: ["plugins"],
    queryFn: () => pluginsAPI.list(),
  });

  const plugins = data?.plugins || [];
  const total = data?.total || 0;

  // Discover plugins mutation
  const discoverMutation = useMutation({
    mutationFn: () => pluginsAPI.discover(),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["plugins"] });
      // Show info notification if no new plugins found
      if (response.newly_discovered === 0) {
        toast.info("No more plugins found");
      } else {
        toast.success(response.message || "Plugins discovered successfully");
      }
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to discover plugins";
      toast.error(message);
    },
  });

  // Toggle enabled mutation
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      enabled ? pluginsAPI.enable(id) : pluginsAPI.disable(id),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["plugins"] });
      toast.success(
        `Plugin ${variables.enabled ? "enabled" : "disabled"} successfully`,
      );
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to update plugin";
      toast.error(message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => pluginsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plugins"] });
      toast.success("Plugin deleted successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete plugin";
      toast.error(message);
    },
  });

  const handleDiscover = () => {
    discoverMutation.mutate();
  };

  const handleDelete = (plugin: Plugin) => {
    setDeleteConfirm({
      isOpen: true,
      plugin,
    });
  };

  const handleConfirmDelete = () => {
    if (deleteConfirm.plugin) {
      deleteMutation.mutate(deleteConfirm.plugin.id);
      setDeleteConfirm({ isOpen: false, plugin: null });
    }
  };

  const handleCancelDelete = () => {
    setDeleteConfirm({ isOpen: false, plugin: null });
  };

  const getPluginIcon = () => {
    // Use puzzle piece icon for plugins
    return (
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
          d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"
        />
      </svg>
    );
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">
          Loading plugins...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Plugins
        </h1>
        <button
          onClick={handleDiscover}
          disabled={discoverMutation.isPending}
          className="bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          {discoverMutation.isPending ? "Discovering..." : "Discover Plugins"}
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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
                  d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Total Plugins
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {total}
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
                Enabled Plugins
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {plugins.filter((p) => p.enabled).length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 dark:bg-yellow-900/50 rounded-lg flex items-center justify-center">
              <svg
                className="w-5 h-5 text-yellow-600 dark:text-yellow-300"
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
                Total Invocations
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {plugins.reduce((sum, p) => sum + p.total_invocations, 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Plugins List */}
      {plugins.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center">
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
              d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"
            />
          </svg>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No plugins discovered yet
          </h3>
          <p className="text-gray-600 dark:text-gray-300 mb-4">
            Click "Discover Plugins" to scan for available plugins in your
            plugins directory.
          </p>
          <button
            onClick={handleDiscover}
            disabled={discoverMutation.isPending}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            {discoverMutation.isPending
              ? "Discovering..."
              : "Discover Plugins"}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {plugins.map((plugin) => (
            <div
              key={plugin.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow border border-transparent dark:border-gray-700"
            >
              <div className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className={`p-2 rounded-lg ${
                        plugin.enabled
                          ? "bg-blue-100 dark:bg-blue-900/50"
                          : "bg-gray-100 dark:bg-gray-700"
                      }`}
                    >
                      <div
                        className={
                          plugin.enabled
                            ? "text-blue-600 dark:text-blue-300"
                            : "text-gray-400 dark:text-gray-500"
                        }
                      >
                        {getPluginIcon()}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {plugin.name}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        v{plugin.version}
                        {plugin.author && ` by ${plugin.author}`}
                      </p>
                    </div>
                  </div>
                  {/* Toggle Switch */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleEnabledMutation.mutate({
                        id: plugin.id,
                        enabled: !plugin.enabled,
                      });
                    }}
                    disabled={toggleEnabledMutation.isPending}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 disabled:opacity-50 disabled:cursor-not-allowed ${
                      plugin.enabled
                        ? "bg-blue-600"
                        : "bg-gray-300 dark:bg-gray-600"
                    }`}
                    title={plugin.enabled ? "Disable plugin" : "Enable plugin"}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        plugin.enabled ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>

                {/* Description */}
                {plugin.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                    {plugin.description}
                  </p>
                )}

                {/* Status Badges */}
                <div className="flex items-center gap-2 mb-4">
                  {plugin.subscribed_events &&
                    plugin.subscribed_events.length > 0 && (
                      <span className="px-2 py-1 text-xs rounded-full bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300">
                        {plugin.subscribed_events.includes("*")
                          ? "All events"
                          : `${plugin.subscribed_events.length} event${plugin.subscribed_events.length !== 1 ? "s" : ""}`}
                      </span>
                    )}
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                  <div>
                    <p className="text-gray-500 dark:text-gray-400">
                      Invocations
                    </p>
                    <p className="font-semibold text-gray-900 dark:text-white">
                      {plugin.total_invocations}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 dark:text-gray-400">Errors</p>
                    <p
                      className={`font-semibold ${
                        plugin.total_errors > 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-gray-900 dark:text-white"
                      }`}
                    >
                      {plugin.total_errors}
                    </p>
                  </div>
                </div>

                {/* Last Error Message */}
                {plugin.last_error_message && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2 mb-4">
                    <p className="text-xs text-red-800 dark:text-red-300 font-medium mb-1">
                      Last Error:
                    </p>
                    <p className="text-xs text-red-700 dark:text-red-400 break-words">
                      {plugin.last_error_message}
                    </p>
                    <p className="text-xs text-red-600 dark:text-red-500 mt-1">
                      {formatDate(plugin.last_error_at)}
                    </p>
                  </div>
                )}

                {/* File Path */}
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-4 break-all">
                  <span className="font-medium">Module:</span>{" "}
                  {plugin.module_name}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={() => setSelectedPlugin(plugin)}
                    className="flex-1 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                  >
                    View Details
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(plugin);
                    }}
                    className="flex-1 px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mt-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          About Plugins
        </h2>
        <p className="text-gray-600 dark:text-gray-300 mb-4">
          Plugins extend Linguard's functionality by subscribing to events and
          executing custom code. They can integrate with external services,
          automate tasks, and add new features to your VPN management workflow.
        </p>
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
            Plugin Lifecycle:
          </h3>
          <div className="text-sm text-gray-600 dark:text-gray-300 space-y-2">
            <div className="flex items-start gap-2">
              <span className="font-medium text-blue-600 dark:text-blue-400">
                1. Discovery:
              </span>
              <span>
                Plugins are discovered from the plugins directory and registered
                in the database
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="font-medium text-green-600 dark:text-green-400">
                2. Enable:
              </span>
              <span>
                When enabled, the plugin is loaded into memory and can respond
                to events
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="font-medium text-purple-600 dark:text-purple-400">
                3. Invoke:
              </span>
              <span>
                When subscribed events occur, the plugin's handler is executed
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="font-medium text-yellow-600 dark:text-yellow-400">
                4. Disable:
              </span>
              <span>
                Disabled plugins are unloaded from memory but remain in the
                database
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirm.isOpen && deleteConfirm.plugin && (
        <ConfirmDialog
          isOpen={deleteConfirm.isOpen}
          title="Delete Plugin"
          message={`Are you sure you want to delete "${deleteConfirm.plugin.name}"? This will remove it from the database but not delete the plugin files.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
          type="danger"
        />
      )}

      {/* Plugin Details Dialog */}
      {selectedPlugin && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-md"
          onClick={() => setSelectedPlugin(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div
                  className={`p-3 rounded-lg ${
                    selectedPlugin.enabled
                      ? "bg-blue-100 dark:bg-blue-900/50"
                      : "bg-gray-100 dark:bg-gray-700"
                  }`}
                >
                  <div
                    className={
                      selectedPlugin.enabled
                        ? "text-blue-600 dark:text-blue-300"
                        : "text-gray-400 dark:text-gray-500"
                    }
                  >
                    {getPluginIcon()}
                  </div>
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {selectedPlugin.name}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    v{selectedPlugin.version}
                    {selectedPlugin.author && ` by ${selectedPlugin.author}`}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedPlugin(null)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <svg
                  className="w-6 h-6 text-gray-500 dark:text-gray-400"
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

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Description */}
              {selectedPlugin.description && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    Description
                  </h3>
                  <p className="text-gray-600 dark:text-gray-300">
                    {selectedPlugin.description}
                  </p>
                </div>
              )}

              {/* Status */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                  Status
                </h3>
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                    Enabled
                  </p>
                  <p className="font-semibold">
                    <span
                      className={
                        selectedPlugin.enabled
                          ? "text-green-600 dark:text-green-400"
                          : "text-gray-600 dark:text-gray-400"
                      }
                    >
                      {selectedPlugin.enabled ? "Yes" : "No"}
                    </span>
                  </p>
                </div>
              </div>

              {/* Event Handlers */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                  Event Handlers
                </h3>
                {selectedPlugin.subscribed_events &&
                selectedPlugin.subscribed_events.length > 0 ? (
                  <div className="space-y-2">
                    {selectedPlugin.subscribed_events.map((event, idx) => (
                      <div
                        key={idx}
                        className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-3 flex items-center gap-3"
                      >
                        <svg
                          className="w-5 h-5 text-purple-600 dark:text-purple-400 flex-shrink-0"
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
                        <div className="flex-1">
                          <code className="text-sm font-mono text-purple-900 dark:text-purple-200">
                            {event}
                          </code>
                          {event === "*" && (
                            <p className="text-xs text-purple-700 dark:text-purple-300 mt-1">
                              Wildcard - handles all events
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 italic">
                    No event handlers configured
                  </p>
                )}
              </div>

              {/* Statistics */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                  Statistics
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      Total Invocations
                    </p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {selectedPlugin.total_invocations}
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      Total Errors
                    </p>
                    <p
                      className={`text-2xl font-bold ${
                        selectedPlugin.total_errors > 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-gray-900 dark:text-white"
                      }`}
                    >
                      {selectedPlugin.total_errors}
                    </p>
                  </div>
                </div>
                {selectedPlugin.last_invoked_at && (
                  <div className="mt-4 bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      Last Invoked
                    </p>
                    <p className="text-sm text-gray-900 dark:text-white">
                      {formatDate(selectedPlugin.last_invoked_at)}
                    </p>
                  </div>
                )}
              </div>

              {/* Last Error */}
              {selectedPlugin.last_error_message && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                    Last Error
                  </h3>
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                    <p className="text-sm text-red-800 dark:text-red-300 mb-2 break-words">
                      {selectedPlugin.last_error_message}
                    </p>
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {formatDate(selectedPlugin.last_error_at)}
                    </p>
                  </div>
                </div>
              )}

              {/* Technical Details */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                  Technical Details
                </h3>
                <div className="space-y-3">
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      Module Name
                    </p>
                    <code className="text-sm font-mono text-gray-900 dark:text-white">
                      {selectedPlugin.module_name}
                    </code>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      File Path
                    </p>
                    <code className="text-sm font-mono text-gray-900 dark:text-white break-all">
                      {selectedPlugin.file_path}
                    </code>
                  </div>
                  {selectedPlugin.requirements &&
                    selectedPlugin.requirements.length > 0 && (
                      <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                          Dependencies
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {selectedPlugin.requirements.map((req, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded font-mono"
                            >
                              {req}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              </div>

              {/* Timestamps */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                  Timestamps
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                      Created
                    </p>
                    <p className="text-sm text-gray-900 dark:text-white">
                      {formatDate(selectedPlugin.created_at)}
                    </p>
                  </div>
                  {selectedPlugin.updated_at && (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                        Updated
                      </p>
                      <p className="text-sm text-gray-900 dark:text-white">
                        {formatDate(selectedPlugin.updated_at)}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 p-6 flex justify-end">
              <button
                onClick={() => setSelectedPlugin(null)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
