import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { setupAPI, authAPI, settingsAPI, backupKeyError } from "../../services/apiClient";
import { useAuthStore } from "../../store/auth";
import { loadSetupState, saveSetupState } from "../../utils/setupStorage";
import ToggleSwitch from "../../components/ToggleSwitch";
import type { FieldErrors } from "../../utils/errorUtils";
import {
  parseValidationErrors,
  getFieldError,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from "../../utils/errorUtils";
import FieldError from "../../components/FieldError";

interface GlobalSettingsStepProps {
  onNext: (data: any) => void;
  onBack: () => void;
  setupData?: any;
}

export default function GlobalSettingsStep({
  onNext,
  onBack,
  setupData,
}: GlobalSettingsStepProps) {
  const login = useAuthStore((state) => state.login);
  const logout = useAuthStore((state) => state.logout);

  // Generate a random secret key on mount
  const generateSecretKey = () => {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, (byte) => byte.toString(16).padStart(2, "0")).join(
      "",
    );
  };

  const [formData, setFormData] = useState({
    // DNS Configuration
    dns_primary: "1.1.1.1",
    dns_secondary: "8.8.8.8",
    // Security Settings (hidden - auto-generated)
    secret_key: generateSecretKey(),
    algorithm: "HS256",
    access_token_expire_minutes: 30,
    disable_auth: false,
    // Logging Settings (hidden - defaults, not shown in UI)
    log_level: "INFO",
    log_path: "./linguard.log",
    // Backup Settings
    backup_dir: "./backups",
    backup_retention_days: 30,
    backup_auto_cleanup_enabled: true,
    backup_periodic_enabled: true,
    backup_schedule_frequency: "weekly",
    backup_schedule_hour: 2,
    backup_schedule_minute: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [backupKey, setBackupKey] = useState("");
  const [keyPending, setKeyPending] = useState(() => loadSetupState()?.data.backup_key_pending === true);
  const [keySaved, setKeySaved] = useState(() => loadSetupState()?.data.backup_key_saved === true);
  const [savingKey, setSavingKey] = useState(false);
  const [keyAction, setKeyAction] = useState<"keep" | "replace" | "recover" | "delete" | null>(null);
  const queryClient = useQueryClient();
  const { data: keyStatus, isError: keyStatusError, isLoading: keyStatusLoading } = useQuery({
    queryKey: ["setup-backup-key-status"],
    queryFn: settingsAPI.getBackupKey,
    retry: false,
  });

  const markKeyPending = (pending: boolean, savedKey = keySaved) => {
    setKeyPending(pending);
    const saved = loadSetupState();
    saveSetupState({
      currentStep: saved?.currentStep ?? "globals",
      lastUpdated: new Date().toISOString(),
      data: { ...saved?.data, ...(setupData?.username ? { username: setupData.username } : {}), backup_key_pending: pending, backup_key_saved: savedKey },
    });
  };

  const configureMutation = useMutation({
    mutationFn: setupAPI.configureGlobals,
    onSuccess: async () => {
      setFieldErrors({}); // Clear errors on success
      // The previous token is invalid as soon as the signing key changes.
      logout();
      if (setupData?.username && setupData?.password) {
        try {
          const loginResponse = await authAPI.setupLogin(
            setupData.username,
            setupData.password,
          );
          if (loginResponse.user?.role !== "admin") throw new Error("Administrator privileges required");
          login(loginResponse.access_token, loginResponse.user?.role);
        } catch {
          console.error("[GlobalSettingsStep] Re-authentication failed");
        }
      }
      const { secret_key: _secretKey, ...settings } = formData;
      onNext(settings);
    },
    onError: (err: any) => {
      if (isValidationError(err)) {
        const errors = parseValidationErrors(err);
        setFieldErrors(errors);
        setError(formatErrorCount(countErrors(errors)));
      } else {
        setError(getGenericError(err, "Failed to configure global settings"));
      }
    },
  });

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    const value =
      e.target.type === "checkbox"
        ? (e.target as HTMLInputElement).checked
        : e.target.value;
    setFormData({ ...formData, [e.target.name]: value });
    setError(null);
    setFieldErrors({});
  };

  const handleGenerateSecret = () => {
    setFormData({ ...formData, secret_key: generateSecretKey() });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (savingKey || configureMutation.isPending) return;
    if (keyPending && (!backupKey || keyAction === "keep" || keyAction === "delete")) return;
    if (keyStatusLoading || keyStatusError || !keyStatus || (keyStatus.configured && !keyAction)) return;
    if ((keyAction === "replace" || keyAction === "recover") && !backupKey) return;

    // Prepare data with proper types
    const submitData = {
      ...formData,
      access_token_expire_minutes: Number(formData.access_token_expire_minutes),
      backup_retention_days: Number(formData.backup_retention_days),
      backup_schedule_hour: Number(formData.backup_schedule_hour),
      backup_schedule_minute: Number(formData.backup_schedule_minute),
    };

    if (backupKey || keyAction === "delete") {
      setSavingKey(true);
      setError(null);
      try {
        if (keyAction === "delete") await settingsAPI.clearBackupKey();
        else if (keyAction === "recover") await settingsAPI.recoverBackupKey(backupKey);
        else await settingsAPI.setBackupKey(backupKey);
        const configured = keyAction !== "delete";
        queryClient.setQueryData(["setup-backup-key-status"], { configured });
        markKeyPending(false, configured);
        setBackupKey("");
        setKeySaved(configured);
        setKeyAction(configured ? "keep" : null);
      } catch (err) {
        setError(backupKeyError(err, "Failed to save backup key. Retry or explicitly discard the unsaved key."));
        setSavingKey(false);
        return;
      }
      setSavingKey(false);
    }
    configureMutation.mutate(submitData);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Settings
        </h2>
        <p className="text-gray-600 dark:text-gray-300">
          Configure application settings. These can be modified later in the
          Settings page.
        </p>
      </div>

      {error && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* DNS Configuration */}
        <div className="bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
            DNS Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Primary DNS Server
              </label>
              <input
                type="text"
                name="dns_primary"
                value={formData.dns_primary}
                onChange={handleChange}
                className={`w-full px-3 py-2 border ${
                  getFieldError(fieldErrors, "dns_primary")
                    ? "border-red-500"
                    : "border-gray-300 dark:border-gray-600"
                } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                placeholder="1.1.1.1"
              />
              <FieldError error={getFieldError(fieldErrors, "dns_primary")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Secondary DNS Server
              </label>
              <input
                type="text"
                name="dns_secondary"
                value={formData.dns_secondary}
                onChange={handleChange}
                className={`w-full px-3 py-2 border ${
                  getFieldError(fieldErrors, "dns_secondary")
                    ? "border-red-500"
                    : "border-gray-300 dark:border-gray-600"
                } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                placeholder="8.8.8.8"
              />
              <FieldError error={getFieldError(fieldErrors, "dns_secondary")} />
            </div>
          </div>
        </div>

        {/* Backup Configuration */}
        <div className="bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
            Backup Configuration
          </h3>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">{keyStatusLoading ? "Loading backup key status..." : keyStatusError ? "Backup key status unavailable" : keyStatus?.status === "missing" ? "Backup key missing" : keyStatus?.configured ? "Backup key configured" : "Backup key not configured"}</p>
              {keyStatusError && <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">Cannot check the backup key. If the file is unsafe or unreadable, a local operator must repair it before continuing.</p>}
              {keyStatusError && <button type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ["setup-backup-key-status"] })} className="text-blue-700 dark:text-blue-400 underline">Retry key status</button>}
              {keyStatus?.configured && <fieldset className="mt-2 space-y-2 text-sm text-gray-700 dark:text-gray-300">
                <legend>Choose what to do with the {keyStatus.status === "missing" ? "missing" : "configured"} backup key</legend>
                <label className="block"><input type="radio" name="backup-key-action" checked={keyAction === "keep"} onChange={() => setKeyAction("keep")} /> Keep {keyStatus.status === "missing" ? "missing key configuration" : "current key"}</label>
                <label className="block"><input type="radio" name="backup-key-action" checked={keyAction === (keyStatus.status === "missing" ? "recover" : "replace")} onChange={() => setKeyAction(keyStatus.status === "missing" ? "recover" : "replace")} /> {keyStatus.status === "missing" ? "Recover missing key" : "Replace current key"}</label>
                <label className="block"><input type="radio" name="backup-key-action" checked={keyAction === "delete"} onChange={() => setKeyAction("delete")} /> Delete backup key</label>
                <p className="text-xs text-amber-800 dark:text-amber-300">Old backups require their original key. Deleting the key makes future backups unencrypted.{keyStatus.status === "missing" ? " Keeping a missing key prevents encrypted backups until it is recovered." : ""}</p>
              </fieldset>}
              <label htmlFor="setup-backup-key" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Backup encryption key (optional)</label>
              <input id="setup-backup-key" type="password" autoComplete="new-password" disabled={keyStatusLoading || keyStatusError || (keyStatus?.configured && keyAction !== "replace" && keyAction !== "recover")} value={backupKey} onChange={(e) => { setBackupKey(e.target.value); if (e.target.value && !keyPending) markKeyPending(true); }} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50" />
              <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">Unencrypted backups expose secrets. Save a copy of the key; it is required to restore encrypted backups.</p>
              {keySaved && !keyPending && <p className="mt-1 text-sm text-green-700 dark:text-green-400">Backup key saved during setup. Enter a key only to replace it.</p>}
              {keyPending && <div className="mt-2 text-sm text-amber-800 dark:text-amber-300"><p>A previously entered backup key was not confirmed saved. Re-enter it or explicitly discard the unsaved key.</p><button type="button" onClick={() => { setBackupKey(""); markKeyPending(false); }} className="underline">Discard unsaved key</button></div>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Backup Directory
              </label>
              <input
                type="text"
                name="backup_dir"
                value={formData.backup_dir}
                onChange={handleChange}
                className={`w-full px-3 py-2 border ${
                  getFieldError(fieldErrors, "backup_dir")
                    ? "border-red-500"
                    : "border-gray-300 dark:border-gray-600"
                } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm`}
                placeholder="./backups"
              />
              <FieldError error={getFieldError(fieldErrors, "backup_dir")} />
            </div>

            {/* Auto Cleanup Toggle */}
            <div>
              <ToggleSwitch
                id="backup_auto_cleanup_enabled"
                enabled={formData.backup_auto_cleanup_enabled}
                onChange={(enabled) =>
                  handleChange({
                    target: {
                      name: "backup_auto_cleanup_enabled",
                      type: "checkbox",
                      checked: enabled,
                    },
                  } as any)
                }
                label="Enable automatic cleanup of old backups"
              />
              <p className="ml-6 mt-1 text-xs text-gray-500 dark:text-gray-400">
                Automatically delete backups older than the retention period
              </p>
            </div>

            {/* Retention Period - only show when cleanup is enabled */}
            {formData.backup_auto_cleanup_enabled && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Retention Period (days)
                </label>
                <input
                  type="number"
                  name="backup_retention_days"
                  value={formData.backup_retention_days}
                  onChange={handleChange}
                  min="1"
                  max="365"
                  className={`w-full px-3 py-2 border ${
                    getFieldError(fieldErrors, "backup_retention_days")
                      ? "border-red-500"
                      : "border-gray-300 dark:border-gray-600"
                  } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                />
                <FieldError
                  error={getFieldError(fieldErrors, "backup_retention_days")}
                />
                {!getFieldError(fieldErrors, "backup_retention_days") && (
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Backups older than this period will be automatically deleted
                  </p>
                )}
              </div>
            )}

            {/* Periodic Backup Toggle */}
            <div>
              <ToggleSwitch
                id="backup_periodic_enabled"
                enabled={formData.backup_periodic_enabled}
                onChange={(enabled) =>
                  handleChange({
                    target: {
                      name: "backup_periodic_enabled",
                      type: "checkbox",
                      checked: enabled,
                    },
                  } as any)
                }
                label="Enable scheduled automatic backups"
              />
              <p className="ml-6 mt-1 text-xs text-gray-500 dark:text-gray-400">
                Create backups automatically at the scheduled time
              </p>
            </div>

            {/* Backup Schedule - only show when periodic is enabled */}
            {formData.backup_periodic_enabled && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Backup Schedule
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    name="backup_schedule_frequency"
                    value={formData.backup_schedule_frequency}
                    onChange={handleChange}
                    className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                  <span className="text-gray-700 dark:text-gray-300">at</span>
                  <input
                    type="number"
                    name="backup_schedule_hour"
                    value={formData.backup_schedule_hour}
                    onChange={handleChange}
                    min="0"
                    max="23"
                    className={`w-20 px-3 py-2 border ${
                      getFieldError(fieldErrors, "backup_schedule_hour")
                        ? "border-red-500"
                        : "border-gray-300 dark:border-gray-600"
                    } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center font-mono`}
                    placeholder="HH"
                  />
                  <span className="text-gray-700 dark:text-gray-300 font-mono text-lg">
                    :
                  </span>
                  <input
                    type="number"
                    name="backup_schedule_minute"
                    value={formData.backup_schedule_minute}
                    onChange={handleChange}
                    min="0"
                    max="59"
                    className={`w-20 px-3 py-2 border ${
                      getFieldError(fieldErrors, "backup_schedule_minute")
                        ? "border-red-500"
                        : "border-gray-300 dark:border-gray-600"
                    } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center font-mono`}
                    placeholder="MM"
                  />
                </div>
                <FieldError
                  error={getFieldError(fieldErrors, "backup_schedule_hour")}
                />
                <FieldError
                  error={getFieldError(fieldErrors, "backup_schedule_minute")}
                />
                {!getFieldError(fieldErrors, "backup_schedule_hour") &&
                  !getFieldError(fieldErrors, "backup_schedule_minute") && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {formData.backup_schedule_frequency === "weekly" &&
                        "Backups will run every Monday at the specified time"}
                      {formData.backup_schedule_frequency === "monthly" &&
                        "Backups will run on the 1st of each month at the specified time"}
                      {formData.backup_schedule_frequency === "daily" &&
                        "Backups will run every day at the specified time"}
                    </p>
                  )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between pt-4">
          <button
            type="button"
            onClick={onBack}
            className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Back
          </button>
          <button
            type="submit"
            disabled={configureMutation.isPending || savingKey || keyStatusLoading || keyStatusError || !keyStatus || (keyPending && (!backupKey || keyAction === "keep" || keyAction === "delete")) || (keyStatus.configured && !keyAction) || ((keyAction === "replace" || keyAction === "recover") && !backupKey)}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            {configureMutation.isPending || savingKey ? "Saving..." : "Save & Continue"}
          </button>
        </div>
      </form>
    </div>
  );
}
