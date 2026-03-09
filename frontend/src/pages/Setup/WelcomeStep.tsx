export default function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="mx-auto w-20 h-20 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-10 h-10 text-blue-600 dark:text-blue-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Welcome to Linguard
        </h2>
        <p className="text-lg text-gray-600 dark:text-gray-300">
          Let's get your VPN management system up and running!
        </p>
      </div>

      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-300 mb-3">
          What we'll configure:
        </h3>
        <ul className="space-y-3">
          <li className="flex items-start">
            <svg
              className="w-6 h-6 text-blue-600 dark:text-blue-400 mr-3 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                You account
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Create your administrator credentials
              </p>
            </div>
          </li>
          <li className="flex items-start">
            <svg
              className="w-6 h-6 text-blue-600 dark:text-blue-400 mr-3 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                Some settings
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Not too much, just the basics
              </p>
            </div>
          </li>
          <li className="flex items-start">
            <svg
              className="w-6 h-6 text-blue-600 dark:text-blue-400 mr-3 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                First server
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Set up your initial VPN server
              </p>
            </div>
          </li>
          <li className="flex items-start">
            <svg
              className="w-6 h-6 text-blue-600 dark:text-blue-400 mr-3 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                First peer
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Create your first VPN client
              </p>
            </div>
          </li>
        </ul>
      </div>

      <div className="pt-4">
        <button
          onClick={onNext}
          className="w-full bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium text-lg transition-colors"
        >
          Get Started
        </button>
      </div>
    </div>
  );
}
