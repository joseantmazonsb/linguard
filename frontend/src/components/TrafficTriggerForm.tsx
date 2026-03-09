import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { trafficTriggersAPI } from "../services/api";
import ToggleSwitch from "./ToggleSwitch";
import CustomSelect from "./CustomSelect";
import type {
  TrafficTrigger,
  TrafficScope,
  TrafficDirection,
  ThresholdWindow,
  Server,
  Peer,
  Integration,
} from "../types";

type TrafficTriggerFormProps = {
  trigger: TrafficTrigger | null;
  servers: Server[];
  peers: Peer[];
  integrations: Integration[];
  onClose: () => void;
};

export default function TrafficTriggerForm({
  trigger,
  servers,
  peers,
  integrations,
  onClose,
}: TrafficTriggerFormProps) {
  const queryClient = useQueryClient();
  const isEditing = !!trigger;

  const [formData, setFormData] = useState({
    name: trigger?.name || "",
    scope: (trigger?.scope || "peer") as TrafficScope,
    peer_id: trigger?.peer_id || undefined,
    server_id: trigger?.server_id || undefined,
    direction: (trigger?.direction || "combined") as TrafficDirection,
    threshold_gb: trigger
      ? (trigger.threshold_bytes / 1024 ** 3).toFixed(2)
      : "1",
    window: (trigger?.window || "last_24_hours") as ThresholdWindow,
    cooldown_minutes: trigger?.cooldown_minutes || 60,
    enabled: trigger?.enabled ?? true,
    integration_ids: trigger?.integration_ids || [],
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => trafficTriggersAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traffic-triggers"] });
      toast.success("Traffic trigger created successfully");
      onClose();
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to create trigger";
      toast.error(message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      trafficTriggersAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traffic-triggers"] });
      toast.success("Traffic trigger updated successfully");
      onClose();
    },
    onError: (error: any) => {
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Failed to update trigger";
      toast.error(message);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const threshold_bytes = Math.round(
      parseFloat(formData.threshold_gb) * 1024 ** 3,
    );

    const payload: any = {
      name: formData.name,
      scope: formData.scope,
      direction: formData.direction,
      threshold_bytes,
      window: formData.window,
      cooldown_minutes: formData.cooldown_minutes,
      enabled: formData.enabled,
      integration_ids: formData.integration_ids,
    };

    if (formData.scope === "peer" && formData.peer_id) {
      payload.peer_id = formData.peer_id;
    } else if (formData.scope === "server" && formData.server_id) {
      payload.server_id = formData.server_id;
    }

    if (isEditing) {
      updateMutation.mutate({ id: trigger.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const toggleIntegration = (integrationId: number) => {
    if (formData.integration_ids.includes(integrationId)) {
      setFormData({
        ...formData,
        integration_ids: formData.integration_ids.filter(
          (id) => id !== integrationId,
        ),
      });
    } else {
      setFormData({
        ...formData,
        integration_ids: [...formData.integration_ids, integrationId],
      });
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-[60] bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">
            {isEditing ? "Edit Traffic Trigger" : "Add Traffic Trigger"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
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

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Trigger Name *
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="e.g., High Usage Alert - John's Laptop"
            />
          </div>

          {/* Scope */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Scope *
            </label>
            <CustomSelect
              value={formData.scope}
              onChange={(value) =>
                setFormData({
                  ...formData,
                  scope: value as TrafficScope,
                  peer_id: undefined,
                  server_id: undefined,
                })
              }
              options={[
                { value: "peer", label: "Peer (Individual User)" },
                { value: "server", label: "Server (All Peers on Server)" },
                { value: "global", label: "Global (All Traffic)" },
              ]}
              placeholder="Select scope"
            />
          </div>

          {/* Peer Selection (if scope=peer) */}
          {formData.scope === "peer" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Select Peer *
              </label>
              <CustomSelect
                value={formData.peer_id?.toString() || ""}
                onChange={(value) =>
                  setFormData({
                    ...formData,
                    peer_id: parseInt(value.toString()),
                  })
                }
                options={[
                  { value: "", label: "Select a peer..." },
                  ...peers.map((peer) => ({
                    value: peer.id.toString(),
                    label: `${peer.name} (${peer.address})`,
                  })),
                ]}
                placeholder="Select a peer"
              />
            </div>
          )}

          {/* Server Selection (if scope=server) */}
          {formData.scope === "server" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Select Server *
              </label>
              <CustomSelect
                value={formData.server_id?.toString() || ""}
                onChange={(value) =>
                  setFormData({
                    ...formData,
                    server_id: parseInt(value.toString()),
                  })
                }
                options={[
                  { value: "", label: "Select a server..." },
                  ...servers.map((server) => ({
                    value: server.id.toString(),
                    label: `${server.name} (${server.endpoint})`,
                  })),
                ]}
                placeholder="Select a server"
              />
            </div>
          )}

          {/* Direction */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Traffic Direction *
            </label>
            <CustomSelect
              value={formData.direction}
              onChange={(value) =>
                setFormData({
                  ...formData,
                  direction: value as TrafficDirection,
                })
              }
              options={[
                { value: "combined", label: "Combined (RX + TX)" },
                { value: "rx_only", label: "Download Only (RX)" },
                { value: "tx_only", label: "Upload Only (TX)" },
              ]}
              placeholder="Select direction"
            />
          </div>

          {/* Threshold */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Threshold (GB) *
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={formData.threshold_gb}
              onChange={(e) =>
                setFormData({ ...formData, threshold_gb: e.target.value })
              }
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="e.g., 5.00"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Trigger fires when traffic exceeds this amount
            </p>
          </div>

          {/* Window */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Time Window *
            </label>
            <CustomSelect
              value={formData.window}
              onChange={(value) =>
                setFormData({ ...formData, window: value as ThresholdWindow })
              }
              options={[
                { value: "last_hour", label: "Last Hour" },
                { value: "last_24_hours", label: "Last 24 Hours" },
                { value: "last_7_days", label: "Last 7 Days" },
                { value: "last_30_days", label: "Last 30 Days" },
              ]}
              placeholder="Select time window"
            />
          </div>

          {/* Cooldown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Cooldown (minutes) *
            </label>
            <input
              type="number"
              min="1"
              required
              value={formData.cooldown_minutes}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  cooldown_minutes: parseInt(e.target.value),
                })
              }
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="e.g., 60"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Minimum time between notifications
            </p>
          </div>

          {/* Integrations */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Integrations to Trigger
            </label>
            <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2 max-h-40 overflow-y-auto">
              {integrations.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No integrations available. Create an integration first.
                </p>
              ) : (
                integrations.map((integration) => (
                  <label
                    key={integration.id}
                    className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 p-2 rounded"
                  >
                    <input
                      type="checkbox"
                      checked={formData.integration_ids.includes(
                        integration.id,
                      )}
                      onChange={() => toggleIntegration(integration.id)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-900 dark:text-white">
                      {integration.name}
                      <span className="text-gray-500 dark:text-gray-400 ml-1">
                        ({integration.type})
                      </span>
                    </span>
                  </label>
                ))
              )}
            </div>
          </div>

          {/* Enabled */}
          <ToggleSwitch
            id="enabled"
            checked={formData.enabled}
            onChange={(checked) =>
              setFormData({ ...formData, enabled: checked })
            }
            label="Enable"
          />

          {/* Form Actions */}
          <div className="flex items-center gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
            >
              {createMutation.isPending || updateMutation.isPending
                ? "Saving..."
                : isEditing
                  ? "Update Trigger"
                  : "Create Trigger"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
