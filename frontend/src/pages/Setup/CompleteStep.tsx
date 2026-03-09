import { useEffect, useState, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { setupAPI } from "../../services/api";

interface CompleteStepProps {
  setupData: any;
  onComplete: () => void;
}

export default function CompleteStep({
  setupData,
  onComplete,
}: CompleteStepProps) {
  const [isCompleting, setIsCompleting] = useState(false);
  const [backupId, setBackupId] = useState<number | null>(null);
  const hasCompleted = useRef(false);

  const completeMutation = useMutation({
    mutationFn: setupAPI.complete,
    onSuccess: (data) => {
      setBackupId(data.backup_id);
      setIsCompleting(false);
    },
    onError: () => {
      setIsCompleting(false);
    },
  });

  useEffect(() => {
    // Prevent double-calling in React strict mode
    if (hasCompleted.current) return;
    hasCompleted.current = true;

    // Auto-trigger completion
    setIsCompleting(true);
    completeMutation.mutate();
  }, []);

  return (
    <div className="space-y-6 text-center">
      {isCompleting ? (
        <>
          <div className="mx-auto w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mb-4">
            <svg
              className="w-10 h-10 text-blue-600 dark:text-blue-400 animate-spin"
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
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Completing Setup...
          </h2>
          <p className="text-gray-600 dark:text-gray-300">
            Creating initial backup and finalizing configuration.
          </p>
        </>
      ) : (
        <>
          <div className="mx-auto w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <svg
              className="w-10 h-10 text-green-600 dark:text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Setup Complete!
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-300 mb-6">
            Your Linguard instance is ready to use.
          </p>

          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6 text-left">
            <h3 className="font-semibold text-green-900 dark:text-green-400 mb-3">
              What we configured:
            </h3>
            <ul className="space-y-2 text-sm text-green-800 dark:text-green-400">
              <li className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                Admin account:{" "}
                <strong className="ml-1">{setupData.username}</strong>
              </li>
              <li className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                Basic settings
              </li>
              <li className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                Server: <strong className="ml-1">{setupData.serverName}</strong>
              </li>
              <li className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                Peer: <strong className="ml-1">{setupData.peerName}</strong>
              </li>
            </ul>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-800 dark:text-blue-400">
              <strong>Ready to go!</strong> Click below to access your VPN
              management dashboard.
            </p>
          </div>

          <button
            onClick={onComplete}
            className="w-full bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium text-lg transition-colors"
          >
            Go to Dashboard
          </button>
        </>
      )}
    </div>
  );
}
