import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Server } from "../types";
import type { FieldErrors } from "../utils/errorUtils";
import { getFieldError } from "../utils/errorUtils";
import { serversAPI, utilsAPI } from "../services/api";
import CustomSelect from "./CustomSelect";
import ToggleSwitch from "./ToggleSwitch";
import FieldError from "./FieldError";

interface ServerFormProps {
  server: Server | null;
  servers: Server[];
  onSubmit: (data: any) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  fieldErrors?: FieldErrors;
}

export default function ServerForm({
  server,
  servers,
  onSubmit,
  onCancel,
  isSubmitting,
  fieldErrors = {},
}: ServerFormProps) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    interface: "",
    listen_port: 51820,
    endpoint: "",
    ipv4_address: "",
    ipv6_address: "",
    dns_primary: "",
    dns_secondary: "",
    bounce_via_server_id: "",
    public_key: "",
    private_key: "",
    autostart: true,  // Default to true for new servers
  });

  const [keysLoading, setKeysLoading] = useState(false);

  // Fetch autofill defaults for new servers
  const { data: defaults } = useQuery({
    queryKey: ["server-defaults"],
    queryFn: serversAPI.getDefaults,
    enabled: !server, // Only fetch for new servers
  });

  // Initialize form with server data or defaults
  useEffect(() => {
    if (server) {
      setFormData({
        name: server.name,
        description: server.description || "",
        interface: server.interface,
        listen_port: server.listen_port,
        endpoint: server.endpoint,
        ipv4_address: server.ipv4_address || "",
        ipv6_address: server.ipv6_address || "",
        dns_primary: server.dns_primary || "",
        dns_secondary: server.dns_secondary || "",
        bounce_via_server_id: server.bounce_via_server_id?.toString() || "",
        public_key: server.public_key || "",
        private_key: server.private_key || "",
        autostart: server.autostart ?? true,  // Default to true if undefined
      });
    } else if (defaults) {
      setFormData((prev) => ({
        ...prev,
        interface: defaults.interface || prev.interface,
        listen_port: defaults.listen_port || prev.listen_port,
        ipv4_address: defaults.ipv4_address || prev.ipv4_address,
        ipv6_address: defaults.ipv6_address || prev.ipv6_address,
        dns_primary: defaults.dns_primary || prev.dns_primary,
        dns_secondary: defaults.dns_secondary || prev.dns_secondary,
      }));
    }
  }, [server, defaults]);

  // Generate keys for new servers
  useEffect(() => {
    if (!server && !formData.public_key && !keysLoading) {
      const generateKeys = async () => {
        setKeysLoading(true);
        try {
          const response = await utilsAPI.generateKeypair();
          setFormData((prev) => ({
            ...prev,
            public_key: response.public_key,
            private_key: response.private_key,
          }));
        } catch (error) {
          console.error("Failed to generate keys:", error);
        } finally {
          setKeysLoading(false);
        }
      };
      generateKeys();
    }
  }, [server, formData.public_key, keysLoading]);

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const submitData: any = {
      name: formData.name,
      // interface is auto-detected, don't send it
      listen_port: parseInt(formData.listen_port.toString()),
      endpoint: formData.endpoint,
      public_key: formData.public_key,
      private_key: formData.private_key,
      autostart: formData.autostart,
    };

    if (formData.description) submitData.description = formData.description;
    
    // For IP addresses: when editing, always send them (even if empty) so backend can delete
    // When creating, only send if they have a value
    if (server) {
      // Editing: always include IP addresses (empty string will be converted to null in backend)
      submitData.ipv4_address = formData.ipv4_address || "";
      submitData.ipv6_address = formData.ipv6_address || "";
    } else {
      // Creating: only include if not empty
      if (formData.ipv4_address) submitData.ipv4_address = formData.ipv4_address;
      if (formData.ipv6_address) submitData.ipv6_address = formData.ipv6_address;
    }
    
    if (formData.dns_primary) submitData.dns_primary = formData.dns_primary;
    if (formData.dns_secondary)
      submitData.dns_secondary = formData.dns_secondary;
    if (formData.bounce_via_server_id) {
      submitData.bounce_via_server_id = parseInt(formData.bounce_via_server_id);
    }

    onSubmit(submitData);
  };

  // Available bounce servers (exclude current server when editing)
  const availableBounceServers = servers.filter((s) => s.id !== server?.id);

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
      onClick={onCancel}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          {/* Header */}
          <div className="sticky top-0 z-[60] bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              {server ? "Edit Server" : "Create New Server"}
            </h2>
            <button
              type="button"
              onClick={onCancel}
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
                  Server Name *
                </label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  required
                  className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'name') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                  placeholder="My WireGuard Server"
                />
                <FieldError error={getFieldError(fieldErrors, 'name')} />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  rows={2}
                  className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'description') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                  placeholder="Optional description"
                />
                <FieldError error={getFieldError(fieldErrors, 'description')} />
              </div>
            </div>

            {/* Network Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Network Configuration
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Public Endpoint *
                  </label>
                  <input
                    type="text"
                    name="endpoint"
                    value={formData.endpoint}
                    onChange={handleChange}
                    required
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'endpoint') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="vpn.example.com or 1.2.3.4"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'endpoint')} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Listen Port *
                  </label>
                  <input
                    type="number"
                    name="listen_port"
                    value={formData.listen_port}
                    onChange={handleChange}
                    required
                    min="1"
                    max="65535"
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'listen_port') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                  />
                  <FieldError error={getFieldError(fieldErrors, 'listen_port')} />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    IPv4 Address (CIDR)
                  </label>
                  <input
                    type="text"
                    name="ipv4_address"
                    value={formData.ipv4_address}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv4_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="10.0.0.1/24"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'ipv4_address')} />
                  {!getFieldError(fieldErrors, 'ipv4_address') && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Server IP address with subnet (e.g., 10.0.0.1/24)
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    IPv6 Address (CIDR)
                  </label>
                  <input
                    type="text"
                    name="ipv6_address"
                    value={formData.ipv6_address}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv6_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="fd00::1/64"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'ipv6_address')} />
                  {!getFieldError(fieldErrors, 'ipv6_address') && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Server IPv6 address with subnet (e.g., fd00::1/64)
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* DNS Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                DNS Configuration
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Primary DNS
                  </label>
                  <input
                    type="text"
                    name="dns_primary"
                    value={formData.dns_primary}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'dns_primary') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="8.8.8.8"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'dns_primary')} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Secondary DNS
                  </label>
                  <input
                    type="text"
                    name="dns_secondary"
                    value={formData.dns_secondary}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'dns_secondary') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="8.8.4.4"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'dns_secondary')} />
                </div>
              </div>
            </div>

            {/* Security */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Security
              </h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Public Key
                </label>
                <input
                  type="text"
                  name="public_key"
                  value={formData.public_key}
                  disabled={!!server}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-700 dark:text-gray-300 font-mono text-sm cursor-not-allowed"
                  readOnly
                />
              </div>
            </div>

            {/* Advanced Options */}
            {availableBounceServers.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Advanced Options
                </h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Bounce Server (Optional)
                  </label>
                  <CustomSelect
                    value={formData.bounce_via_server_id}
                    onChange={(value) =>
                      setFormData((prev) => ({
                        ...prev,
                        bounce_via_server_id: value.toString(),
                      }))
                    }
                    options={[
                      { value: "", label: "None" },
                      ...availableBounceServers.map((s) => ({
                        value: s.id.toString(),
                        label: `${s.name} (${s.endpoint})`,
                      })),
                    ]}
                    placeholder="None"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'bounce_via_server_id')} />
                  {!getFieldError(fieldErrors, 'bounce_via_server_id') && (
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                      Route this server's traffic through another WireGuard server
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Auto-start Setting */}
          <div className="px-6 pb-6">
            <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-4">
                Server Settings
              </h3>
              <ToggleSwitch
                id="autostart"
                checked={formData.autostart}
                onChange={(checked) => setFormData({ ...formData, autostart: checked })}
                label="Auto-start on boot"
              />
              <p className="ml-14 text-xs text-gray-500 dark:text-gray-400 mt-1">
                Automatically start this server when Linguard boots up
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 dark:bg-blue-700 hover:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-500 text-white rounded-lg font-medium transition-colors"
            >
              {isSubmitting
                ? "Saving..."
                : server
                  ? "Update Server"
                  : "Create Server"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
