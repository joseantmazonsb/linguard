import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useInfiniteQuery } from "@tanstack/react-query";
import { auditAPI } from "../services/api";
import CustomSelect from "../components/CustomSelect";

interface AuditLog {
  id: number;
  user_id: number;
  username: string;
  action: string;
  resource_type: string;
  resource_id?: number;
  resource_name?: string;
  details?: any;
  ip_address?: string;
  user_agent?: string;
  status: string;
  error_message?: string;
  created_at: string;
}

export default function AuditLog() {
  const [filters, setFilters] = useState({
    action: "",
    resource_type: "",
    search: "",
  });
  const [searchInput, setSearchInput] = useState("");
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const observerTarget = useRef<HTMLDivElement>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: searchInput }));
    }, 500); // Wait 500ms after user stops typing

    return () => clearTimeout(timer);
  }, [searchInput]);

  // Fetch audit logs with infinite scroll
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["audit-logs", filters],
    queryFn: ({ pageParam = 0 }) =>
      auditAPI.list({ ...filters, skip: pageParam, limit: 50 }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const currentCount = allPages.reduce((acc, page) => acc + page.length, 0);
      return lastPage.length === 50 ? currentCount : undefined;
    },
  });

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 },
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Flatten all pages into a single array
  const logs = data?.pages.flat() || [];

  // Fetch statistics
  const { data: stats } = useQuery({
    queryKey: ["audit-stats"],
    queryFn: auditAPI.getStats,
  });

  const handleFilterChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value, skip: 0 }));
  };

  const handleSelectChange = (name: string, value: string | number) => {
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleClearFilters = () => {
    setFilters({
      action: "",
      resource_type: "",
      search: "",
    });
    setSearchInput("");
  };

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case "CREATE":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
      case "UPDATE":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
      case "DELETE":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
      case "START":
      case "STOP":
      case "RELOAD":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
      case "MIGRATE":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200";
    }
  };

  const getStatusBadgeColor = (status: string) => {
    return status === "success"
      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return "Invalid Date";
      return date.toLocaleString();
    } catch (error) {
      return "Invalid Date";
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500 dark:text-gray-400">
            Loading event logs...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded">
          Error loading audit logs: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Event Logs
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          View system activity and administrative actions
        </p>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Total Actions
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.total_actions || 0}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Creates
            </div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.actions_by_type?.CREATE || 0}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Updates
            </div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {stats.actions_by_type?.UPDATE || 0}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Deletes
            </div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.actions_by_type?.DELETE || 0}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:border dark:border-gray-700 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Action
            </label>
            <CustomSelect
              value={filters.action}
              onChange={(value) => handleSelectChange("action", value)}
              options={[
                { value: "", label: "All Actions" },
                { value: "CREATE", label: "Create" },
                { value: "UPDATE", label: "Update" },
                { value: "DELETE", label: "Delete" },
                { value: "START", label: "Start" },
                { value: "STOP", label: "Stop" },
                { value: "RELOAD", label: "Reload" },
                { value: "MIGRATE", label: "Migrate" },
              ]}
              placeholder="All Actions"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Resource Type
            </label>
            <CustomSelect
              value={filters.resource_type}
              onChange={(value) => handleSelectChange("resource_type", value)}
              options={[
                { value: "", label: "All Types" },
                { value: "server", label: "Server" },
                { value: "peer", label: "Peer" },
                { value: "settings", label: "Settings" },
                { value: "backup", label: "Backup" },
              ]}
              placeholder="All Types"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Search
            </label>
            <input
              type="text"
              name="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search logs..."
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-300 dark:placeholder-gray-400"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={handleClearFilters}
              className="w-full px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:border dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Resource
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  IP Address
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {logs && logs.length > 0 ? (
                logs.map((log: AuditLog) => (
                  <tr
                    key={log.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-300">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-300">
                      {log.username}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full ${getActionBadgeColor(log.action)}`}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="text-gray-900 dark:text-gray-300">
                        {log.resource_type}
                      </div>
                      {log.resource_name && (
                        <div className="text-gray-500 dark:text-gray-400 text-xs">
                          {log.resource_name}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeColor(log.status)}`}
                      >
                        {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {log.ip_address || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-12 text-center text-gray-500 dark:text-gray-400"
                  >
                    No audit logs found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Infinite scroll trigger */}
        <div ref={observerTarget} className="h-4" />

        {/* Loading indicator */}
        {isFetchingNextPage && (
          <div className="py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
            Loading more logs...
          </div>
        )}
      </div>

      {/* Details Modal */}
      {selectedLog && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedLog(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl dark:border dark:border-gray-700 max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  Audit Log Details
                </h2>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
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

              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Timestamp
                  </label>
                  <div className="text-gray-900 dark:text-gray-300">
                    {formatDate(selectedLog.created_at)}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    User
                  </label>
                  <div className="text-gray-900 dark:text-gray-300">
                    {selectedLog.username} (ID: {selectedLog.user_id})
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Action
                  </label>
                  <div>
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded-full ${getActionBadgeColor(selectedLog.action)}`}
                    >
                      {selectedLog.action}
                    </span>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Resource
                  </label>
                  <div className="text-gray-900 dark:text-gray-300">
                    {selectedLog.resource_type}{" "}
                    {selectedLog.resource_id &&
                      `(ID: ${selectedLog.resource_id})`}
                    {selectedLog.resource_name &&
                      ` - ${selectedLog.resource_name}`}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </label>
                  <div>
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeColor(selectedLog.status)}`}
                    >
                      {selectedLog.status}
                    </span>
                  </div>
                </div>

                {selectedLog.error_message && (
                  <div>
                    <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Error Message
                    </label>
                    <div className="text-red-600 dark:text-red-400">
                      {selectedLog.error_message}
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    IP Address
                  </label>
                  <div className="text-gray-900 dark:text-gray-300">
                    {selectedLog.ip_address || "N/A"}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    User Agent
                  </label>
                  <div className="text-gray-900 dark:text-gray-300 text-sm break-all">
                    {selectedLog.user_agent || "N/A"}
                  </div>
                </div>

                {selectedLog.details && (
                  <div>
                    <label className="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Details
                    </label>
                    <pre className="mt-1 p-3 bg-gray-50 dark:bg-gray-900 dark:border dark:border-gray-700 rounded-lg text-xs overflow-x-auto dark:text-gray-300">
                      {JSON.stringify(selectedLog.details, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setSelectedLog(null)}
                  className="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-300 rounded-lg transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
