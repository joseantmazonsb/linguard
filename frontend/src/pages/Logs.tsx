import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import { logsAPI } from '../services/api';
import CustomSelect from '../components/CustomSelect';
import ToggleSwitch from '../components/ToggleSwitch';

interface LogInfo {
  path: string;
  size_bytes: number;
  size_human: string;
  line_count: number;
  last_modified: number;
}

export default function Logs() {
  const [logs, setLogs] = useState<string[]>([]);
  const [isTailing, setIsTailing] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [initialLines, setInitialLines] = useState(100);
  const [copied, setCopied] = useState(false);
  const [showPathTooltip, setShowPathTooltip] = useState(false);
  const [isPathTruncated, setIsPathTruncated] = useState(false);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pathRef = useRef<HTMLDivElement>(null);

  // Fetch log file info
  const { data: logInfo, isLoading: infoLoading } = useQuery<LogInfo>({
    queryKey: ['log-info'],
    queryFn: logsAPI.getInfo,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Check if path is truncated
  useEffect(() => {
    if (pathRef.current && logInfo?.path) {
      const isTruncated = pathRef.current.scrollWidth > pathRef.current.clientWidth;
      setIsPathTruncated(isTruncated);
    }
  }, [logInfo?.path]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const startTailing = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setLogs([]); // Clear existing logs
    setIsTailing(true);

    const eventSource = new EventSource(
      `http://localhost:8000/api/v1/logs/stream?lines=${initialLines}`
    );

    eventSource.onmessage = (event) => {
      const logLine = event.data;
      setLogs((prev) => [...prev, logLine]);
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      eventSource.close();
      setIsTailing(false);
    };

    eventSourceRef.current = eventSource;
  };

  const stopTailing = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsTailing(false);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const handleDownload = () => {
    window.open('http://localhost:8000/api/v1/logs/download', '_blank');
  };

  const handleCopyPath = () => {
    if (logInfo?.path) {
      navigator.clipboard.writeText(logInfo.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  const getLogLevelColor = (line: string) => {
    if (line.includes('ERROR') || line.includes('CRITICAL')) {
      return 'text-red-600 dark:text-red-400';
    } else if (line.includes('WARNING') || line.includes('WARN')) {
      return 'text-yellow-600 dark:text-yellow-400';
    } else if (line.includes('INFO')) {
      return 'text-blue-600 dark:text-blue-400';
    } else if (line.includes('DEBUG')) {
      return 'text-gray-500 dark:text-gray-400';
    }
    return 'text-gray-700 dark:text-gray-300';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2 dark:text-white">System Logs</h1>
        <p className="text-gray-600 dark:text-gray-400">
          View and monitor backend application logs in real-time
        </p>
      </div>

      {/* Log Info Statistics */}
      {logInfo && !infoLoading && (
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-6">
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm text-gray-600 dark:text-gray-400">File Size</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{logInfo.size_human}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm text-gray-600 dark:text-gray-400">Total Lines</div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {logInfo.line_count.toLocaleString()}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm text-gray-600 dark:text-gray-400">Last Modified</div>
            <div className="text-sm font-medium text-purple-600 dark:text-purple-400 mt-1">
              {formatDate(logInfo.last_modified)}
            </div>
          </div>
          <div className="md:col-span-3 bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Log File</div>
            <div className="flex items-center gap-2">
              <div 
                className="relative flex-1 min-w-0"
                onMouseEnter={() => isPathTruncated && setShowPathTooltip(true)}
                onMouseLeave={() => setShowPathTooltip(false)}
              >
                <div 
                  ref={pathRef}
                  className={`text-sm font-mono text-gray-700 dark:text-gray-300 truncate ${isPathTruncated ? 'cursor-help' : ''}`}
                >
                  {logInfo.path}
                </div>
                {showPathTooltip && isPathTruncated && (
                  <div className="absolute z-50 bottom-full left-0 mb-2 w-max max-w-md px-3 py-2 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded-lg shadow-lg">
                    <div className="break-all">{logInfo.path}</div>
                    <div className="absolute top-full left-4 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900 dark:border-t-gray-700"></div>
                  </div>
                )}
              </div>
              <button
                onClick={handleCopyPath}
                className="flex-shrink-0 p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Copy path to clipboard"
              >
                {copied ? (
                  <svg className="w-4 h-4 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:border dark:border-gray-700 mb-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Live Tail Controls */}
          <div className="flex items-center gap-2">
            {!isTailing ? (
              <button
                onClick={startTailing}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 dark:hover:bg-green-600 transition-colors font-medium flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Start Live Tail
              </button>
            ) : (
              <button
                onClick={stopTailing}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 dark:hover:bg-red-600 transition-colors font-medium flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Stop Live Tail
              </button>
            )}

            <button
              onClick={clearLogs}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
            >
              Clear
            </button>

            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download
            </button>
          </div>

          {/* Settings */}
          <div className="flex items-center gap-4 ml-auto">
            <ToggleSwitch
              checked={autoScroll}
              onChange={(checked) => setAutoScroll(checked)}
              label="Auto-scroll"
            />

            <label className="flex items-center gap-2 text-sm dark:text-gray-300">
              <span>Initial lines:</span>
              <CustomSelect
                value={initialLines}
                onChange={(value) => setInitialLines(Number(value))}
                options={[
                  { value: 50, label: '50' },
                  { value: 100, label: '100' },
                  { value: 200, label: '200' },
                  { value: 500, label: '500' },
                ]}
                className={isTailing ? 'opacity-50' : ''}
              />
            </label>
          </div>
        </div>

        {/* Status Indicator */}
        {isTailing && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Live tailing • {logs.length} lines loaded
            </span>
          </div>
        )}
      </div>

      {/* Logs Display */}
      <div className="bg-gray-100 dark:bg-gray-900 rounded-lg shadow-lg overflow-hidden border border-gray-300 dark:border-gray-700">
        <div
          ref={logsContainerRef}
          className="p-4 font-mono text-sm overflow-y-auto"
          style={{ height: '600px' }}
        >
          {logs.length === 0 ? (
            <div className="text-gray-500 dark:text-gray-400 text-center py-8">
              {isTailing
                ? 'Waiting for logs...'
                : 'Click "Start Live Tail" to view logs'}
            </div>
          ) : (
            logs.map((line, index) => (
              <div key={index} className={`${getLogLevelColor(line)} whitespace-pre-wrap break-all`}>
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Help Text */}
      <div className="mt-4 p-4 bg-blue-50 dark:bg-gray-800 rounded-lg dark:border dark:border-gray-700">
        <h3 className="font-semibold text-blue-900 dark:text-white mb-2">💡 Tips</h3>
        <ul className="text-sm text-blue-800 dark:text-gray-300 space-y-1">
          <li>• Use "Start Live Tail" to watch logs in real-time</li>
          <li>• Enable "Auto-scroll" to automatically follow new logs</li>
          <li>• Download the complete log file for offline analysis</li>
          <li>• Log levels are color-coded: ERROR (red), WARNING (yellow), INFO (blue)</li>
        </ul>
      </div>
    </div>
  );
}
