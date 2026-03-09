import { useState } from "react";
import type { Server } from "../types";
import CustomSelect from "./CustomSelect";
import { utilsAPI } from "../services/api";

interface ImportServerDialogProps {
  servers: Server[];
  onImport: (data: any) => void;
  onClose: () => void;
  isPending?: boolean;
}

interface ParsedServerData {
  name: string;
  interface: string;
  private_key: string;
  listen_port?: number;
  ipv4_address?: string;
  ipv6_address?: string;
  dns_primary?: string;
  dns_secondary?: string;
}

export default function ImportServerDialog({
  servers,
  onImport,
  onClose,
  isPending = false,
}: ImportServerDialogProps) {
  const [step, setStep] = useState<"upload" | "review">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [parsedData, setParsedData] = useState<ParsedServerData | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    private_key: "",
    public_key: "",
    listen_port: 51820,
    endpoint: "",
    ipv4_address: "",
    ipv6_address: "",
    dns_primary: "",
    dns_secondary: "",
    bounce_via_server_id: "",
  });

  const parseConfigFile = async (file: File) => {
    try {
      const content = await file.text();
      const lines = content.split("\n");

      const data: any = {
        interface: {},
        peers: [],
      };

      let currentSection = "";
      let currentPeer: any = null;

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;

        if (trimmed === "[Interface]") {
          currentSection = "interface";
          continue;
        } else if (trimmed === "[Peer]") {
          currentSection = "peer";
          currentPeer = {};
          data.peers.push(currentPeer);
          continue;
        }

        if (trimmed.includes("=")) {
          const equalIndex = trimmed.indexOf("=");
          const key = trimmed.substring(0, equalIndex).trim();
          const value = trimmed.substring(equalIndex + 1).trim();
          if (currentSection === "interface") {
            data.interface[key] = value;
          } else if (currentSection === "peer" && currentPeer) {
            currentPeer[key] = value;
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

      const parsed: ParsedServerData = {
        name,
        interface:
          name
            .toLowerCase()
            .replace(/[^a-z0-9]/g, "")
            .substring(0, 15) || "wg0",
        private_key: (data.interface.PrivateKey || "").trim(),
        listen_port: parseInt(data.interface.ListenPort) || 51820,
        ipv4_address,
        ipv6_address,
        dns_primary,
        dns_secondary,
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
        listen_port: parsed.listen_port || 51820,
        ipv4_address: parsed.ipv4_address || "",
        ipv6_address: parsed.ipv6_address || "",
        dns_primary: parsed.dns_primary || "",
        dns_secondary: parsed.dns_secondary || "",
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
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // interface is auto-detected by backend, don't send it
    const submitData: any = {
      name: formData.name,
      listen_port: parseInt(formData.listen_port.toString()),
      endpoint: formData.endpoint,
      public_key: formData.public_key,
      private_key: formData.private_key,
    };

    if (formData.description) submitData.description = formData.description;
    if (formData.ipv4_address) submitData.ipv4_address = formData.ipv4_address;
    if (formData.ipv6_address) submitData.ipv6_address = formData.ipv6_address;
    if (formData.dns_primary) submitData.dns_primary = formData.dns_primary;
    if (formData.dns_secondary)
      submitData.dns_secondary = formData.dns_secondary;
    if (formData.bounce_via_server_id) {
      submitData.bounce_via_server_id = parseInt(formData.bounce_via_server_id);
    }

    onImport(submitData);
  };

  const handleBack = () => {
    setStep("upload");
    setSelectedFile(null);
    setParsedData(null);
    setParseError(null);
  };

  // Available bounce servers
  const availableBounceServers = servers;

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
                  Import Server Configuration
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
                Upload a WireGuard server configuration file (.conf). You'll be
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
                      The file must be a valid WireGuard server configuration
                      with [Interface] section including PrivateKey, Address,
                      and ListenPort.
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
                  Review & Import Server
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
                      Server Name *
                    </label>
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="My VPN Server"
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="vpn.example.com or 1.2.3.4"
                    />
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      placeholder="10.0.0.1/24"
                    />
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Server IP address with subnet (e.g., 10.0.0.1/24)
                    </p>
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      placeholder="fd00::1/64"
                    />
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Server IPv6 address with subnet (e.g., fd00::1/64)
                    </p>
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
                      className="w-full px-3 py-2 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="1.1.1.1"
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
                      placeholder="8.8.8.8"
                    />
                  </div>
                </div>
              </div>

              {/* Advanced Options */}
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
                        bounce_via_server_id: value,
                      }))
                    }
                    options={[
                      { value: "", label: "None" },
                      ...availableBounceServers.map((s) => ({
                        value: s.id,
                        label: `${s.name} (${s.endpoint})`,
                      })),
                    ]}
                    placeholder="None"
                    disabled={isPending}
                  />
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Route this server's traffic through another WireGuard server
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
                  disabled={isPending}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-500 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                >
                  {isPending ? "Importing..." : "Import Server"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
