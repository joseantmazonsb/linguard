import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { oidcAPI } from '../services/apiClient';
import { useAuthStore } from '../store/auth';

export default function AuthCallback() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oidcError = searchParams.get('error');

    if (oidcError) {
      setError(
        searchParams.get('error_description') ||
          'The identity provider refused the login attempt.'
      );
      return;
    }

    if (!code || !state) {
      setError('Missing authorization code or state parameter.');
      return;
    }

    oidcAPI
      .callback(code, state)
      .then((response) => {
        login(response.access_token, response.user?.role);
        navigate('/dashboard', { replace: true });
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Single Sign-On failed. Please try again.');
      });
  }, [searchParams, login, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-lg text-center">
        {error ? (
          <>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Sign-in failed</h2>
            <p className="text-sm text-gray-600 mb-6">{error}</p>
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <svg
              className="w-10 h-10 mx-auto text-blue-600 animate-spin"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            <p className="mt-4 text-sm text-gray-600">Completing sign-in...</p>
          </>
        )}
      </div>
    </div>
  );
}
