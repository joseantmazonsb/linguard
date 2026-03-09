import { useEffect } from "react";

interface WireGuardTestResult {
  success: boolean;
  error: string | null;
  output: string;
  binary_path: string;
}

interface AutodetectResult {
  found: boolean;
  paths: Array<{
    path: string;
    version: string;
  }>;
  searched_locations: string[];
}

interface WireGuardTestDialogProps {
  isOpen: boolean;
  result: WireGuardTestResult | null;
  isLoading: boolean;
  onClose: () => void;
  onAutodetect?: () => void;
  autodetectResult?: AutodetectResult | null;
  isAutodetecting?: boolean;
  onSelectPath?: (path: string) => void;
  isEditing?: boolean;
}

export default function WireGuardTestDialog({
  isOpen,
  result,
  isLoading,
  onClose,
  onAutodetect,
  autodetectResult,
  isAutodetecting = false,
  onSelectPath,
  isEditing = false,
}: WireGuardTestDialogProps) {
  // Handle Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl dark:shadow-gray-900/50 max-w-2xl w-full border dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
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
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            WireGuard Binary Test
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
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

        {/* Content */}
        <div className="p-6">
          {isLoading || isAutodetecting ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                <p className="text-gray-600 dark:text-gray-400">
                  {isAutodetecting ? "Auto-detecting WireGuard binary..." : "Testing WireGuard binary..."}
                </p>
              </div>
            </div>
          ) : autodetectResult ? (
            <div className="space-y-4">
              {/* Autodetect Results */}
              <div className="flex items-center gap-3">
                {autodetectResult.found ? (
                  <>
                    <div className="flex-shrink-0 w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-green-600 dark:text-green-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-green-700 dark:text-green-400">
                        WireGuard Found
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Found {autodetectResult.paths.length} installation{autodetectResult.paths.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex-shrink-0 w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-yellow-600 dark:text-yellow-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-yellow-700 dark:text-yellow-400">
                        Not Found
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        WireGuard binary not found in common locations
                      </p>
                    </div>
                  </>
                )}
              </div>

              {/* Found Paths */}
              {autodetectResult.found && autodetectResult.paths.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Detected Installations
                  </label>
                  <div className="space-y-2">
                    {autodetectResult.paths.map((pathInfo, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-blue-500 dark:hover:border-blue-400 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-mono text-gray-900 dark:text-gray-100 truncate">
                            {pathInfo.path}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {pathInfo.version}
                          </p>
                        </div>
                        {onSelectPath && (
                          <button
                            onClick={() => onSelectPath(pathInfo.path)}
                            className="ml-3 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white text-sm rounded-lg transition-colors whitespace-nowrap"
                          >
                            Use This
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Searched Locations */}
              {!autodetectResult.found && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Searched Locations
                  </label>
                  <div className="px-3 py-2 bg-gray-900 dark:bg-gray-950 rounded-lg border border-gray-700 dark:border-gray-600 max-h-48 overflow-auto">
                    <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap">
                      {autodetectResult.searched_locations.join('\n')}
                    </pre>
                  </div>
                  <div className="mt-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
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
                        <p className="text-sm text-blue-800 dark:text-blue-300">
                          <strong>Install WireGuard:</strong>
                        </p>
                        <p className="text-xs text-blue-700 dark:text-blue-400 mt-1">
                          • Ubuntu/Debian: <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">sudo apt install wireguard-tools</code>
                        </p>
                        <p className="text-xs text-blue-700 dark:text-blue-400">
                          • macOS: <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">brew install wireguard-tools</code>
                        </p>
                        <p className="text-xs text-blue-700 dark:text-blue-400">
                          • CentOS/RHEL: <code className="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">sudo yum install wireguard-tools</code>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : result ? (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex items-center gap-3">
                {result.success ? (
                  <>
                    <div className="flex-shrink-0 w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-green-600 dark:text-green-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-green-700 dark:text-green-400">
                        Test Successful
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        WireGuard binary is working correctly
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex-shrink-0 w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-red-600 dark:text-red-400"
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
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-red-700 dark:text-red-400">
                        Test Failed
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        There was an issue with the WireGuard binary
                      </p>
                    </div>
                  </>
                )}
              </div>

              {/* Binary Path */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Binary Path
                </label>
                <div className="px-3 py-2 bg-gray-100 dark:bg-gray-700/50 rounded-lg text-gray-900 dark:text-gray-300 font-mono text-sm border border-gray-300 dark:border-gray-600">
                  {result.binary_path}
                </div>
              </div>

              {/* Error Message (if failed) */}
              {result.error && (
                <div>
                  <label className="block text-sm font-medium text-red-700 dark:text-red-400 mb-1">
                    Error
                  </label>
                  <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-red-700 dark:text-red-300 text-sm border border-red-200 dark:border-red-800">
                    {result.error}
                  </div>
                </div>
              )}

              {/* Command Output */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Command Output (wg show)
                </label>
                <div className="px-3 py-2 bg-gray-900 dark:bg-gray-950 rounded-lg border border-gray-700 dark:border-gray-600 max-h-64 overflow-auto">
                  <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap">
                    {result.output || "(empty)"}
                  </pre>
                </div>
              </div>

              {/* Info Message */}
              {result.success && !result.output && (
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
                    <p className="text-sm text-blue-800 dark:text-blue-300">
                      The WireGuard binary is functional. No interfaces are
                      currently configured, which is normal for a fresh
                      installation or when all interfaces are down.
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-between rounded-b-lg border-t border-gray-200 dark:border-gray-700">
          <div>
            {!autodetectResult && (
              <button
                onClick={onAutodetect}
                disabled={isAutodetecting || !isEditing}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-600 disabled:bg-purple-400 dark:disabled:bg-purple-800 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                title={!isEditing ? "Enable editing mode to use autodetect" : "Auto-detect WireGuard binary"}
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
                {isAutodetecting ? "Detecting..." : "Autodetect"}
              </button>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
