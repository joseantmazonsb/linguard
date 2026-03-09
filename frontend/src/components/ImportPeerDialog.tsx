import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Server } from "../types";
import CustomSelect from "./CustomSelect";
import ToggleSwitch from "./ToggleSwitch";
import { utilsAPI, peersAPI } from "../services/api";

interface ImportPeerDialogProps {
  servers: Server[];
  selectedServerId?: number;
  onImport: (data: any) => void;
  onClose: () => void;
  isPending?: boolean;
}

interface ParsedPeerData {
  name: string;
  private_key: string;
  ipv4_address?: string;
  ipv6_address?: string;
  dns_primary?: string;
  dns_secondary?: string;
  server_public_key?: string;
  preshared_key?: string;
  ipv4_allowed_ips?: string;
  ipv6_allowed_ips?: string;
  persistent_keepalive?: number;
  server_endpoint?: string;
  server_port?: number;
}

export default function ImportPeerDialog({
  servers,
  selectedServerId,
  onImport,
  onClose,
  isPending = false,
}: ImportPeerDialogProps) {
  const [step, setStep] = useState<"upload" | "review">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [parsedData, setParsedData] = useState<ParsedPeerData | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    server_id: selectedServerId || "",
    name: "",
    description: "",
    private_key: "",
    public_key: "",
    ipv4_address: "",
    ipv6_address: "",
    dns_primary: "",
    dns_secondary: "",
    preshared_key: "",
    ipv4_allowed_ips: "",
    ipv6_allowed_ips: "",
    persistent_keepalive: 25,
    enabled: true,
  });

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

  // Fetch autofill defaults when server is selected
  const { data: defaults } = useQuery({
    queryKey: ["peer-defaults", formData.server_id],
    queryFn: () =>
      peersAPI.getDefaults(parseInt(formData.server_id.toString())),
    enabled: step === "review" && !!formData.server_id,
  });

  // Autofill IPs and DNS when server is selected and defaults are available
  useEffect(() => {
    if (defaults && step === "review") {
      const selectedServer = servers.find(
        (s) => s.id.toString() === formData.server_id.toString(),
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
  }, [defaults, formData.server_id, servers, step]);

  const parseConfigFile = async (file: File) => {
    try {
      const content = await file.text();
      const lines = content.split("\n");

      const data: any = {
        interface: {},
        peer: {},
      };

      let currentSection = "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;

        if (trimmed === "[Interface]") {
          currentSection = "interface";
          continue;
        } else if (trimmed === "[Peer]") {
          currentSection = "peer";
          continue;
        }

        if (trimmed.includes("=")) {
          const equalIndex = trimmed.indexOf("=");
          const key = trimmed.substring(0, equalIndex).trim();
          const value = trimmed.substring(equalIndex + 1).trim();
          if (currentSection === "interface") {
            data.interface[key] = value;
          } else if (currentSection === "peer") {
            data.peer[key] = value;
          }
        }
      }

      // Extract name from filename
      const name = file.name.replace(".conf", "").replace(".wg", "");

      // Parse Address field
      const addresses = (data.interface.Address || "")
        .split(",")
        .map((s: string) => s.trim());
      let ipv4_address = "";
      let ipv6_address = "";

      for (const addr of addresses) {
        if (addr.includes(":")) {
          ipv6_address = addr;
        } else if (addr) {
          ipv4_address = addr;
        }
      }

      // Parse DNS
      const dnsList = (data.interface.DNS || "")
        .split(",")
        .map((s: string) => s.trim())
        .filter(Boolean);
      const dns_primary = dnsList[0] || "";
      const dns_secondary = dnsList[1] || "";

      // Parse AllowedIPs
      const allowedIPs = (data.peer.AllowedIPs || "")
        .split(",")
        .map((s: string) => s.trim());
      let ipv4_allowed: string[] = [];
      let ipv6_allowed: string[] = [];

      for (const ip of allowedIPs) {
        if (ip.includes(":")) {
          ipv6_allowed.push(ip);
        } else if (ip) {
          ipv4_allowed.push(ip);
        }
      }

      const parsed: ParsedPeerData = {
        name,
        private_key: (data.interface.PrivateKey || "").trim(),
        ipv4_address,
        ipv6_address,
        dns_primary,
        dns_secondary,
        server_public_key: (data.peer.PublicKey || "").trim(),
        preshared_key: (data.peer.PresharedKey || "").trim(),
        ipv4_allowed_ips: ipv4_allowed.join(", "),
        ipv6_allowed_ips: ipv6_allowed.join(", "),
        persistent_keepalive: parseInt(data.peer.PersistentKeepalive || "25"),
        server_endpoint: data.peer.Endpoint
          ? data.peer.Endpoint.split(":")[0]
          : "",
        server_port: data.peer.Endpoint
          ? parseInt(data.peer.Endpoint.split(":")[1])
          : undefined,
      };

      if (!parsed.private_key) {
        throw new Error("PrivateKey not found in configuration file");
      }

      return parsed;
    } catch (error) {
      throw new Error(
        `Failed to parse config: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith(".conf") || file.type === "text/plain") {
        await handleFileSelect(file);
      } else {
        setParseError(
          "Please select a valid WireGuard configuration file (.conf)",
        );
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleFileSelect(e.target.files[0]);
    }
  };

  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setParseError(null);

    try {
      const parsed = await parseConfigFile(file);
      setParsedData(parsed);

      // Generate public key from private key
      let publicKey = "";
      try {
        console.log("Deriving public key from private key:", {
          length: parsed.private_key.length,
          hasWhitespace: /\s/.test(parsed.private_key),
          firstChars: parsed.private_key.substring(0, 10),
          lastChars: parsed.private_key.substring(
            parsed.private_key.length - 10,
          ),
        });
        const keyData = await utilsAPI.derivePublicKey(parsed.private_key);
        publicKey = keyData.public_key;
      } catch (error: any) {
        console.error("Failed to derive public key:", error);
        console.error("Error details:", {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status,
        });
        const errorMsg =
          error.response?.data?.detail ||
          "Failed to derive public key from private key. Please check the private key is valid.";
        setParseError(errorMsg);
        return;
      }

      // Pre-populate form
      setFormData((prev) => ({
        ...prev,
        name: parsed.name,
        private_key: parsed.private_key,
        public_key: publicKey,
        ipv4_address: parsed.ipv4_address || "",
        ipv6_address: parsed.ipv6_address || "",
        dns_primary: parsed.dns_primary || "",
        dns_secondary: parsed.dns_secondary || "",
        preshared_key: parsed.preshared_key || "",
        ipv4_allowed_ips: parsed.ipv4_allowed_ips || "0.0.0.0/0",
        ipv6_allowed_ips: parsed.ipv6_allowed_ips || "::/0",
        persistent_keepalive: parsed.persistent_keepalive || 25,
      }));

      setStep("review");
    } catch (error) {
      setParseError(
        error instanceof Error ? error.message : "Failed to parse file",
      );
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
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

    if (!formData.server_id) {
      alert("Please select a server");
      return;
    }

    const submitData: any = {
      server_id: parseInt(formData.server_id.toString()),
      name: formData.name,
      private_key: formData.private_key,
      public_key: formData.public_key,
      persistent_keepalive: parseInt(formData.persistent_keepalive.toString()),
      enabled: formData.enabled,
    };

    if (formData.description) submitData.description = formData.description;
    if (formData.ipv4_address) submitData.ipv4_address = formData.ipv4_address;
    if (formData.ipv6_address) submitData.ipv6_address = formData.ipv6_address;
    if (formData.dns_primary) submitData.dns_primary = formData.dns_primary;
    if (formData.dns_secondary)
      submitData.dns_secondary = formData.dns_secondary;
    if (formData.preshared_key)
      submitData.preshared_key = formData.preshared_key;
    if (formData.ipv4_allowed_ips)
      submitData.ipv4_allowed_ips = formData.ipv4_allowed_ips;
    if (formData.ipv6_allowed_ips)
      submitData.ipv6_allowed_ips = formData.ipv6_allowed_ips;

    onImport(submitData);
  };

  const handleBack = () => {
    setStep("upload");
    setSelectedFile(null);
    setParsedData(null);
    setParseError(null);
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full border border-gray-200 dark:border-gray-700 ${
          step === "review"
            ? "max-w-4xl max-h-[90vh] overflow-y-auto"
            : "max-w-lg"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {step === "upload" ? (
          <div>
            {/* Upload Step */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  Import Peer Configuration
                </h2>
                <button
                  type="button"
                  onClick={onClose}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
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
            </div>

            <div className="p-6 space-y-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Upload a WireGuard peer configuration file (.conf). You'll be
                able to review and edit the settings before importing.
              </p>

              {/* File Upload Area */}
              <div
                className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragActive
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                    : "border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500"
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  accept=".conf,text/plain"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />

                {selectedFile && !parseError ? (
                  <div className="space-y-2">
                    <svg
                      className="w-12 h-12 mx-auto text-green-500"
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
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {(selectedFile.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <svg
                      className="w-12 h-12 mx-auto text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      />
                    </svg>
                    <div>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        <span className="font-semibold text-blue-600 dark:text-blue-400">
                          Click to upload
                        </span>{" "}
                        or drag and drop
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-500">
                        WireGuard configuration file (.conf)
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {parseError && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <svg
                      className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <div>
                      <h4 className="text-sm font-semibold text-red-900 dark:text-red-200">
                        Parse Error
                      </h4>
                      <p className="text-sm text-red-800 dark:text-red-300 mt-1">
                        {parseError}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Info Box */}
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg
                    className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5"
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
                    <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200">
                      Import Requirements
                    </h4>
                    <p className="text-sm text-blue-800 dark:text-blue-300 mt-1">
                      The file must be a valid WireGuard peer configuration with
                      [Interface] and [Peer] sections including PrivateKey and
                      Address.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t border-gray-200 dark:border-gray-700">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {/* Review Step - Header */}
            <div className="sticky top-0 z-[60] bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
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
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  Review & Import Peer
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
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

            {/* Review Step - Body */}
            <div className="p-6 space-y-6">
              {/* Success message */}
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg
                    className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5"
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
                  <div>
                    <h4 className="text-sm font-semibold text-green-900 dark:text-green-200">
                      Configuration Parsed Successfully
                    </h4>
                    <p className="text-sm text-green-800 dark:text-green-300 mt-1">
                      Review the settings below and make any necessary
                      adjustments before importing.
                    </p>
                  </div>
                </div>
              </div>

              {/* Basic Information */}
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="John's Laptop"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Server *
                    </label>
                    <CustomSelect
                      value={formData.server_id}
                      onChange={(value) =>
                        setFormData((prev) => ({ ...prev, server_id: value }))
                      }
                      options={[
                        { value: "", label: "Select a server" },
                        ...servers.map((server) => ({
                          value: server.id,
                          label: `${server.name} (${server.endpoint})`,
                        })),
                      ]}
                      placeholder="Select a server"
                      disabled={isPending}
                    />
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
                    className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Optional description"
                  />
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      placeholder="10.0.0.2"
                    />
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      placeholder="fd00::2"
                    />
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
                    className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="0.0.0.0/0, ::/0"
                  />
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    IP ranges that will be routed through the VPN (default: all
                    traffic)
                  </p>
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Auto-filled from server"
                    />
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Auto-filled from server"
                    />
                  </div>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Leave empty to inherit from server or global settings
                </p>
              </div>

              {/* Security */}
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
                    className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                    placeholder="Optional additional layer of symmetric encryption"
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Adds post-quantum security. Leave empty to omit.
                  </p>
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
                    className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Keep connection alive through NAT/firewalls (recommended:
                    25)
                  </p>
                </div>
              </div>
            </div>

            {/* Review Step - Footer */}
            <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-between border-t border-gray-200 dark:border-gray-700 rounded-b-lg">
              <button
                type="button"
                onClick={handleBack}
                disabled={isPending}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
              >
                Back to Upload
              </button>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isPending}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    !formData.server_id || servers.length === 0 || isPending
                  }
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-500 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                >
                  {isPending ? "Importing..." : "Import Peer"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
