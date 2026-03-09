import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { setupAPI, authAPI } from '../../services/api';
import { useAuthStore } from '../../store/auth';
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

interface AccountStepProps {
  onNext: (data: any) => void;
  onBack: () => void;
}

export default function AccountStep({ onNext, onBack }: AccountStepProps) {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const login = useAuthStore((state) => state.login);

  const initializeMutation = useMutation({
    mutationFn: setupAPI.initialize,
    onSuccess: async (data) => {
      // Auto-login the user
      try {
        const loginResponse = await authAPI.login(formData.username, formData.password);
        // Update auth store with token
        login(loginResponse.access_token);
        // Pass username and password to setupData so GlobalSettingsStep can re-login after secret key change
        onNext({ 
          userId: data.user_id, 
          username: formData.username,
          password: formData.password  // Store temporarily for re-authentication
        });
      } catch (err) {
        console.error('[AccountStep] Auto-login failed:', err);
        setError('Account created but login failed. Please continue with setup.');
        onNext({ userId: data.user_id, username: data.username });
      }
    },
    onError: (err: any) => {
      if (isValidationError(err)) {
        const errors = parseValidationErrors(err);
        setFieldErrors(errors);
        setError(formatErrorCount(countErrors(errors)));
      } else {
        setError(getGenericError(err, 'Failed to create admin account'));
      }
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError(null);
    setFieldErrors({});
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    // Frontend validation
    if (formData.password.length < 6) {
      setFieldErrors({ password: ['Password must be at least 6 characters long'] });
      setError('1 validation error found');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: ['Passwords do not match'] });
      setError('1 validation error found');
      return;
    }

    initializeMutation.mutate({
      username: formData.username,
      email: formData.email,
      password: formData.password,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Create Admin Account</h2>
        <p className="text-gray-600 dark:text-gray-300">
          This account will have full access to manage your WireGuard infrastructure.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Username *
          </label>
          <input
            type="text"
            name="username"
            value={formData.username}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'username') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="admin"
          />
          <FieldError error={getFieldError(fieldErrors, 'username')} />
          {!getFieldError(fieldErrors, 'username') && (
            <p className="text-xs text-gray-500 mt-1">This will be used for login</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Email Address *
          </label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'email') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="admin@example.com"
          />
          <FieldError error={getFieldError(fieldErrors, 'email')} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Password *
          </label>
          <input
            type="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'password') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="••••••••"
          />
          <FieldError error={getFieldError(fieldErrors, 'password')} />
          {!getFieldError(fieldErrors, 'password') && (
            <p className="text-xs text-gray-500 mt-1">Minimum 6 characters</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Confirm Password *
          </label>
          <input
            type="password"
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleChange}
            required
            className={`w-full px-3 py-2 border ${getFieldError(fieldErrors, 'confirmPassword') ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
            placeholder="••••••••"
          />
          <FieldError error={getFieldError(fieldErrors, 'confirmPassword')} />
        </div>

        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-blue-600 dark:text-blue-400 mr-2 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-blue-800 dark:text-blue-400">
              <strong>Important:</strong> Save these credentials securely! You'll need them to access
              the system after setup is complete.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4">
          <button
            type="button"
            onClick={onBack}
            className="px-6 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Back
          </button>
          <button
            type="submit"
            disabled={initializeMutation.isPending}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            {initializeMutation.isPending ? 'Creating Account...' : 'Create Account & Continue'}
          </button>
        </div>
      </form>
    </div>
  );
}
