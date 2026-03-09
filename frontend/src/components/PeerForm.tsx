import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Peer, Server } from "../types";
import type { FieldErrors } from "../utils/errorUtils";
import { getFieldError } from "../utils/errorUtils";
import { peersAPI, utilsAPI } from "../services/api";
import CustomSelect from "./CustomSelect";
import FieldError from "./FieldError";
import ToggleSwitch from "./ToggleSwitch";

interface PeerFormProps {
  peer: Peer | null;
  servers: Server[];
  onSubmit: (data: any) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  fieldErrors?: FieldErrors;
}

export default function PeerForm({
  peer,
  servers,
  onSubmit,
  onCancel,
  isSubmitting,
  fieldErrors = {},
}: PeerFormProps) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    server_id: "",
    preshared_key: "",
    address: "",
    ipv4_address: "",
    ipv6_address: "",
    allowed_ips: "0.0.0.0/0, ::/0",
    dns_primary: "",
    dns_secondary: "",
    persistent_keepalive: 25,
    enabled: true,
    public_key: "",
    private_key: "",
  });

  const [keysLoading, setKeysLoading] = useState(false);

  // Helper function to check if an IP is in a given subnet
  const isIPInSubnet = (ip: string, subnet: string): boolean => {
    if (!ip || !subnet) return false;

    // Extract IP and CIDR from subnet (e.g., "10.0.0.1/24" -> ["10.0.0.1", "24"])
    const [subnetIP, cidr] = subnet.split("/");
    if (!cidr) return false;

    const cidrNum = parseInt(cidr);

    // Simple IPv4 check (supports /8, /16, /24, /32)
    if (ip.includes(".") && subnetIP.includes(".")) {
      const ipParts = ip.split(".").map(Number);
      const subnetParts = subnetIP.split(".").map(Number);

      // Check based on CIDR
      if (cidrNum >= 24)
        return (
          ipParts[0] === subnetParts[0] &&
          ipParts[1] === subnetParts[1] &&
          ipParts[2] === subnetParts[2]
        );
      if (cidrNum >= 16)
        return ipParts[0] === subnetParts[0] && ipParts[1] === subnetParts[1];
      if (cidrNum >= 8) return ipParts[0] === subnetParts[0];
      return false;
    }

    // Simple IPv6 prefix check
    if (ip.includes(":") && subnetIP.includes(":")) {
      // For IPv6, check if they share the same prefix (simplified)
      const ipPrefix = ip.split(":").slice(0, 4).join(":");
      const subnetPrefix = subnetIP.split(":").slice(0, 4).join(":");
      return ipPrefix === subnetPrefix;
    }

    return false;
  };

  // Fetch autofill defaults for new peers
  const { data: defaults } = useQuery({
    queryKey: ["peer-defaults", formData.server_id],
    queryFn: () => peersAPI.getDefaults(parseInt(formData.server_id)),
    enabled: !peer && !!formData.server_id,
  });

  // Initialize form with peer data or defaults
  useEffect(() => {
    if (peer) {
      setFormData({
        name: peer.name,
        description: peer.description || "",
        server_id: peer.server_id.toString(),
        preshared_key: peer.preshared_key || "",
        address: peer.address,
        ipv4_address: peer.ipv4_address || "",
        ipv6_address: peer.ipv6_address || "",
        allowed_ips: peer.allowed_ips,
        dns_primary: peer.dns_primary || "",
        dns_secondary: peer.dns_secondary || "",
        persistent_keepalive: peer.persistent_keepalive,
        enabled: peer.enabled,
        public_key: peer.public_key || "",
        private_key: peer.private_key || "",
      });
    } else if (defaults) {
      // Find the selected server to check subnets
      const selectedServer = servers.find(
        (s) => s.id.toString() === formData.server_id,
      );

      setFormData((prev) => {
        const updates: any = {};

        // Only autofill IPv4 if current value is empty OR not in the same subnet as the server
        if (defaults.ipv4_address) {
          const shouldAutofillIPv4 =
            !prev.ipv4_address ||
            (selectedServer?.ipv4_address &&
              !isIPInSubnet(prev.ipv4_address, selectedServer.ipv4_address));

          if (shouldAutofillIPv4) {
            updates.ipv4_address = defaults.ipv4_address;
          }
        }

        // Only autofill IPv6 if current value is empty OR not in the same subnet as the server
        if (defaults.ipv6_address) {
          const shouldAutofillIPv6 =
            !prev.ipv6_address ||
            (selectedServer?.ipv6_address &&
              !isIPInSubnet(prev.ipv6_address, selectedServer.ipv6_address));

          if (shouldAutofillIPv6) {
            updates.ipv6_address = defaults.ipv6_address;
          }
        }

        // Always autofill DNS if empty
        if (defaults.dns_primary && !prev.dns_primary) {
          updates.dns_primary = defaults.dns_primary;
        }
        if (defaults.dns_secondary && !prev.dns_secondary) {
          updates.dns_secondary = defaults.dns_secondary;
        }

        return { ...prev, ...updates };
      });
    }
  }, [peer, defaults, formData.server_id, servers]);

  // Generate keys for new peers
  useEffect(() => {
    if (!peer && !formData.public_key && !keysLoading) {
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
  }, [peer, formData.public_key, keysLoading]);

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >,
  ) => {
    const { name, value, type } = e.target;
    const checked = (e.target as HTMLInputElement).checked;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const submitData: any = {
      name: formData.name,
      server_id: parseInt(formData.server_id),
      allowed_ips: formData.allowed_ips,
      persistent_keepalive: parseInt(formData.persistent_keepalive.toString()),
      enabled: formData.enabled,
      public_key: formData.public_key,
      private_key: formData.private_key,
    };

    if (formData.description) submitData.description = formData.description;
    if (formData.preshared_key)
      submitData.preshared_key = formData.preshared_key;
    if (formData.address) submitData.address = formData.address;
    
    // For IP addresses: when editing, always send them (even if empty) so backend can delete
    // When creating, only send if they have a value
    if (peer) {
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

    onSubmit(submitData);
  };

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
              {peer ? "Edit Peer" : "Create New Peer"}
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

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Peer Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'name') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="John's Laptop"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'name')} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Server *
                  </label>
                  <CustomSelect
                    value={formData.server_id}
                    onChange={(value) =>
                      setFormData((prev) => ({
                        ...prev,
                        server_id: value.toString(),
                      }))
                    }
                    options={[
                      { value: "", label: "Select a server" },
                      ...servers.map((server: Server) => ({
                        value: server.id.toString(),
                        label: `${server.name} (${server.endpoint})`,
                      })),
                    ]}
                    placeholder="Select a server"
                    className={peer ? "opacity-50 pointer-events-none" : ""}
                  />
                  <FieldError error={getFieldError(fieldErrors, 'server_id')} />
                </div>
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

              <ToggleSwitch
                id="enabled"
                checked={formData.enabled}
                onChange={(checked) => setFormData({ ...formData, enabled: checked })}
                label="Enable this peer"
              />
            </div>

            {/* IP Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                IP Configuration
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    IPv4 Address
                  </label>
                  <input
                    type="text"
                    name="ipv4_address"
                    value={formData.ipv4_address}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv4_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="10.0.0.2"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'ipv4_address')} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    IPv6 Address
                  </label>
                  <input
                    type="text"
                    name="ipv6_address"
                    value={formData.ipv6_address}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv6_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                    placeholder="fd00::2"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'ipv6_address')} />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Allowed IPs *
                </label>
                <input
                  type="text"
                  name="allowed_ips"
                  value={formData.allowed_ips}
                  onChange={handleChange}
                  required
                  className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'allowed_ips') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                  placeholder="0.0.0.0/0, ::/0"
                />
                <FieldError error={getFieldError(fieldErrors, 'allowed_ips')} />
                {!getFieldError(fieldErrors, 'allowed_ips') && (
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    IP ranges that will be routed through the VPN (default: all
                    traffic)
                  </p>
                )}
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
                    placeholder="Auto-filled from server"
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
                    placeholder="Auto-filled from server"
                  />
                  <FieldError error={getFieldError(fieldErrors, 'dns_secondary')} />
                </div>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Leave empty to inherit from server or global settings
              </p>
            </div>

            {/* Keys */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Security
              </h3>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Preshared Key (Optional)
                </label>
                <input
                  type="text"
                  name="preshared_key"
                  value={formData.preshared_key}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                  placeholder="Optional additional layer of symmetric encryption"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Adds post-quantum security. Leave empty to omit.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Public Key
                </label>
                <input
                  type="text"
                  name="public_key"
                  value={formData.public_key}
                  disabled={!!peer}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-700 dark:text-gray-300 font-mono text-sm cursor-not-allowed"
                  readOnly
                />
              </div>
            </div>

            {/* Advanced Options */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Advanced Options
              </h3>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Persistent Keepalive (seconds)
                </label>
                <input
                  type="number"
                  name="persistent_keepalive"
                  value={formData.persistent_keepalive}
                  onChange={handleChange}
                  min="0"
                  max="65535"
                  className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'persistent_keepalive') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500`}
                />
                <FieldError error={getFieldError(fieldErrors, 'persistent_keepalive')} />
                {!getFieldError(fieldErrors, 'persistent_keepalive') && (
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Keep connection alive through NAT/firewalls (recommended: 25)
                  </p>
                )}
              </div>
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
                : peer
                  ? "Update Peer"
                  : "Create Peer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
