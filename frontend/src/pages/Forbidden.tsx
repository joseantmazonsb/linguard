import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

export default function Forbidden() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-lg text-center">
        <div className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Access denied</h2>
        <p className="text-sm text-gray-600 mb-6">
          You don't have permission to access this area of Linguard. Ask an administrator
          if you believe you should have access.
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => navigate('/profile')}
            className="py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Go to profile
          </button>
          <button
            onClick={() => logout()}
            className="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
