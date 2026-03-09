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

  const createServerMutation = useMutation({
    mutationFn: setupAPI.createServer,
    onSuccess: (data) => {
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
