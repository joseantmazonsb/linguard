import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { integrationsAPI, pluginsAPI } from "../services/api";
import type { Integration, IntegrationType } from "../types";
import IntegrationForm from "../components/IntegrationForm";
import ConfirmDialog from "../components/ConfirmDialog";
import ToggleSwitch from "../components/ToggleSwitch";

export default function Integrations() {
  const [showForm, setShowForm] = useState(false);
  const [editingIntegration, setEditingIntegration] =
    useState<Integration | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    isOpen: boolean;
    integration: Integration | null;
  }>({
    isOpen: false,
    integration: null,
  });
  const queryClient = useQueryClient();

  // Fetch integrations
  const { data: integrations = [], isLoading } = useQuery<Integration[]>({
    queryKey: ["integrations"],
    queryFn: () => integrationsAPI.list(),
  });

  // Fetch integration types
  const { data: integrationTypes = [] } = useQuery<IntegrationType[]>({
    queryKey: ["integration-types"],
    queryFn: () => integrationsAPI.getTypes(),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => integrationsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      toast.success("Integration deleted successfully");
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to delete integration";
      toast.error(message);
    },
  });

  // Toggle enabled mutation
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      integrationsAPI.update(id, { enabled }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      toast.success(
        `Integration ${variables.enabled ? "enabled" : "disabled"}`,
      );
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to update integration";
      toast.error(message);
    },
  });

  // Discover plugins mutation
  const discoverPluginsMutation = useMutation({
    mutationFn: () => pluginsAPI.discover(),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["integration-types"] });
      // Show info notification if no new plugins found
      if (data.newly_discovered === 0) {
        toast.info("No more plugins found");
      } else {
        toast.success(
          data.message || `Discovered ${data.newly_discovered} new plugin(s)`,
        );
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

  const handleAddClick = () => {
    setEditingIntegration(null);
    setShowForm(true);
  };

  const handleEditClick = (integration: Integration) => {
    setEditingIntegration(integration);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingIntegration(null);
  };

  const handleDelete = (integration: Integration) => {
    setDeleteConfirm({
      isOpen: true,
      integration,
    });
  };

  const handleConfirmDelete = () => {
    if (deleteConfirm.integration) {
      deleteMutation.mutate(deleteConfirm.integration.id);
      setDeleteConfirm({ isOpen: false, integration: null });
    }
  };

  const handleCancelDelete = () => {
    setDeleteConfirm({ isOpen: false, integration: null });
  };

  const handleRefreshPlugins = () => {
    discoverPluginsMutation.mutate();
  };

  const getIntegrationTypeInfo = (type: string) => {
    return integrationTypes.find((t) => t.type === type);
  };

  const getIntegrationIcon = (type: string) => {
    const typeInfo = getIntegrationTypeInfo(type);
    const iconName = typeInfo?.icon || "bell";

    const icons: Record<string, JSX.Element> = {
      bell: (
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
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
      ),
      link: (
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
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
      ),
      mail: (
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
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      ),
      code: (
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
            d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
          />
        </svg>
      ),
      puzzle: (
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
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
      ),
      slack: (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
          <path d="M6 15a2 2 0 01-2 2 2 2 0 01-2-2 2 2 0 012-2h2v2zm1 0a2 2 0 012-2 2 2 0 012 2v5a2 2 0 01-2 2 2 2 0 01-2-2v-5zM9 6a2 2 0 01-2-2 2 2 0 012-2 2 2 0 012 2v2H9zm0 1a2 2 0 012 2 2 2 0 01-2 2H4a2 2 0 01-2-2 2 2 0 012-2h5zm9 2a2 2 0 012-2 2 2 0 012 2 2 2 0 01-2 2h-2V9zm-1 0a2 2 0 01-2 2 2 2 0 01-2-2V4a2 2 0 012-2 2 2 0 012 2v5zm-2 9a2 2 0 012 2 2 2 0 01-2 2 2 2 0 01-2-2v-2h2zm0-1a2 2 0 01-2-2 2 2 0 012-2h5a2 2 0 012 2 2 2 0 01-2 2h-5z" />
        </svg>
      ),
      discord: (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
          <path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
        </svg>
      ),
      telegram: (
        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
          <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
        </svg>
      ),
    };

    return icons[iconName] || icons.bell;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">
          Loading integrations...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Integrations
          </h1>
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-300 mt-1">
            Connect external services to receive notifications and alerts
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 self-start sm:self-auto">
          <button
            onClick={handleRefreshPlugins}
            disabled={discoverPluginsMutation.isPending}
            className="bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm sm:text-base"
            title="Discover new plugins from the plugins directory"
          >
            <svg
              className={`w-4 h-4 sm:w-5 sm:h-5 ${discoverPluginsMutation.isPending ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            <span className="hidden sm:inline">
              {discoverPluginsMutation.isPending
                ? "Discovering..."
                : "Refresh Plugins"}
            </span>
            <span className="sm:hidden">
              {discoverPluginsMutation.isPending ? "Discovering..." : "Refresh"}
            </span>
          </button>
          <button
            onClick={handleAddClick}
            className="bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base"
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
            <span className="hidden sm:inline">Add Integration</span>
            <span className="sm:hidden">Add</span>
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
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
                Total Integrations
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {integrations.length}
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
                Active Integrations
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {integrations.filter((i) => i.enabled).length}
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
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Total Triggered
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {integrations.reduce((sum, i) => sum + i.total_triggered, 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Integrations List */}
      {integrations.length === 0 ? (
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
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No integrations yet
          </h3>
          <p className="text-gray-600 dark:text-gray-300 mb-4">
            Get started by adding your first integration to receive
            notifications and automate workflows.
          </p>
          <button
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
            Add Your First Integration
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {integrations.map((integration) => {
            const typeInfo = getIntegrationTypeInfo(integration.type);
            return (
              <div
                key={integration.id}
                className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow border border-transparent dark:border-gray-700"
              >
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2 rounded-lg ${
                          integration.enabled
                            ? "bg-blue-100 dark:bg-blue-900/50"
                            : "bg-gray-100 dark:bg-gray-700"
                        }`}
                      >
                        <div
                          className={
                            integration.enabled
                              ? "text-blue-600 dark:text-blue-300"
                              : "text-gray-400 dark:text-gray-500"
                          }
                        >
                          {getIntegrationIcon(integration.type)}
                        </div>
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                          {integration.name}
                        </h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {typeInfo?.name || integration.type}
                        </p>
                      </div>
                    </div>
                    {integration.name === "In-App Notifications" ? (
                      <div className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 whitespace-nowrap">
                        Always Enabled
                      </div>
                    ) : (
                      <ToggleSwitch
                        checked={integration.enabled}
                        onChange={(enabled) =>
                          toggleEnabledMutation.mutate({
                            id: integration.id,
                            enabled,
                          })
                        }
                        label=""
                      />
                    )}
                  </div>

                  {/* Description */}
                  {integration.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                      {integration.description}
                    </p>
                  )}

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
                          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                        />
                      </svg>
                      <span>{integration.events_subscribed.length} events</span>
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
                          d="M13 10V3L4 14h7v7l9-11h-7z"
                        />
                      </svg>
                      <span>{integration.total_triggered} triggered</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                    {integration.name === "In-App Notifications" ? (
                      <>
                        <button
                          onClick={() => handleEditClick(integration)}
                          className="flex-1 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                        >
                          Edit
                        </button>
                        <div className="flex-1 px-3 py-2 text-sm text-gray-400 dark:text-gray-500 text-center">
                          Built-in integration
                        </div>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => handleEditClick(integration)}
                          className="flex-1 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(integration)}
                          className="flex-1 px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* What are Event Hooks / How it works */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mt-6 border border-gray-200 dark:border-gray-700">
        {/* How it Works */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8">
          <div className="text-center">
            <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-blue-600 dark:text-blue-300">
                1
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Create Integration
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Set up your integration (Webhook, Slack, Email, etc.)
            </p>
          </div>

          <div className="text-center">
            <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-purple-600 dark:text-purple-300">
                2
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Subscribe to Events
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Choose which events should trigger the integration
            </p>
          </div>

          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 dark:bg-green-900/50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl font-bold text-green-600 dark:text-green-300">
                3
              </span>
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Automatic Execution
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Integration triggers automatically when events occur
            </p>
          </div>
        </div>
        <p className="text-gray-600 dark:text-gray-300 mb-4">
          Event Hooks connect your integrations to specific events in Linguard.
          When an event occurs (like creating a server or peer), all enabled
          integrations subscribed to that event will be triggered automatically.
        </p>
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 mb-6 border border-gray-200 dark:border-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
            Example Use Case:
          </h3>
          <div className="text-sm text-gray-600 dark:text-gray-300 space-y-1">
            <p>
              <span className="font-medium">Event:</span>{" "}
              <code className="bg-white dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700">
                server.started
              </code>
            </p>
            <p>
              <span className="font-medium">→ Integration:</span> Slack webhook
            </p>
            <p>
              <span className="font-medium">→ Action:</span> Post message
              "Server production-vpn-01 has started" to #alerts channel
            </p>
          </div>
        </div>
      </div>

      {/* Integration Form Modal */}
      {showForm && (
        <IntegrationForm
          integration={editingIntegration}
          integrationTypes={integrationTypes}
          onClose={handleFormClose}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm.isOpen && deleteConfirm.integration && (
        <ConfirmDialog
          isOpen={deleteConfirm.isOpen}
          title="Delete Integration"
          message={`Are you sure you want to delete "${deleteConfirm.integration.name}"? This action cannot be undone.`}
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
