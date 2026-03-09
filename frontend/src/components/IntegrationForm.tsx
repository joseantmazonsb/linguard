import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { integrationsAPI } from "../services/api";
import ToggleSwitch from "./ToggleSwitch";
import type { Integration, IntegrationType } from "../types";
import type { FieldErrors } from "../utils/errorUtils";
import {
  parseValidationErrors,
  getFieldError,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from "../utils/errorUtils";
import FieldError from "./FieldError";
import CustomSelect from "./CustomSelect";

type IntegrationFormProps = {
  integration: Integration | null;
  integrationTypes: IntegrationType[];
  onClose: () => void;
};

// All available event types
const EVENT_TYPES = [
  { value: "server.created", label: "Server Created", category: "Server" },
  { value: "server.edited", label: "Server Edited", category: "Server" },
  { value: "server.deleted", label: "Server Deleted", category: "Server" },
  { value: "server.started", label: "Server Started", category: "Server" },
  { value: "server.stopped", label: "Server Stopped", category: "Server" },
  { value: "server.reloaded", label: "Server Reloaded", category: "Server" },
  { value: "peer.created", label: "Peer Created", category: "Peer" },
  { value: "peer.edited", label: "Peer Edited", category: "Peer" },
  { value: "peer.deleted", label: "Peer Deleted", category: "Peer" },
  { value: "peer.connected", label: "Peer Connected", category: "Peer" },
  { value: "peer.disconnected", label: "Peer Disconnected", category: "Peer" },
  { value: "backup.created", label: "Backup Created", category: "Backup" },
  { value: "backup.restored", label: "Backup Restored", category: "Backup" },
  { value: "backup.deleted", label: "Backup Deleted", category: "Backup" },
  { value: "settings.updated", label: "Settings Updated", category: "System" },
];

export default function IntegrationForm({
  integration,
  integrationTypes,
  onClose,
}: IntegrationFormProps) {
  const queryClient = useQueryClient();

  // Get first available non-notification type for new integrations
  const defaultType =
    integration?.type ||
    integrationTypes.find((t) => t.type !== "notification")?.type ||
    "webhook";

  const [formData, setFormData] = useState({
    name: integration?.name || "",
    description: integration?.description || "",
    type: defaultType,
    config: integration?.config || {},
    events_subscribed: integration?.events_subscribed || [],
    enabled: integration?.enabled ?? true,
  });

  // Track visibility for sensitive fields
  const [sensitiveFieldsVisible, setSensitiveFieldsVisible] = useState<
    Record<string, boolean>
  >({});

  // Track field-level validation errors
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  // Check if editing the built-in In-App Notifications integration
  const isInAppNotifications = integration?.name === "In-App Notifications";

  // Events that In-App Notifications is allowed to subscribe to
  const allowedInAppEvents = [
    "server.reloaded",
    "peer.connected",
    "peer.disconnected",
  ];

  const selectedType = integrationTypes.find((t) => t.type === formData.type);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: any) => integrationsAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setFieldErrors({}); // Clear errors on success
      toast.success("Integration created successfully");
      onClose();
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to create integration"));
      }
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: any) => integrationsAPI.update(integration!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setFieldErrors({}); // Clear errors on success
      toast.success("Integration updated successfully");
      onClose();
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to update integration"));
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (integration) {
      updateMutation.mutate(formData);
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleEventToggle = (eventValue: string) => {
    const events = formData.events_subscribed.includes(eventValue)
      ? formData.events_subscribed.filter((e) => e !== eventValue)
      : [...formData.events_subscribed, eventValue];

    setFormData({ ...formData, events_subscribed: events });
  };

  const handleSelectAllEvents = () => {
    setFormData({
      ...formData,
      events_subscribed: EVENT_TYPES.map((e) => e.value),
    });
  };

  const handleDeselectAllEvents = () => {
    setFormData({ ...formData, events_subscribed: [] });
  };

  const handleConfigChange = (key: string, value: any) => {
    setFormData({
      ...formData,
      config: {
        ...formData.config,
        [key]: value,
      },
    });
    setFieldErrors({}); // Clear errors when user types
  };

  const toggleSensitiveFieldVisibility = (key: string) => {
    setSensitiveFieldsVisible((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const renderConfigFields = () => {
    if (
      !selectedType?.config_schema ||
      Object.keys(selectedType.config_schema).length === 0
    ) {
      return (
        <div className="text-sm text-gray-500 dark:text-gray-400 italic">
          No additional configuration required for this integration type.
        </div>
      );
    }

    return Object.entries(selectedType.config_schema).map(
      ([key, schema]: [string, any]) => {
        const value = formData.config[key] || schema.default || "";
        const fieldName = `config.${key}`;

        return (
          <div key={key}>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
              {schema.required && (
                <span className="text-red-600 dark:text-red-400 ml-1">*</span>
              )}
            </label>
            {schema.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {schema.description}
              </p>
            )}
            {schema.type === "boolean" ? (
              <>
                <ToggleSwitch
                  enabled={value === true || value === "true"}
                  onChange={(enabled) => handleConfigChange(key, enabled)}
                  label=""
                />
                <FieldError error={getFieldError(fieldErrors, fieldName)} />
              </>
            ) : schema.type === "array" ? (
              <>
                <textarea
                  value={Array.isArray(value) ? value.join("\n") : value}
                  onChange={(e) =>
                    handleConfigChange(
                      key,
                      e.target.value.split("\n").filter(Boolean),
                    )
                  }
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, fieldName)
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                  rows={3}
                  placeholder="One item per line"
                  required={schema.required}
                />
                <FieldError error={getFieldError(fieldErrors, fieldName)} />
              </>
            ) : schema.options ? (
              <>
                <CustomSelect
                  value={value}
                  onChange={(val) => handleConfigChange(key, val)}
                  options={[
                    { value: "", label: "Select..." },
                    ...schema.options.map((option: string) => ({
                      value: option,
                      label: option,
                    })),
                  ]}
                  placeholder="Select..."
                />
                <FieldError error={getFieldError(fieldErrors, fieldName)} />
              </>
            ) : schema.type === "number" ? (
              <>
                <input
                  type="number"
                  value={value}
                  onChange={(e) =>
                    handleConfigChange(key, parseInt(e.target.value))
                  }
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, fieldName)
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                  required={schema.required}
                />
                <FieldError error={getFieldError(fieldErrors, fieldName)} />
              </>
            ) : (
              <div className="relative">
                <input
                  type={
                    schema.sensitive && !sensitiveFieldsVisible[key]
                      ? "password"
                      : "text"
                  }
                  value={value}
                  onChange={(e) => handleConfigChange(key, e.target.value)}
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, fieldName)
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white pr-10`}
                  required={schema.required}
                />
                {schema.sensitive && (
                  <button
                    type="button"
                    onClick={() => toggleSensitiveFieldVisibility(key)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                    title={sensitiveFieldsVisible[key] ? "Hide" : "Show"}
                  >
                    {sensitiveFieldsVisible[key] ? (
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
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                        />
                      </svg>
                    ) : (
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
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    )}
                  </button>
                )}
                <FieldError error={getFieldError(fieldErrors, fieldName)} />
              </div>
            )}
          </div>
        );
      },
    );
  };

  // Group events by category
  const eventsByCategory = EVENT_TYPES.reduce(
    (acc, event) => {
      if (!acc[event.category]) {
        acc[event.category] = [];
      }
      acc[event.category].push(event);
      return acc;
    },
    {} as Record<string, typeof EVENT_TYPES>,
  );

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          {/* Header */}
          <div className="sticky top-0 z-[60] bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              {integration ? "Edit Integration" : "Add Integration"}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
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

          {/* Form Body */}
          <div className="p-6 space-y-6">
            {/* Basic Info */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Basic Information
              </h3>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Name <span className="text-red-600 dark:text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    setFieldErrors({}); // Clear errors when user types
                  }}
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, "name")
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed`}
                  required
                  disabled={isInAppNotifications}
                />
                <FieldError error={getFieldError(fieldErrors, "name")} />
                {isInAppNotifications &&
                  !getFieldError(fieldErrors, "name") && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Name cannot be changed for built-in integration
                    </p>
                  )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => {
                    setFormData({ ...formData, description: e.target.value });
                    setFieldErrors({}); // Clear errors when user types
                  }}
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, "description")
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed`}
                  rows={2}
                  disabled={isInAppNotifications}
                />
                <FieldError error={getFieldError(fieldErrors, "description")} />
                {isInAppNotifications &&
                  !getFieldError(fieldErrors, "description") && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Description cannot be changed for built-in integration
                    </p>
                  )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Type <span className="text-red-600 dark:text-red-400">*</span>
                </label>
                <CustomSelect
                  value={formData.type}
                  onChange={(value) =>
                    setFormData({
                      ...formData,
                      type: value.toString(),
                      config: {},
                    })
                  }
                  options={integrationTypes
                    .filter(
                      (type) => 
                        type.enabled && // Only show enabled integration types
                        (integration || type.type !== "notification") // Hide 'notification' type when creating new
                    )
                    .map((type) => ({
                      value: type.type,
                      label: `${type.name} - ${type.description}`,
                    }))}
                  placeholder="Select integration type"
                  className={
                    integration ? "opacity-50 pointer-events-none" : ""
                  }
                />
                {integration && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Type cannot be changed after creation
                  </p>
                )}
              </div>

              <ToggleSwitch
                id="enabled"
                checked={formData.enabled}
                onChange={(checked) =>
                  setFormData({ ...formData, enabled: checked })
                }
                disabled={isInAppNotifications}
                label="Enabled"
              />
            </div>

            {/* Configuration */}
            {!isInAppNotifications && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Configuration
                </h3>
                {renderConfigFields()}
              </div>
            )}

            {/* Event Subscriptions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Event Subscriptions
                </h3>
                {!isInAppNotifications && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleSelectAllEvents}
                      className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                    >
                      Select All
                    </button>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <button
                      type="button"
                      onClick={handleDeselectAllEvents}
                      className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                    >
                      Deselect All
                    </button>
                  </div>
                )}
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400">
                Select events to trigger this integration automatically. Leave empty if you only want to use this integration with traffic triggers.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(eventsByCategory).map(([category, events]) => (
                  <div
                    key={category}
                    className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800"
                  >
                    <h4 className="font-semibold text-gray-900 dark:text-white mb-3">
                      {category}
                    </h4>
                    <div className="space-y-2">
                      {events.map((event) => {
                        const isEventAllowed =
                          !isInAppNotifications ||
                          allowedInAppEvents.includes(event.value);
                        return (
                          <label
                            key={event.value}
                            className={`flex items-center ${!isEventAllowed ? "opacity-50" : ""}`}
                          >
                            <input
                              type="checkbox"
                              checked={
                                isInAppNotifications ||
                                formData.events_subscribed.includes(event.value)
                              }
                              onChange={() => handleEventToggle(event.value)}
                              disabled={!isEventAllowed}
                              className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500 bg-white dark:bg-gray-700 disabled:cursor-not-allowed"
                            />
                            <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                              {event.label}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                createMutation.isPending ||
                updateMutation.isPending
              }
              className="px-4 py-2 bg-blue-600 dark:bg-blue-700 hover:bg-blue-700 dark:hover:bg-blue-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending || updateMutation.isPending
                ? "Saving..."
                : integration
                  ? "Update Integration"
                  : "Create Integration"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
