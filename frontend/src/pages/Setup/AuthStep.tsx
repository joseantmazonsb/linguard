import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { setupAPI, oidcAPI } from '../../services/apiClient';
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

interface AuthStepProps {
  onNext: (data: any) => void;
  onBack: () => void;
  setupData: any;
}

export default function AuthStep({ onNext, onBack }: AuthStepProps) {
  const [mode, setMode] = useState<'skip' | 'oidc'>('skip');
  const [authMode, setAuthMode] = useState('both');
  const [formData, setFormData] = useState({
    oidc_discovery_url: '',
    oidc_client_id: '',
    oidc_client_secret: '',
    oidc_scopes: 'openid email profile',
    oidc_auto_provision: true,
    oidc_admin_groups: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const configureAuthMutation = useMutation({
    mutationFn: setupAPI.configureAuth,
    onSuccess: () => {
      onNext({ auth: mode === 'skip' ? { skipped: true } : { ...formData, auth_mode: authMode, skipped: false } });
    },
    onError: (err: any) => {
      if (isValidationError(err)) {
        const errors = parseValidationErrors(err);
        setFieldErrors(errors);
        setError(formatErrorCount(countErrors(errors)));
      } else {
        setError(getGenericError(err, 'Failed to configure authentication'));
      }
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    const finalValue = type === 'checkbox' ? (e.target as HTMLInputElement).checked : value;
    setFormData((prev) => ({ ...prev, [name]: finalValue }));
    setFieldErrors({});
  };

  const handleTest = async () => {
    if (!formData.oidc_discovery_url || !formData.oidc_client_id) {
      setTestResult({
        success: false,
        message: 'Discovery URL and Client ID are required before testing.',
      });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await oidcAPI.test({
        discovery_url: formData.oidc_discovery_url,
        client_id: formData.oidc_client_id,
        client_secret: formData.oidc_client_secret,
        scopes: formData.oidc_scopes,
      });
      setTestResult({ success: result.success, message: result.message });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || 'Test failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    if (mode === 'skip') {
      configureAuthMutation.mutate({ skip: true });
      return;
    }

    if (!formData.oidc_discovery_url.trim() || !formData.oidc_client_id.trim()) {
      setFieldErrors({
        oidc_discovery_url: ['Discovery URL is required'],
        oidc_client_id: ['Client ID is required'],
      });
      setError('2 validation errors found');
      return;
    }

    configureAuthMutation.mutate({
      skip: false,
      auth_mode: authMode,
      ...formData,
    });
  };

  return (
    <div>
      <div className="mb-6">
        <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/50 rounded-lg flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-blue-600 dark:text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Authentication</h2>
        <p className="text-gray-600 dark:text-gray-300">
          Configure how users sign in to Linguard. You can enable Single Sign-On now via any
          OpenID Connect provider (Authentik, Keycloak, etc.), or continue with local
          authentication and set it up later in Settings.
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          {/* Mode selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setMode('skip')}
              className={`p-4 rounded-lg border-2 text-left transition-colors ${
                mode === 'skip'
                  ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'
              }`}
            >
              <p className="font-medium text-gray-900 dark:text-white">Local authentication only</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Use the admin account created earlier. You can configure SSO later in Settings.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setMode('oidc')}
              className={`p-4 rounded-lg border-2 text-left transition-colors ${
                mode === 'oidc'
                  ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'
              }`}
            >
              <p className="font-medium text-gray-900 dark:text-white">Set up Single Sign-On (OIDC)</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Connect an OpenID Connect identity provider now.
              </p>
            </button>
          </div>

          {mode === 'oidc' && (
            <>
              {/* Auth mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Authentication Mode
                </label>
                <select
                  name="auth_mode_select"
                  value={authMode}
                  onChange={(e) => setAuthMode(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="both">Local + OIDC (both)</option>
                  <option value="local_only">Local Authentication Only</option>
                  <option value="oidc_only">OIDC Only</option>
                </select>
              </div>

              {/* Discovery URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Discovery URL *
                </label>
                <input
                  type="text"
                  name="oidc_discovery_url"
                  value={formData.oidc_discovery_url}
                  onChange={handleChange}
                  className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'oidc_discovery_url') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                  placeholder="https://idp.example.com/application/o/linguard/.well-known/openid-configuration"
                />
                <FieldError error={getFieldError(fieldErrors, 'oidc_discovery_url')} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client ID *</label>
                  <input
                    type="text"
                    name="oidc_client_id"
                    value={formData.oidc_client_id}
                    onChange={handleChange}
                    className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'oidc_client_id') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                  />
                  <FieldError error={getFieldError(fieldErrors, 'oidc_client_id')} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client Secret</label>
                  <input
                    type="password"
                    name="oidc_client_secret"
                    value={formData.oidc_client_secret}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Scopes</label>
                <input
                  type="text"
                  name="oidc_scopes"
                  value={formData.oidc_scopes}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  name="oidc_auto_provision"
                  checked={formData.oidc_auto_provision}
                  onChange={handleChange}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label className="text-sm text-gray-700 dark:text-gray-300">
                  Automatically create users on first sign-in
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Admin Groups</label>
                <input
                  type="text"
                  name="oidc_admin_groups"
                  value={formData.oidc_admin_groups}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="linguard-admins"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Comma-separated. Users in any of these identity provider groups get administrator privileges.
                </p>
              </div>

              {/* Test connection */}
              <div>
                <button
                  type="button"
                  onClick={handleTest}
                  disabled={testing}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-lg flex items-center gap-2 transition-colors text-sm font-medium"
                >
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
                {testResult && (
                  <div
                    className={`mt-2 text-sm px-3 py-2 rounded-lg border ${
                      testResult.success
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                        : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                    }`}
                  >
                    {testResult.message}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <div className="flex items-center justify-between pt-4 mt-4">
          <button type="button" onClick={onBack} className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50">
            Back
          </button>
          <button
            type="submit"
            disabled={configureAuthMutation.isPending}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium"
          >
            {configureAuthMutation.isPending
              ? 'Saving...'
              : mode === 'skip'
                ? 'Continue with Local Auth'
                : 'Save & Continue'}
          </button>
        </div>
      </form>
    </div>
  );
}
