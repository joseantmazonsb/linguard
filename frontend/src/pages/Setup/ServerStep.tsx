import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { setupAPI } from '../../services/api';
import type { FieldErrors } from '../../utils/errorUtils';
import {
  parseValidationErrors,
  getFieldError,
  isValidationError,
  countErrors,
  formatErrorCount,
  getGenericError,
} from '../../utils/errorUtils';
import FieldError from '../../components/FieldError';

interface ServerStepProps {
  onNext: (data: any) => void;
  onBack: () => void;
  setupData: any;
}

export default function ServerStep({ onNext, onBack, setupData }: ServerStepProps) {
  const [formData, setFormData] = useState({
    name: 'Main VPN Server',
    endpoint: '',
    listen_port: 51820,
    ipv4_address: '10.0.1.1/24',
    ipv6_address: 'fd00::1/64',
    dns: setupData.dns_primary || '8.8.8.8',
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [wireguardMissing, setWireguardMissing] = useState(false);

  const createServerMutation = useMutation({
    mutationFn: setupAPI.createServer,
    onSuccess: (data) => {
      if (data.wireguard_missing) {
        // WireGuard is not installed — show warning and let user continue
        setWireguardMissing(true);
        return;
      }
      onNext({ serverId: data.server_id, serverName: data.server_name });
    },
    onError: (err: any) => {
      if (isValidationError(err)) {
        const errors = parseValidationErrors(err);
        setFieldErrors(errors);
        setError(formatErrorCount(countErrors(errors)));
      } else {
        setError(getGenericError(err, 'Failed to create server'));
      }
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.type === 'number' ? parseInt(e.target.value) : e.target.value;
    setFormData({ ...formData, [e.target.name]: value });
    setError(null);
    setFieldErrors({});
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createServerMutation.mutate(formData);
  };

  if (wireguardMissing) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">WireGuard Not Found</h2>
          <p className="text-gray-600 dark:text-gray-300">The server could not be created because WireGuard is not installed.</p>
        </div>

        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="font-medium text-yellow-800 dark:text-yellow-300">WireGuard is not installed</p>
              <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">
                You can still complete setup and access the dashboard. The system status will show as unhealthy until WireGuard is installed and servers are configured.
              </p>
              <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-2">
                To install WireGuard, run: <code className="bg-yellow-100 dark:bg-yellow-900/40 px-1 rounded font-mono">apt install wireguard</code> (Debian/Ubuntu) or equivalent for your OS.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4">
          <button type="button" onClick={onBack} className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50">
            Back
          </button>
          <button
            type="button"
            onClick={() => onNext({ wireguardMissing: true })}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg font-medium"
          >
            Continue Anyway
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Create First Server</h2>
        <p className="text-gray-600 dark:text-gray-300">Configure your first WireGuard VPN server.</p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Server Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'name') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
          />
          <FieldError error={getFieldError(fieldErrors, 'name')} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Endpoint (Public IP or Domain) *</label>
          <input
            type="text"
            name="endpoint"
            value={formData.endpoint}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'endpoint') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="vpn.example.com or 203.0.113.1"
          />
          <FieldError error={getFieldError(fieldErrors, 'endpoint')} />
          {!getFieldError(fieldErrors, 'endpoint') && (
            <p className="text-xs text-gray-500 mt-1">Clients will connect to this address</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Listen Port *</label>
            <input
              type="number"
              name="listen_port"
              value={formData.listen_port}
              onChange={handleChange}
              required
              className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'listen_port') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            />
            <FieldError error={getFieldError(fieldErrors, 'listen_port')} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">DNS Server</label>
            <input
              type="text"
              name="dns"
              value={formData.dns}
              onChange={handleChange}
              className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'dns') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            />
            <FieldError error={getFieldError(fieldErrors, 'dns')} />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">IPv4 Address (CIDR) *</label>
            <input
              type="text"
              name="ipv4_address"
              value={formData.ipv4_address}
              onChange={handleChange}
              required
              className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv4_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            />
            <FieldError error={getFieldError(fieldErrors, 'ipv4_address')} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">IPv6 Address (CIDR)</label>
            <input
              type="text"
              name="ipv6_address"
              value={formData.ipv6_address}
              onChange={handleChange}
              className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'ipv6_address') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            />
            <FieldError error={getFieldError(fieldErrors, 'ipv6_address')} />
          </div>
        </div>

        <div className="flex items-center justify-between pt-4">
          <button type="button" onClick={onBack} className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50">
            Back
          </button>
          <button type="submit" disabled={createServerMutation.isPending} className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium">
            {createServerMutation.isPending ? 'Creating...' : 'Create Server'}
          </button>
        </div>
      </form>
    </div>
  );
}

