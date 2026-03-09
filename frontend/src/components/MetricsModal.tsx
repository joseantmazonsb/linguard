import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { metricsAPI } from '../services/api';
import type { MetricsData } from '../types';

type TimeRange = 24 | 168 | 720; // 24h, 7d, 30d

interface MetricsModalProps {
  type: 'server' | 'peer';
  id: number;
  name: string;
  onClose: () => void;
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

const formatDate = (dateStr: string, timeRange: TimeRange): string => {
  const date = new Date(dateStr);
  
  if (timeRange === 24) {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } else {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  }
};

export default function MetricsModal({ type, id, name, onClose }: MetricsModalProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(24);
  const [isCollecting, setIsCollecting] = useState(false);

  const { data, isLoading, error, refetch } = useQuery<MetricsData>({
    queryKey: ['metrics', type, id, timeRange],
    queryFn: async () => {
      if (type === 'server') {
        return await metricsAPI.getServerMetrics(id, timeRange);
      } else {
        return await metricsAPI.getPeerMetrics(id, timeRange);
      }
    },
  });

  const handleCollectNow = async () => {
    setIsCollecting(true);
    try {
      await metricsAPI.collectNow();
      // Wait a bit for the collection to complete, then refetch
      setTimeout(() => {
        refetch();
        setIsCollecting(false);
      }, 2000);
    } catch (err) {
      console.error('Failed to collect metrics:', err);
      setIsCollecting(false);
    }
  };

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Prepare chart data
  const chartData = data?.metrics.map(metric => ({
    time: formatDate(metric.recorded_at, timeRange),
    rx: metric.rx_bytes / (1024 * 1024), // Convert to MB
    tx: metric.tx_bytes / (1024 * 1024), // Convert to MB
    fullTime: metric.recorded_at,
  })) || [];

  // Calculate totals
  const latestMetric = data?.metrics[data.metrics.length - 1];
  const totalRx = latestMetric?.rx_bytes || 0;
  const totalTx = latestMetric?.tx_bytes || 0;

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-100 dark:bg-cyan-900 rounded-lg">
              <svg className="w-6 h-6 text-cyan-600 dark:text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Traffic Metrics</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {type === 'server' ? 'Server' : 'Peer'}: {name}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCollectNow}
              disabled={isCollecting}
              className="px-3 py-2 text-sm font-medium text-cyan-700 dark:text-cyan-300 hover:bg-cyan-50 dark:hover:bg-cyan-900/20 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCollecting ? (
                <>
                  <svg className="animate-spin h-4 w-4 inline mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Collecting...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4 inline mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Time Range Selector */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setTimeRange(24)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 24
                  ? 'bg-cyan-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              24 Hours
            </button>
            <button
              onClick={() => setTimeRange(168)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 168
                  ? 'bg-cyan-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              7 Days
            </button>
            <button
              onClick={() => setTimeRange(720)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                timeRange === 720
                  ? 'bg-cyan-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              30 Days
            </button>
          </div>

          {/* Current Totals */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 p-6 rounded-lg border border-green-200 dark:border-green-800">
              <div className="flex items-center gap-3 mb-2">
                <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
                <span className="text-sm font-medium text-green-700 dark:text-green-300">Total Received</span>
              </div>
              <p className="text-3xl font-bold text-green-900 dark:text-green-100">{formatBytes(totalRx)}</p>
            </div>
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 p-6 rounded-lg border border-blue-200 dark:border-blue-800">
              <div className="flex items-center gap-3 mb-2">
                <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
                <span className="text-sm font-medium text-blue-700 dark:text-blue-300">Total Transmitted</span>
              </div>
              <p className="text-3xl font-bold text-blue-900 dark:text-blue-100">{formatBytes(totalTx)}</p>
            </div>
          </div>

          {/* Chart */}
          {isLoading ? (
            <div className="flex items-center justify-center h-96">
              <div className="flex flex-col items-center gap-3">
                <svg className="animate-spin h-8 w-8 text-cyan-600" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p className="text-gray-500 dark:text-gray-400">Loading metrics...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-96">
              <div className="text-center">
                <svg className="w-12 h-12 text-red-500 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-gray-700 dark:text-gray-300 font-medium">Failed to load metrics</p>
                <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">Please try again later</p>
              </div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-96">
              <div className="text-center">
                <svg className="w-12 h-12 text-gray-400 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p className="text-gray-700 dark:text-gray-300 font-medium">No metrics data available</p>
                <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">Metrics will appear here once collected</p>
                <button
                  onClick={handleCollectNow}
                  className="mt-4 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors"
                >
                  Collect Now
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                  <XAxis 
                    dataKey="time" 
                    stroke="#9CA3AF"
                    tick={{ fill: '#9CA3AF' }}
                    tickLine={{ stroke: '#9CA3AF' }}
                  />
                  <YAxis 
                    stroke="#9CA3AF"
                    tick={{ fill: '#9CA3AF' }}
                    tickLine={{ stroke: '#9CA3AF' }}
                    label={{ value: 'Traffic (MB)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F9FAFB'
                    }}
                    formatter={(value: number) => [`${value.toFixed(2)} MB`, '']}
                  />
                  <Legend 
                    wrapperStyle={{ color: '#9CA3AF' }}
                    iconType="line"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="rx" 
                    stroke="#10B981" 
                    strokeWidth={2}
                    name="Received"
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="tx" 
                    stroke="#3B82F6" 
                    strokeWidth={2}
                    name="Transmitted"
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Summary Info */}
          {data && data.metrics.length > 0 && (
            <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="flex flex-wrap gap-6 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Data Points:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-white">{data.summary.total_data_points}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Time Range:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-white">{data.summary.time_range_hours} hours</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Total Traffic:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-white">{formatBytes(totalRx + totalTx)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
