import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import type { Peer, Server } from '../types';
import type { FieldErrors } from '../utils/errorUtils';
import {
  parseValidationErrors,
  getFieldError,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from '../utils/errorUtils';
import FieldError from './FieldError';
import CustomSelect from './CustomSelect';
import { api } from '../services/api';

interface MigratePeerDialogProps {
  peer: Peer;
  currentServer: Server;
  availableServers: Server[];
  onMigrate: (peerId: number, migrationData: MigrationData, onSuccess?: () => void, onError?: (error: any) => void) => void;
  onClose: () => void;
  isPending?: boolean;
}

export interface MigrationData {
  target_server_id: number;
  ipv4_address?: string;
  ipv6_address?: string;
  dns_primary?: string;
  dns_secondary?: string;
  ipv4_allowed_ips?: string;
  ipv6_allowed_ips?: string;
  persistent_keepalive?: number;
}

interface MigrationPreview {
  suggested_ipv4_address: string | null;
  suggested_ipv6_address: string | null;
  suggested_dns_primary: string | null;
  suggested_dns_secondary: string | null;
  current_ipv4_address: string | null;
  current_ipv6_address: string | null;
  current_dns_primary: string | null;
  current_dns_secondary: string | null;
  current_ipv4_allowed_ips: string | null;
  current_ipv6_allowed_ips: string | null;
  current_persistent_keepalive: number;
}

export default function MigratePeerDialog({
  peer,
  currentServer,
  availableServers,
  onMigrate,
  onClose,
  isPending = false,
}: MigratePeerDialogProps) {
  const [targetServerId, setTargetServerId] = useState<number | null>(null);
  
  // Form state for editable configuration
  const [ipv4Address, setIpv4Address] = useState('');
  const [ipv6Address, setIpv6Address] = useState('');
  const [dnsPrimary, setDnsPrimary] = useState('');
  const [dnsSecondary, setDnsSecondary] = useState('');
  const [ipv4AllowedIps, setIpv4AllowedIps] = useState('');
  const [ipv6AllowedIps, setIpv6AllowedIps] = useState('');
  const [persistentKeepalive, setPersistentKeepalive] = useState(25);

  // Field-level validation errors
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  // Filter out the current server from available servers
  const otherServers = useMemo(
    () => availableServers.filter((s) => s.id !== currentServer.id),
    [availableServers, currentServer.id]
  );

  const targetServer = otherServers.find((s) => s.id === targetServerId);

  // Fetch migration preview when target server changes
  const { data: migrationPreview, isLoading: previewLoading } = useQuery<MigrationPreview>({
    queryKey: ['migration-preview', peer.id, targetServerId],
    queryFn: async () => {
      const response = await api.get(
        `/peers/${peer.id}/migration-preview?target_server_id=${targetServerId}`
      );
      return response.data;
    },
    enabled: !!targetServerId,
  });

  // Auto-populate form when preview loads
  useEffect(() => {
    if (migrationPreview) {
      setIpv4Address(migrationPreview.suggested_ipv4_address || '');
      setIpv6Address(migrationPreview.suggested_ipv6_address || '');
      setDnsPrimary(migrationPreview.suggested_dns_primary || '');
      setDnsSecondary(migrationPreview.suggested_dns_secondary || '');
      setIpv4AllowedIps(migrationPreview.current_ipv4_allowed_ips || '0.0.0.0/0');
      setIpv6AllowedIps(migrationPreview.current_ipv6_allowed_ips || '::/0');
      setPersistentKeepalive(migrationPreview.current_persistent_keepalive || 25);
      setFieldErrors({}); // Clear errors when loading new preview
    }
  }, [migrationPreview]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (targetServerId) {
      const migrationData: MigrationData = {
        target_server_id: targetServerId,
        ipv4_address: ipv4Address || undefined,
        ipv6_address: ipv6Address || undefined,
        dns_primary: dnsPrimary || undefined,
        dns_secondary: dnsSecondary || undefined,
        ipv4_allowed_ips: ipv4AllowedIps || undefined,
        ipv6_allowed_ips: ipv6AllowedIps || undefined,
        persistent_keepalive: persistentKeepalive,
      };
      
      // Call onMigrate with success and error callbacks
      onMigrate(
        peer.id,
        migrationData,
        () => {
          // Success callback
          setFieldErrors({}); // Clear errors on success
          toast.success("Peer migrated successfully");
          onClose();
        },
        (error: any) => {
          // Error callback
          if (isValidationError(error)) {
            const errors = parseValidationErrors(error);
            setFieldErrors(errors);
            const count = countErrors(errors);
            toast.error(formatErrorCount(count));
          } else {
            toast.error(getGenericError(error, "Failed to migrate peer"));
          }
        }
      );
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Migrate Peer</h2>
                <p className="text-gray-600 dark:text-gray-300 mt-1">
                  Move peer "{peer.name}" to a different server
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Current Status Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Current Configuration</h3>
              <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4 space-y-2 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Server:</span>
                  <span className="text-sm text-gray-900 dark:text-white font-medium">{currentServer.name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Interface:</span>
                  <span className="text-sm text-gray-900 dark:text-white">{currentServer.interface}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Endpoint:</span>
                  <span className="text-sm text-gray-900 dark:text-white">{currentServer.endpoint || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Peer IPv4:</span>
                  <span className="text-sm text-gray-900 dark:text-white">{peer.ipv4_address || 'N/A'}</span>
                </div>
                {peer.ipv6_address && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Peer IPv6:</span>
                    <span className="text-sm text-gray-900 dark:text-white">{peer.ipv6_address}</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Public Key:</span>
                  <span className="text-sm text-gray-900 dark:text-white font-mono">{peer.public_key.substring(0, 20)}...</span>
                </div>
              </div>
            </div>

            {/* Target Server Selection */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Target Server *
              </label>
              <CustomSelect
                value={targetServerId || ''}
                onChange={(value) => setTargetServerId(Number(value))}
                options={[
                  { value: '', label: 'Select target server...' },
                  ...otherServers.map((server) => ({
                    value: server.id,
                    label: `${server.name} (${server.interface || 'interface TBD'})`,
                  })),
                ]}
                placeholder="Select target server"
              />
              {otherServers.length === 0 && (
                <p className="text-sm text-amber-600 mt-2">
                  No other servers available. Create another server first.
                </p>
              )}
            </div>

            {/* Editable Configuration Form */}
            {targetServer && (
              <>
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    New Configuration (Editable)
                  </h3>
                  
                  {previewLoading ? (
                    <div className="text-center py-4 text-gray-600 dark:text-gray-400">Loading suggested configuration...</div>
                  ) : (
                    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800 space-y-4">
                      <p className="text-sm text-blue-800 dark:text-blue-200 mb-3">
                        <strong>Note:</strong> Public and private keys will remain unchanged. Customize the settings below:
                      </p>

                      {/* IPv4 Address */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          IPv4 Address
                        </label>
                        <input
                          type="text"
                          value={ipv4Address}
                          onChange={(e) => {
                            setIpv4Address(e.target.value);
                            setFieldErrors({}); // Clear errors when user types
                          }}
                          placeholder="e.g., 10.0.0.2/24"
                          className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                            getFieldError(fieldErrors, 'ipv4_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                          }`}
                        />
                        <FieldError error={getFieldError(fieldErrors, 'ipv4_address')} />
                      </div>

                      {/* IPv6 Address */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          IPv6 Address
                        </label>
                        <input
                          type="text"
                          value={ipv6Address}
                          onChange={(e) => {
                            setIpv6Address(e.target.value);
                            setFieldErrors({}); // Clear errors when user types
                          }}
                          placeholder="e.g., fd00::2/64"
                          className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                            getFieldError(fieldErrors, 'ipv6_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                          }`}
                        />
                        <FieldError error={getFieldError(fieldErrors, 'ipv6_address')} />
                      </div>

                      {/* DNS Settings */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Primary DNS
                          </label>
                          <input
                            type="text"
                            value={dnsPrimary}
                            onChange={(e) => {
                              setDnsPrimary(e.target.value);
                              setFieldErrors({}); // Clear errors when user types
                            }}
                            placeholder="e.g., 1.1.1.1"
                            className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                              getFieldError(fieldErrors, 'dns_primary') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                            }`}
                          />
                          <FieldError error={getFieldError(fieldErrors, 'dns_primary')} />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Secondary DNS
                          </label>
                          <input
                            type="text"
                            value={dnsSecondary}
                            onChange={(e) => {
                              setDnsSecondary(e.target.value);
                              setFieldErrors({}); // Clear errors when user types
                            }}
                            placeholder="e.g., 8.8.8.8"
                            className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                              getFieldError(fieldErrors, 'dns_secondary') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                            }`}
                          />
                          <FieldError error={getFieldError(fieldErrors, 'dns_secondary')} />
                        </div>
                      </div>

                      {/* Allowed IPs */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            IPv4 Allowed IPs
                          </label>
                          <input
                            type="text"
                            value={ipv4AllowedIps}
                            onChange={(e) => {
                              setIpv4AllowedIps(e.target.value);
                              setFieldErrors({}); // Clear errors when user types
                            }}
                            placeholder="e.g., 0.0.0.0/0"
                            className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                              getFieldError(fieldErrors, 'ipv4_allowed_ips') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                            }`}
                          />
                          <FieldError error={getFieldError(fieldErrors, 'ipv4_allowed_ips')} />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            IPv6 Allowed IPs
                          </label>
                          <input
                            type="text"
                            value={ipv6AllowedIps}
                            onChange={(e) => {
                              setIpv6AllowedIps(e.target.value);
                              setFieldErrors({}); // Clear errors when user types
                            }}
                            placeholder="e.g., ::/0"
                            className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 ${
                              getFieldError(fieldErrors, 'ipv6_allowed_ips') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                            }`}
                          />
                          <FieldError error={getFieldError(fieldErrors, 'ipv6_allowed_ips')} />
                        </div>
                      </div>

                      {/* Persistent Keepalive */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Persistent Keepalive (seconds)
                        </label>
                        <input
                          type="number"
                          value={persistentKeepalive}
                          onChange={(e) => {
                            setPersistentKeepalive(Number(e.target.value));
                            setFieldErrors({}); // Clear errors when user types
                          }}
                          min="0"
                          max="3600"
                          className={`w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white ${
                            getFieldError(fieldErrors, 'persistent_keepalive') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
                          }`}
                        />
                        <FieldError error={getFieldError(fieldErrors, 'persistent_keepalive')} />
                      </div>

                      {/* Target Server Info */}
                        <div className="mt-4 pt-4 border-t border-blue-300 dark:border-blue-700">
                          <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">Target Server Details</h4>
                          <div className="space-y-1">
                            <div className="flex justify-between text-sm">
                              <span className="text-blue-700 dark:text-blue-300">Server:</span>
                              <span className="text-blue-900 dark:text-blue-100 font-medium">{targetServer.name}</span>
                            </div>
                            <div className="flex justify-between text-sm">
                              <span className="text-blue-700 dark:text-blue-300">Endpoint:</span>
                              <span className="text-blue-900 dark:text-blue-100">{targetServer.endpoint || 'N/A'}</span>
                            </div>
                            <div className="flex justify-between text-sm">
                              <span className="text-blue-700 dark:text-blue-300">Listen Port:</span>
                              <span className="text-blue-900 dark:text-blue-100">{targetServer.listen_port}</span>
                            </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Warning Notice */}
                <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 mb-6">
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-200">Important</h4>
                      <p className="text-sm text-amber-800 dark:text-amber-300 mt-1">
                        After migration, clients using this peer will need to download a new configuration
                        file with the updated server endpoint and public key. The peer's keys will remain the same.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t border-gray-200 dark:border-gray-700">
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
              disabled={!targetServerId || isPending || otherServers.length === 0}
              className="px-6 py-2 bg-blue-600 dark:bg-blue-700 hover:bg-blue-700 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-500 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
            >
              {isPending ? 'Migrating...' : 'Migrate Peer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
