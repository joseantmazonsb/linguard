import type { Peer } from '../types';

interface PeerCardProps {
  peer: Peer;
  serverName: string;
  onEdit: (peer: Peer) => void;
  onDelete: (id: number, name: string) => void;
  onMigrate: (peer: Peer) => void;
  onShowQRCode: (id: number, name: string) => void;
  onDownloadConfig: (id: number, name: string) => void;
  onShowMetrics: (id: number, name: string) => void;
  onToggleEnabled: (id: number, enabled: boolean) => void;
  isSelectable?: boolean;
  isSelected?: boolean;
  onToggleSelect?: () => void;
}

export default function PeerCard({
  peer,
  serverName,
  onEdit,
  onDelete,
  onMigrate,
  onShowQRCode,
  onDownloadConfig,
  onShowMetrics,
  onToggleEnabled,
  isSelectable = false,
  isSelected = false,
  onToggleSelect,
}: PeerCardProps) {
  return (
    <div 
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200 dark:border-gray-700 relative ${
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
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white">{peer.name}</h3>
            </div>
            {peer.description && (
              <p className="text-sm text-gray-600 dark:text-gray-300">{peer.description}</p>
            )}
          </div>
          {/* Toggle Switch - Hidden during bulk selection */}
          {!isSelectable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleEnabled(peer.id, !peer.enabled);
              }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 ${
                peer.enabled
                  ? "bg-green-600"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
              title={peer.enabled ? "Disable peer" : "Enable peer"}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  peer.enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="p-6 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Server:</span>
          <span className="font-medium text-gray-900 dark:text-white">{serverName}</span>
        </div>

        {peer.ipv4_address && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">IPv4:</span>
            <span className="font-medium text-gray-900 dark:text-white">{peer.ipv4_address}</span>
          </div>
        )}

        {peer.ipv6_address && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">IPv6:</span>
            <span className="font-mono text-xs text-gray-900 dark:text-white">{peer.ipv6_address}</span>
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Public Key:</span>
          <span className="font-mono text-xs text-gray-900 dark:text-white truncate" title={peer.public_key}>
            {peer.public_key.substring(0, 20)}...
          </span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Allowed IPs:</span>
          <span className="font-medium text-gray-900 dark:text-white text-xs">{peer.allowed_ips}</span>
        </div>

        {(peer.dns_primary || peer.dns_secondary) && (
          <div className="flex items-center gap-2 text-sm">
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
            <span className="text-gray-600 dark:text-gray-400">DNS:</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {[peer.dns_primary, peer.dns_secondary].filter(Boolean).join(', ')}
            </span>
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-gray-600 dark:text-gray-400">Keepalive:</span>
          <span className="font-medium text-gray-900 dark:text-white">{peer.persistent_keepalive}s</span>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex items-center gap-2">
        {!isSelectable && (
          <>
            <button
              onClick={() => onShowQRCode(peer.id, peer.name)}
              className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors"
              title="Show QR Code"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
              </svg>
            </button>

            <button
              onClick={() => onMigrate(peer)}
              className="p-2 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-50 dark:hover:bg-yellow-900/30 rounded transition-colors"
              title="Migrate to another server"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </button>

            <button
              onClick={() => onEdit(peer)}
              className="p-2 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
              title="Edit"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>

            <button
              onClick={() => onDownloadConfig(peer.id, peer.name)}
              className="p-2 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded transition-colors"
              title="Download Config"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>

            <button
              onClick={() => onShowMetrics(peer.id, peer.name)}
              className="p-2 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-50 dark:hover:bg-cyan-900/30 rounded transition-colors"
              title="View Traffic Metrics"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </button>

            <button
              onClick={() => onDelete(peer.id, peer.name)}
              className="p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
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
  );
}
