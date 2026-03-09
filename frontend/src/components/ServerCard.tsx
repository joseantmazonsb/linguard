import type { Server } from '../types';

interface ServerCardProps {
  server: Server;
  onEdit: (server: Server) => void;
  onDelete: (id: number, name: string) => void | Promise<void>;
  onStart: (id: number) => void;
  onStop: (id: number) => void;
  onReload: (id: number) => void;
  onDownloadConfig: (id: number, name: string) => void;
  onShowMetrics: (id: number, name: string) => void;
  isStarting: boolean;
  isStopping: boolean;
  isReloading: boolean;
  isSelectable?: boolean;
  isSelected?: boolean;
  onToggleSelect?: () => void;
}

export default function ServerCard({
  server,
  onEdit,
  onDelete,
  onStart,
  onStop,
  onReload,
  onDownloadConfig,
  onShowMetrics,
  isStarting,
  isStopping,
  isReloading,
  isSelectable = false,
  isSelected = false,
  onToggleSelect,
}: ServerCardProps) {
  return (
    <div 
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow flex flex-col h-full relative ${
        isSelectable ? 'cursor-pointer' : ''
      } ${
        isSelected ? 'ring-2 ring-blue-500 dark:ring-blue-400' : ''
      }`}
      onClick={isSelectable ? onToggleSelect : undefined}
    >
      {/* Selection Overlay */}
      {isSelectable && (
        <div className="absolute top-4 right-4 z-10" onClick={(e) => e.stopPropagation()}>
          <div 
            className={`w-6 h-6 rounded border-2 flex items-center justify-center transition-colors ${
              isSelected 
                ? 'bg-blue-500 dark:bg-blue-600 border-blue-500 dark:border-blue-600' 
                : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
            }`}
            onClick={onToggleSelect}
          >
            {isSelected && (
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            {/* Badges above server name */}
            <div className="flex items-center gap-2 mb-2">
              {/* Status indicator dot */}
              <div
                className={`w-2 h-2 rounded-full ${
                  server.status === 'running' && server.needs_reload
                    ? "bg-orange-500" 
                    : server.status === 'running' 
                      ? "bg-green-500" 
                      : "bg-gray-400"
                }`}
              />
              {server.autostart && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                  </svg>
                  Autostart
                </span>
              )}
              {server.status === 'running' && server.needs_reload && (
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-orange-100 dark:bg-orange-900/50 text-orange-800 dark:text-orange-300">
                  Needs Reload
                </span>
              )}
            </div>
            
            {/* Server name */}
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-1">{server.name}</h3>
            
            {server.description && (
              <p className="text-sm text-gray-600 dark:text-gray-400">{server.description}</p>
            )}
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="p-6 space-y-3 flex-1">
        {server.status === 'running' && server.interface && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">Interface:</span>
            <span className="font-medium text-gray-900 dark:text-white">{server.interface}</span>
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Endpoint:</span>
          <span className="font-medium text-gray-900 dark:text-white">{server.endpoint}:{server.listen_port}</span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Peers:</span>
          <span className="font-medium text-gray-900 dark:text-white">{server.peer_count ?? 0}</span>
        </div>

        {server.ipv4_address && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">IPv4:</span>
            <span className="font-medium text-gray-900 dark:text-white">{server.ipv4_address}</span>
          </div>
        )}

        {server.ipv6_address && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">IPv6:</span>
            <span className="font-mono text-xs text-gray-900 dark:text-white">{server.ipv6_address}</span>
          </div>
        )}

        {(server.dns_primary || server.dns_secondary) && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">DNS:</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {[server.dns_primary, server.dns_secondary].filter(Boolean).join(', ')}
            </span>
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Public Key:</span>
          <span className="font-mono text-xs text-gray-900 dark:text-white truncate" title={server.public_key}>
            {server.public_key.substring(0, 20)}...
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 mt-auto">
        <div className="p-3 flex items-center gap-1.5 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600">{!isSelectable && (
          <>
            {server.status === 'running' ? (
              <>
                <button
                  onClick={() => onReload(server.id)}
                  disabled={isReloading}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 flex-shrink-0 ${
                    server.needs_reload 
                      ? 'bg-orange-600 hover:bg-orange-700 dark:bg-orange-700 dark:hover:bg-orange-600'
                      : 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600'
                  } disabled:opacity-50 text-white rounded text-sm font-medium transition-colors whitespace-nowrap`}
                  title="Reload server configuration"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {isReloading ? 'Reloading...' : 'Reload'}
                </button>
                <button
                  onClick={() => onStop(server.id)}
                  disabled={isStopping}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 flex-shrink-0 bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors whitespace-nowrap"
                  title="Stop server"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                  </svg>
                  {isStopping ? 'Stopping...' : 'Stop'}
                </button>
              </>
            ) : (
              <button
                onClick={() => onStart(server.id)}
                disabled={isStarting}
                className="flex items-center gap-1.5 px-2.5 py-1.5 flex-shrink-0 bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors whitespace-nowrap"
                title="Start server"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {isStarting ? 'Starting...' : 'Start'}
              </button>
            )}

            <button
              onClick={() => onEdit(server)}
              className="p-2 flex-shrink-0 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
              title="Edit"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>

            <button
              onClick={() => onDownloadConfig(server.id, server.name)}
              className="p-2 flex-shrink-0 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors"
              title="Download Config"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>

            <button
              onClick={() => onShowMetrics(server.id, server.name)}
              className="p-2 flex-shrink-0 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-50 dark:hover:bg-cyan-900/30 rounded transition-colors"
              title="View Traffic Metrics"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </button>

            <button
              onClick={() => onDelete(server.id, server.name)}
              className="p-2 flex-shrink-0 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
              title="Delete"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </>
        )}
        {isSelectable && (
          <div className="flex-1 text-center text-sm text-gray-500 dark:text-gray-400">
            Click to {isSelected ? 'deselect' : 'select'}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
