import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { setupAPI } from '../../services/api';
import ToggleSwitch from '../../components/ToggleSwitch';
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

interface PeerStepProps {
  onNext: (data: any) => void;
  onBack: () => void;
  setupData: any;
}

export default function PeerStep({ onNext, onBack, setupData }: PeerStepProps) {
  const [formData, setFormData] = useState({
    name: 'My Laptop',
    preshared_key: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const createPeerMutation = useMutation({
    mutationFn: setupAPI.createPeer,
    onSuccess: (data) => {
      onNext({ peerId: data.peer_id, peerName: data.peer_name });
    },
    onError: (err: any) => {
      if (isValidationError(err)) {
        const errors = parseValidationErrors(err);
        setFieldErrors(errors);
        setError(formatErrorCount(countErrors(errors)));
      } else {
        setError(getGenericError(err, 'Failed to create peer'));
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createPeerMutation.mutate({
      server_id: setupData.serverId,
      name: formData.name,
      preshared_key: formData.preshared_key,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Create First Peer</h2>
        <p className="text-gray-600 dark:text-gray-300">Create your first VPN client configuration.</p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Peer Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={(e) => {
              setFormData({ ...formData, name: e.target.value });
              setError(null);
              setFieldErrors({});
            }}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'name') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="My Laptop"
          />
          <FieldError error={getFieldError(fieldErrors, 'name')} />
          {!getFieldError(fieldErrors, 'name') && (
            <p className="text-xs text-gray-500 mt-1">Descriptive name for this device</p>
          )}
        </div>

        <div className="bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
          <ToggleSwitch
            checked={formData.preshared_key}
            onChange={(checked) => setFormData({ ...formData, preshared_key: checked })}
            label="Enable Preshared Key (PSK)"
          />
          <p className="text-xs text-gray-600 dark:text-gray-300 mt-1 ml-6">
            Provides additional post-quantum cryptographic security
          </p>
        </div>

        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="text-sm text-blue-800 dark:text-blue-400">
            IP addresses will be automatically assigned from your configured IP pools.
          </p>
        </div>

        <div className="flex items-center justify-between pt-4">
          <button type="button" onClick={onBack} className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50">
            Back
          </button>
          <button type="submit" disabled={createPeerMutation.isPending} className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium">
            {createPeerMutation.isPending ? 'Creating...' : 'Create Peer'}
          </button>
        </div>
      </form>
    </div>
  );
}
