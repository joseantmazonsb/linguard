import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { settingsAPI } from "../services/apiClient";
import ToggleSwitch from "../components/ToggleSwitch";
import CustomSelect from "../components/CustomSelect";
import type { FieldErrors } from "../utils/errorUtils";
import {
  parseValidationErrors,
  getFieldError,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from "../utils/errorUtils";
import FieldError from "../components/FieldError";
import { oidcAPI } from "../services/apiClient";

interface GlobalSettings {
  id: number;
  // DNS Configuration
  dns_primary?: string;
  dns_secondary?: string;
  // Database (read-only)
  database_type?: string;
  database_url?: string;
  // Security Settings
  secret_key?: string;
  algorithm?: string;
  access_token_expire_minutes?: number;
  // Authentication Settings
  auth_mode?: string;
  oidc_discovery_url?: string | null;
  oidc_client_id?: string | null;
  oidc_client_secret?: string | null;
  oidc_scopes?: string;
  oidc_provider_name?: string | null;
  oidc_auto_provision?: boolean;
  oidc_admin_groups?: string;
  // Logging Settings
  log_level?: string;
  log_path?: string;
  // Backup Settings
  backup_dir?: string;
  backup_retention_days?: number;
  backup_auto_cleanup_enabled?: boolean;
  backup_periodic_enabled?: boolean;
  backup_schedule_frequency?: string;
  backup_schedule_hour?: number;
  backup_schedule_minute?: number;
  // Traffic Monitoring Settings
  metrics_collection_interval_minutes?: number;
  metrics_retention_days?: number;
  metrics_global_notifications_per_hour?: number;
  // Metadata
  created_at: string;
  updated_at?: string;
}

export default function Settings() {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<GlobalSettings | null>(null);
  const [showConnectionString, setShowConnectionString] = useState(false);
  const [showSecretKey, setShowSecretKey] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [oidcTestResult, setOidcTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [oidcTesting, setOidcTesting] = useState(false);
  const queryClient = useQueryClient();

  // Fetch global settings
  const {
    data: settings,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["global-settings"],
    queryFn: settingsAPI.getGlobal,
  });

  // Update settings mutation
  const updateMutation = useMutation({
    mutationFn: settingsAPI.updateGlobal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["global-settings"] });
      setIsEditing(false);
      setFormData(null);
      setFieldErrors({}); // Clear errors on success
      toast.success("Settings updated successfully");
    },
    onError: (error: any) => {
      if (isValidationError(error)) {
        const errors = parseValidationErrors(error);
        setFieldErrors(errors);
        const count = countErrors(errors);
        toast.error(formatErrorCount(count));
      } else {
        toast.error(getGenericError(error, "Failed to update settings"));
      }
    },
  });

  const handleEdit = () => {
    setFormData(settings);
    setFieldErrors({}); // Clear errors when starting edit
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setFormData(null);
    setFieldErrors({}); // Clear errors when canceling
  };

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    const { name, value, type } = e.target;
    const finalValue =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : value;

    setFormData((prev) => (prev ? { ...prev, [name]: finalValue } : null));
    setFieldErrors({}); // Clear errors when user types
  };

  const generateSecretKey = () => {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const key = Array.from(array, (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    setFormData((prev) => (prev ? { ...prev, secret_key: key } : null));
  };

  const handleOidcTest = async () => {
    if (!displayData?.oidc_discovery_url || !displayData?.oidc_client_id) {
      setOidcTestResult({
        success: false,
        message: "Discovery URL and Client ID are required before testing.",
      });
      return;
    }
    setOidcTesting(true);
    setOidcTestResult(null);
    try {
      const result = await oidcAPI.test({
        discovery_url: displayData.oidc_discovery_url,
        client_id: displayData.oidc_client_id,
        client_secret: displayData.oidc_client_secret || "",
        scopes: displayData.oidc_scopes || "openid email profile",
      });
      setOidcTestResult({ success: result.success, message: result.message });
    } catch (err: any) {
      setOidcTestResult({
        success: false,
        message: err.response?.data?.detail || "Test failed",
      });
    } finally {
      setOidcTesting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (formData) {
      const submitData: any = {};

      // DNS Configuration
      if (formData.dns_primary) submitData.dns_primary = formData.dns_primary;
      if (formData.dns_secondary)
        submitData.dns_secondary = formData.dns_secondary;

      // Security Settings
      if (formData.secret_key) submitData.secret_key = formData.secret_key;
      if (formData.access_token_expire_minutes !== undefined)
        submitData.access_token_expire_minutes =
          formData.access_token_expire_minutes;

      // Authentication Settings
      if (formData.auth_mode !== undefined) submitData.auth_mode = formData.auth_mode;
      if (formData.oidc_discovery_url !== undefined)
        submitData.oidc_discovery_url = formData.oidc_discovery_url || null;
      if (formData.oidc_client_id !== undefined)
        submitData.oidc_client_id = formData.oidc_client_id || null;
      if (formData.oidc_client_secret !== undefined)
        submitData.oidc_client_secret = formData.oidc_client_secret || null;
      if (formData.oidc_scopes !== undefined)
        submitData.oidc_scopes = formData.oidc_scopes;
      if (formData.oidc_provider_name !== undefined)
        submitData.oidc_provider_name = formData.oidc_provider_name || null;
      if (formData.oidc_auto_provision !== undefined)
        submitData.oidc_auto_provision = formData.oidc_auto_provision;
      if (formData.oidc_admin_groups !== undefined)
        submitData.oidc_admin_groups = formData.oidc_admin_groups;

      // Logging Settings
      if (formData.log_level) submitData.log_level = formData.log_level;
      if (formData.log_path !== undefined)
        submitData.log_path = formData.log_path || null;

      // Backup Settings
      if (formData.backup_dir) submitData.backup_dir = formData.backup_dir;
      if (formData.backup_retention_days !== undefined)
        submitData.backup_retention_days = formData.backup_retention_days;
      if (formData.backup_auto_cleanup_enabled !== undefined)
        submitData.backup_auto_cleanup_enabled =
          formData.backup_auto_cleanup_enabled;
      if (formData.backup_periodic_enabled !== undefined)
        submitData.backup_periodic_enabled = formData.backup_periodic_enabled;
      if (formData.backup_schedule_frequency !== undefined)
        submitData.backup_schedule_frequency =
          formData.backup_schedule_frequency;
      if (formData.backup_schedule_hour !== undefined)
        submitData.backup_schedule_hour = formData.backup_schedule_hour;
      if (formData.backup_schedule_minute !== undefined)
        submitData.backup_schedule_minute = formData.backup_schedule_minute;

      // Traffic Monitoring Settings
      if (formData.metrics_collection_interval_minutes !== undefined)
        submitData.metrics_collection_interval_minutes =
          formData.metrics_collection_interval_minutes;
      if (formData.metrics_retention_days !== undefined)
        submitData.metrics_retention_days = formData.metrics_retention_days;
      if (formData.metrics_global_notifications_per_hour !== undefined)
        submitData.metrics_global_notifications_per_hour =
          formData.metrics_global_notifications_per_hour;

      updateMutation.mutate(submitData);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500 dark:text-gray-400">
            Loading settings...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded">
          Error loading settings: {(error as Error).message}
        </div>
      </div>
    );
  }

  const displayData = isEditing ? formData : settings;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Settings
        </h1>
        {!isEditing && (
          <button
            onClick={handleEdit}
            className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
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
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
            Edit Settings
          </button>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <form onSubmit={handleSubmit}>
          {/* Database Configuration (Read-only) */}
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Database Backend
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Database Type
                </label>
                <div className="px-3 py-2 bg-gray-100 dark:bg-gray-700/50 rounded-lg text-gray-900 dark:text-gray-300 font-mono uppercase border border-gray-300 dark:border-gray-600">
                  {displayData?.database_type || "unknown"}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Connection String
                </label>
                <div className="relative">
                  <div className="px-3 py-2 pr-12 bg-gray-100 dark:bg-gray-700/50 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm border border-gray-300 dark:border-gray-600 break-all">
                    {showConnectionString
                      ? displayData?.database_url || "Not available"
                      : "•".repeat(
                          Math.min(displayData?.database_url?.length || 0, 50),
                        )}
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setShowConnectionString(!showConnectionString)
                    }
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
                    title={
                      showConnectionString
                        ? "Hide connection string"
                        : "Show connection string"
                    }
                  >
                    {showConnectionString ? (
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
                </div>
              </div>
            </div>
          </div>

          {/* DNS Configuration */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              DNS
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Global DNS settings inherited by servers and peers when not
              explicitly configured.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Primary DNS Server
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      name="dns_primary"
                      value={displayData?.dns_primary || ""}
                      onChange={handleChange}
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, "dns_primary")
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                      placeholder="8.8.8.8"
                    />
                    <FieldError
                      error={getFieldError(fieldErrors, "dns_primary")}
                    />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.dns_primary || "Not set"}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Secondary DNS Server
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      name="dns_secondary"
                      value={displayData?.dns_secondary || ""}
                      onChange={handleChange}
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, "dns_secondary")
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                      placeholder="8.8.4.4"
                    />
                    <FieldError
                      error={getFieldError(fieldErrors, "dns_secondary")}
                    />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.dns_secondary || "Not set"}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Backup Settings */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Backup
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Configure automatic backup behavior and retention.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Backup Directory
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      name="backup_dir"
                      value={displayData?.backup_dir || ""}
                      onChange={handleChange}
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, "backup_dir")
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm`}
                      placeholder="./backups"
                    />
                    <FieldError
                      error={getFieldError(fieldErrors, "backup_dir")}
                    />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                    {displayData?.backup_dir || "./backups"}
                  </div>
                )}
              </div>

              {/* Auto Cleanup Toggle */}
              <div className="md:col-span-2">
                <ToggleSwitch
                  id="backup_auto_cleanup_enabled"
                  checked={displayData?.backup_auto_cleanup_enabled ?? true}
                  onChange={(checked) =>
                    handleChange({
                      target: {
                        name: "backup_auto_cleanup_enabled",
                        type: "checkbox",
                        checked,
                      },
                    } as any)
                  }
                  disabled={!isEditing}
                  label="Enable automatic cleanup of old backups"
                />
                <p className="ml-6 mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Automatically delete backups older than the retention period
                </p>
              </div>

              {/* Retention Period - only show when cleanup is enabled */}
              {displayData?.backup_auto_cleanup_enabled && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Retention Period (days)
                  </label>
                  {isEditing ? (
                    <>
                      <input
                        type="number"
                        name="backup_retention_days"
                        value={displayData?.backup_retention_days || 30}
                        onChange={handleChange}
                        min="1"
                        max="365"
                        className={`w-full px-3 py-2 border ${
                          getFieldError(fieldErrors, "backup_retention_days")
                            ? "border-red-500"
                            : "border-gray-300 dark:border-gray-600"
                        } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                      />
                      <FieldError
                        error={getFieldError(
                          fieldErrors,
                          "backup_retention_days",
                        )}
                      />
                      {!getFieldError(fieldErrors, "backup_retention_days") && (
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          Backups older than this period will be automatically
                          deleted
                        </p>
                      )}
                    </>
                  ) : (
                    <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                      {displayData?.backup_retention_days || 30} days
                    </div>
                  )}
                </div>
              )}

              {/* Periodic Backup Toggle */}
              <div className="md:col-span-2">
                <ToggleSwitch
                  id="backup_periodic_enabled"
                  checked={displayData?.backup_periodic_enabled ?? false}
                  onChange={(checked) =>
                    handleChange({
                      target: {
                        name: "backup_periodic_enabled",
                        type: "checkbox",
                        checked,
                      },
                    } as any)
                  }
                  disabled={!isEditing}
                  label="Enable scheduled automatic backups"
                />
                <p className="ml-6 mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Create backups automatically at the scheduled time each day
                </p>
              </div>

              {/* Backup Schedule Time */}
              {displayData?.backup_periodic_enabled && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Backup Schedule
                  </label>
                  {isEditing ? (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <CustomSelect
                          value={
                            displayData?.backup_schedule_frequency ?? "daily"
                          }
                          onChange={(value) =>
                            handleChange({
                              target: {
                                name: "backup_schedule_frequency",
                                value: value.toString(),
                              },
                            } as any)
                          }
                          options={[
                            { value: "daily", label: "Daily" },
                            { value: "weekly", label: "Weekly" },
                            { value: "monthly", label: "Monthly" },
                          ]}
                          placeholder="Select frequency"
                          className="w-32"
                        />
                        <span className="text-gray-700 dark:text-gray-300">
                          at
                        </span>
                        <input
                          type="number"
                          name="backup_schedule_hour"
                          value={displayData?.backup_schedule_hour ?? 2}
                          onChange={handleChange}
                          min="0"
                          max="23"
                          className={`w-20 px-3 py-2 border ${
                            getFieldError(fieldErrors, "backup_schedule_hour")
                              ? "border-red-500"
                              : "border-gray-300 dark:border-gray-600"
                          } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center font-mono`}
                          placeholder="HH"
                        />
                        <span className="text-gray-700 dark:text-gray-300 font-mono text-lg">
                          :
                        </span>
                        <input
                          type="number"
                          name="backup_schedule_minute"
                          value={displayData?.backup_schedule_minute ?? 0}
                          onChange={handleChange}
                          min="0"
                          max="59"
                          className={`w-20 px-3 py-2 border ${
                            getFieldError(fieldErrors, "backup_schedule_minute")
                              ? "border-red-500"
                              : "border-gray-300 dark:border-gray-600"
                          } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center font-mono`}
                          placeholder="MM"
                        />
                      </div>
                      <FieldError
                        error={getFieldError(
                          fieldErrors,
                          "backup_schedule_hour",
                        )}
                      />
                      <FieldError
                        error={getFieldError(
                          fieldErrors,
                          "backup_schedule_minute",
                        )}
                      />
                      {!getFieldError(fieldErrors, "backup_schedule_hour") &&
                        !getFieldError(
                          fieldErrors,
                          "backup_schedule_minute",
                        ) && (
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            {displayData?.backup_schedule_frequency ===
                              "weekly" &&
                              "Backups will run every Monday at the specified time"}
                            {displayData?.backup_schedule_frequency ===
                              "monthly" &&
                              "Backups will run on the 1st of each month at the specified time"}
                            {(!displayData?.backup_schedule_frequency ||
                              displayData?.backup_schedule_frequency ===
                                "daily") &&
                              "Backups will run every day at the specified time"}
                          </p>
                        )}
                    </>
                  ) : (
                    <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                      {displayData?.backup_schedule_frequency === "weekly" &&
                        "Weekly on Monday"}
                      {displayData?.backup_schedule_frequency === "monthly" &&
                        "Monthly on the 1st"}
                      {(!displayData?.backup_schedule_frequency ||
                        displayData?.backup_schedule_frequency === "daily") &&
                        "Daily"}
                      {" at "}
                      <span className="font-mono font-semibold">
                        {String(
                          displayData?.backup_schedule_hour ?? 2,
                        ).padStart(2, "0")}
                        :
                        {String(
                          displayData?.backup_schedule_minute ?? 0,
                        ).padStart(2, "0")}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Logging Settings */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Logging
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Configure application logging behavior.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Log Level
                </label>
                {isEditing ? (
                  <CustomSelect
                    value={displayData?.log_level || "INFO"}
                    onChange={(value) =>
                      handleChange({
                        target: {
                          name: "log_level",
                          value: value.toString(),
                        },
                      } as any)
                    }
                    options={[
                      { value: "DEBUG", label: "DEBUG" },
                      { value: "INFO", label: "INFO" },
                      { value: "WARNING", label: "WARNING" },
                      { value: "ERROR", label: "ERROR" },
                      { value: "CRITICAL", label: "CRITICAL" },
                    ]}
                    placeholder="Select log level"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.log_level || "INFO"}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Log File
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      name="log_path"
                      value={displayData.log_path}
                      onChange={handleChange}
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, "log_path")
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                      placeholder="/path/to/logfile.log"
                    />
                    <FieldError
                      error={getFieldError(fieldErrors, "log_path")}
                    />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.log_path || "stdout only"}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Traffic Monitoring Settings */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Traffic Monitoring
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Configure how traffic metrics are collected and stored.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Collection Interval
                </label>
                {isEditing ? (
                  <>
                    <CustomSelect
                      value={displayData?.metrics_collection_interval_minutes || 5}
                      onChange={(value) => handleChange({ 
                        target: { 
                          name: "metrics_collection_interval_minutes", 
                          value: value.toString() 
                        } 
                      } as any)}
                      options={[
                        { value: "5", label: "5 minutes" },
                        { value: "15", label: "15 minutes" },
                        { value: "30", label: "30 minutes" },
                        { value: "60", label: "60 minutes" }
                      ]}
                      placeholder="Select interval"
                    />
                    <FieldError error={getFieldError(fieldErrors, 'metrics_collection_interval_minutes')} />
                    {!getFieldError(fieldErrors, 'metrics_collection_interval_minutes') && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        How often to collect traffic statistics from peers
                      </p>
                    )}
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.metrics_collection_interval_minutes || 5} minutes
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Retention Period (days)
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="number"
                      name="metrics_retention_days"
                      value={displayData?.metrics_retention_days || 90}
                      onChange={handleChange}
                      min="1"
                      max="365"
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, 'metrics_retention_days')
                          ? 'border-red-500'
                          : 'border-gray-300 dark:border-gray-600'
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                    />
                    <FieldError error={getFieldError(fieldErrors, 'metrics_retention_days')} />
                    {!getFieldError(fieldErrors, 'metrics_retention_days') && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Metrics older than this will be automatically deleted
                      </p>
                    )}
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.metrics_retention_days || 90} days
                  </div>
                )}
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Notification Rate Limit (per hour)
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="number"
                      name="metrics_global_notifications_per_hour"
                      value={displayData?.metrics_global_notifications_per_hour || 50}
                      onChange={handleChange}
                      min="1"
                      max="1000"
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, 'metrics_global_notifications_per_hour')
                          ? 'border-red-500'
                          : 'border-gray-300 dark:border-gray-600'
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                    />
                    <FieldError error={getFieldError(fieldErrors, 'metrics_global_notifications_per_hour')} />
                    {!getFieldError(fieldErrors, 'metrics_global_notifications_per_hour') && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Maximum number of traffic trigger notifications allowed per hour (prevents notification spam)
                      </p>
                    )}
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.metrics_global_notifications_per_hour || 50} notifications/hour
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Security Settings */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Security
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Configure authentication and security parameters. Changes to these
              settings may require application restart.
            </p>

            <div className="space-y-4">
              {/* JWT Secret Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  JWT Secret Key
                </label>
                <div className="flex gap-2">
                  {isEditing ? (
                    <>
                      <div className="relative flex-1">
                        <input
                          type={showSecretKey ? "text" : "password"}
                          name="secret_key"
                          value={displayData?.secret_key || ""}
                          onChange={handleChange}
                          className={`w-full px-3 py-2 pr-10 border ${
                            getFieldError(fieldErrors, "secret_key")
                              ? "border-red-500"
                              : "border-gray-300 dark:border-gray-600"
                          } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm`}
                          placeholder="64-character hex string"
                        />
                        <button
                          type="button"
                          onClick={() => setShowSecretKey(!showSecretKey)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
                        >
                          {showSecretKey ? (
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
                      </div>
                      <button
                        type="button"
                        onClick={generateSecretKey}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 text-white rounded-lg flex items-center gap-2 transition-colors text-sm font-medium whitespace-nowrap"
                        title="Generate new secret key"
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
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                          />
                        </svg>
                        Regenerate
                      </button>
                    </>
                  ) : (
                    <div className="relative flex-1">
                      <div className="px-3 py-2 pr-12 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                        {showSecretKey
                          ? displayData?.secret_key || "•".repeat(64)
                          : "•".repeat(64)}
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowSecretKey(!showSecretKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
                        title={
                          showSecretKey ? "Hide secret key" : "Show secret key"
                        }
                      >
                        {showSecretKey ? (
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
                    </div>
                  )}
                </div>
                {isEditing && (
                  <FieldError
                    error={getFieldError(fieldErrors, "secret_key")}
                  />
                )}
              </div>

              {/* Token Expiration */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Access Token Expiration (minutes)
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="number"
                      name="access_token_expire_minutes"
                      value={displayData?.access_token_expire_minutes || 30}
                      onChange={handleChange}
                      min="5"
                      max="43200"
                      className={`w-full px-3 py-2 border ${
                        getFieldError(
                          fieldErrors,
                          "access_token_expire_minutes",
                        )
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                    />
                    <FieldError
                      error={getFieldError(
                        fieldErrors,
                        "access_token_expire_minutes",
                      )}
                    />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.access_token_expire_minutes || 30} minutes
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Authentication Settings */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Authentication
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Configure how users sign in to Linguard. Single Sign-On works with
              any OpenID Connect provider (Authentik, Keycloak, etc.).
            </p>

            <div className="space-y-4">
              {/* Auth Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Authentication Mode
                </label>
                {isEditing ? (
                  <select
                    name="auth_mode"
                    value={displayData?.auth_mode || "both"}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${
                      getFieldError(fieldErrors, "auth_mode")
                        ? "border-red-500"
                        : "border-gray-300 dark:border-gray-600"
                    } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                  >
                    <option value="both">Local + OIDC (both)</option>
                    <option value="local_only">Local Authentication Only</option>
                    <option value="oidc_only">OIDC Only</option>
                  </select>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {({ both: "Local + OIDC (both)", local_only: "Local Authentication Only", oidc_only: "OIDC Only" } as Record<string, string>)[displayData?.auth_mode || "both"]}
                  </div>
                )}
                <FieldError error={getFieldError(fieldErrors, "auth_mode")} />
              </div>

              {/* OIDC Discovery URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  OIDC Discovery URL
                </label>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      name="oidc_discovery_url"
                      value={displayData?.oidc_discovery_url || ""}
                      onChange={handleChange}
                      disabled={displayData?.auth_mode === "local_only"}
                      className={`w-full px-3 py-2 border ${
                        getFieldError(fieldErrors, "oidc_discovery_url")
                          ? "border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm disabled:opacity-50`}
                      placeholder="https://idp.example.com/application/o/linguard/.well-known/openid-configuration"
                    />
                    <FieldError error={getFieldError(fieldErrors, "oidc_discovery_url")} />
                  </>
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm break-all">
                    {displayData?.oidc_discovery_url || "Not configured"}
                  </div>
                )}
              </div>

              {/* Client ID */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Client ID
                </label>
                {isEditing ? (
                  <input
                    type="text"
                    name="oidc_client_id"
                    value={displayData?.oidc_client_id || ""}
                    onChange={handleChange}
                    disabled={displayData?.auth_mode === "local_only"}
                    className={`w-full px-3 py-2 border ${
                      getFieldError(fieldErrors, "oidc_client_id")
                        ? "border-red-500"
                        : "border-gray-300 dark:border-gray-600"
                    } dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm disabled:opacity-50`}
                    placeholder="linguard"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                    {displayData?.oidc_client_id || "Not configured"}
                  </div>
                )}
                <FieldError error={getFieldError(fieldErrors, "oidc_client_id")} />
              </div>

              {/* Client Secret */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Client Secret
                </label>
                {isEditing ? (
                  <input
                    type="password"
                    name="oidc_client_secret"
                    value={displayData?.oidc_client_secret || ""}
                    onChange={handleChange}
                    disabled={displayData?.auth_mode === "local_only"}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm disabled:opacity-50"
                    placeholder="Client secret from your identity provider"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                    {displayData?.oidc_client_secret ? "•".repeat(16) : "Not configured"}
                  </div>
                )}
              </div>

              {/* Scopes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Scopes
                </label>
                {isEditing ? (
                  <input
                    type="text"
                    name="oidc_scopes"
                    value={displayData?.oidc_scopes || "openid email profile"}
                    onChange={handleChange}
                    disabled={displayData?.auth_mode === "local_only"}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm disabled:opacity-50"
                    placeholder="openid email profile"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                    {displayData?.oidc_scopes || "openid email profile"}
                  </div>
                )}
              </div>

              {/* Provider Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Provider Display Name (optional)
                </label>
                {isEditing ? (
                  <input
                    type="text"
                    name="oidc_provider_name"
                    value={displayData?.oidc_provider_name || ""}
                    onChange={handleChange}
                    disabled={displayData?.auth_mode === "local_only"}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
                    placeholder="Authentik"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300">
                    {displayData?.oidc_provider_name || "Auto-detected from discovery URL"}
                  </div>
                )}
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Shown on the login button: "Sign in with {displayData?.oidc_provider_name || "…"}"
                </p>
              </div>

              {/* Auto Provision */}
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  name="oidc_auto_provision"
                  checked={displayData?.oidc_auto_provision ?? true}
                  onChange={handleChange}
                  disabled={!isEditing || displayData?.auth_mode === "local_only"}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:opacity-50"
                />
                <label className="text-sm text-gray-700 dark:text-gray-300">
                  Automatically create users on first sign-in
                </label>
              </div>

              {/* Admin Groups */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Admin Groups
                </label>
                {isEditing ? (
                  <input
                    type="text"
                    name="oidc_admin_groups"
                    value={displayData?.oidc_admin_groups || ""}
                    onChange={handleChange}
                    disabled={displayData?.auth_mode === "local_only"}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm disabled:opacity-50"
                    placeholder="linguard-admins, wireguard-admins"
                  />
                ) : (
                  <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm">
                    {displayData?.oidc_admin_groups || "None"}
                  </div>
                )}
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Comma-separated list of group names. Users whose identity provider
                  groups claim contains any of these get administrator privileges.
                </p>
              </div>

              {/* Test Connection */}
              <div>
                <button
                  type="button"
                  onClick={handleOidcTest}
                  disabled={oidcTesting || displayData?.auth_mode === "local_only"}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg flex items-center gap-2 transition-colors text-sm font-medium"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  {oidcTesting ? "Testing..." : "Test Connection"}
                </button>
                {oidcTestResult && (
                  <div
                    className={`mt-2 text-sm px-3 py-2 rounded-lg border ${
                      oidcTestResult.success
                        ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300"
                        : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300"
                    }`}
                  >
                    {oidcTestResult.message}
                  </div>
                )}
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {isEditing
                    ? "Test uses the values currently in the form. Save settings to apply them."
                    : "Test uses the saved configuration."}
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          {isEditing && (
            <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg">
              <button
                type="button"
                onClick={handleCancel}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-800 text-white rounded-lg font-medium transition-colors"
              >
                {updateMutation.isPending ? "Saving..." : "Save Settings"}
              </button>
            </div>
          )}
        </form>
      </div>

      {/* Information Panel */}
      <div className="mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <div className="flex items-start gap-3">
          <svg
            className="w-6 h-6 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-300 mb-1">
              About DNS Hierarchy
            </h3>
            <p className="text-sm text-blue-800 dark:text-blue-400">
              Settings follow a hierarchical inheritance model:{" "}
              <strong>Global → Server → Peer</strong>. DNS settings configured
              at the global level will be inherited by servers and peers unless
              they explicitly override them. This allows for flexible
              configuration while maintaining sensible defaults throughout your
              infrastructure.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
