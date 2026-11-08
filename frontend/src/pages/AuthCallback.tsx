import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { api, oidcAPI } from '../services/apiClient';
import { useAuthStore } from '../store/auth';
import { tokenFingerprint } from '../utils/oidcLink';

export default function AuthCallback() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<{ code: string; state: string; fingerprint: string } | null>(null);
  const [isLinkFlow, setIsLinkFlow] = useState(false);
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const codes = searchParams.getAll('code');
    const states = searchParams.getAll('state');
    const code = codes.length === 1 ? codes[0] : null;
    const state = states.length === 1 ? states[0] : null;
    const oidcError = searchParams.get('error');
    window.history.replaceState(window.history.state, '', '/oidc-callback');
    let pending: string | null;
    let pendingLogin: string | null;
    try {
      pending = sessionStorage.getItem('oidc-link');
      pendingLogin = sessionStorage.getItem('oidc-login');
      sessionStorage.removeItem('oidc-login');
    } catch {
      setError('Unable to verify your sign-in. Please restart Single Sign-On.');
      return;
    }

    if (pending) {
      setIsLinkFlow(true);
      try {
        const flow = JSON.parse(pending);
        if (!state || state !== flow.state || typeof flow.fingerprint !== 'string') throw new Error();
        if (oidcError) {
          sessionStorage.removeItem('oidc-link');
          setError(searchParams.get('error_description') || 'The identity provider refused account linking.');
          return;
        }
        if (!code) throw new Error();
        const token = localStorage.getItem('token');
        if (!token) throw new Error();
        tokenFingerprint(token).then(fingerprint => {
          if (fingerprint !== flow.fingerprint || localStorage.getItem('token') !== token) {
            sessionStorage.removeItem('oidc-link');
            setError('Your session changed. Please restart account linking.');
          } else {
            setLink({ code, state, fingerprint });
          }
        }).catch(() => {
          sessionStorage.removeItem('oidc-link');
          setError('Unable to verify your session. Please restart account linking.');
        });
      } catch {
        sessionStorage.removeItem('oidc-link');
        setError('Invalid or expired account link. Please restart from your profile.');
      }
      return;
    }

    if (!pendingLogin || !state || state !== pendingLogin) {
      setError('Invalid or expired sign-in. Please restart Single Sign-On.');
      return;
    }

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

  const submitLink = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!link || submitting) return;
    setSubmitting(true);
    const suppliedPassword = password;
    setPassword('');
    sessionStorage.removeItem('oidc-link');
    try {
      const token = localStorage.getItem('token');
      if (!token || await tokenFingerprint(token) !== link.fingerprint || localStorage.getItem('token') !== token) {
        throw new Error('Your session changed. Please restart account linking.');
      }
      // Link failures are also 401s; do not let the global interceptor log out the user.
      await axios.post(`${api.defaults.baseURL}/auth/oidc/link`, {
        code: link.code, state: link.state, password: suppliedPassword,
      }, { headers: { Authorization: `Bearer ${token}` } });
      navigate('/profile', { replace: true, state: { oidcLinked: true } });
    } catch (err: unknown) {
      setLink(null);
      setError((axios.isAxiosError(err) && err.response?.data?.detail) || (err instanceof Error && err.message) || 'Account linking failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-lg text-center">
        {error ? (
          <>
            <h2 className="text-xl font-bold text-gray-900 mb-2">{isLinkFlow ? 'Account linking failed' : 'Sign-in failed'}</h2>
            <p className="text-sm text-gray-600 mb-6">{error}</p>
            <button
              onClick={() => navigate(isLinkFlow ? '/profile' : '/login', { replace: true })}
              className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              {isLinkFlow ? 'Back to profile' : 'Back to sign in'}
            </button>
          </>
        ) : link ? (
          <form onSubmit={submitLink} className="text-left">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Link Single Sign-On</h2>
            <p className="text-sm text-gray-600 mb-4">Confirm your local account password to complete linking.</p>
            <label htmlFor="link-password" className="block text-sm font-medium text-gray-700">Current password</label>
            <input id="link-password" type="password" autoComplete="current-password" required value={password}
              onChange={event => setPassword(event.target.value)} disabled={submitting}
              className="mt-1 mb-4 w-full px-3 py-2 border border-gray-300 rounded-md" />
            <button type="submit" disabled={submitting} className="w-full py-2 px-4 rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50">
              {submitting ? 'Linking...' : 'Confirm link'}
            </button>
            <button type="button" disabled={submitting} onClick={() => {
              sessionStorage.removeItem('oidc-link');
              navigate('/profile', { replace: true });
            }} className="w-full mt-3 py-2 text-sm text-gray-600">Cancel</button>
          </form>
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
