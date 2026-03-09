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

function WireguardMissingBanner({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">WireGuard Not Found</h2>
        <p className="text-gray-600 dark:text-gray-300">The peer could not be created because WireGuard is not installed.</p>
      </div>

      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <div>
            <p className="font-medium text-yellow-800 dark:text-yellow-300">WireGuard is not installed</p>
            <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">
              You can still complete setup and access the dashboard. The system status will show as unhealthy until WireGuard is installed and servers and peers are configured.
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
          onClick={onNext}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg font-medium"
        >
          Continue Anyway
        </button>
      </div>
    </div>
  );
}

export default function PeerStep({ onNext, onBack, setupData }: PeerStepProps) {
  const [formData, setFormData] = useState({
    name: 'My Laptop',
    preshared_key: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [wireguardMissing, setWireguardMissing] = useState(false);

  const createPeerMutation = useMutation({
    mutationFn: setupAPI.createPeer,
    onSuccess: (data) => {
      if (data.wireguard_missing) {
        setWireguardMissing(true);
        return;
      }
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

  // If WireGuard was already missing at the server step, skip straight to the warning view
  if (setupData.wireguardMissing || wireguardMissing) {
    return (
      <WireguardMissingBanner
        onNext={() => onNext({ wireguardMissing: true })}
        onBack={onBack}
      />
    );
  }

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

