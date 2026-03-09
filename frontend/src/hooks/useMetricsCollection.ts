import { useEffect } from 'react';
import { metricsAPI } from '../services/api';

const COLLECTION_INTERVAL = 5 * 60 * 1000; // 5 minutes

export function useMetricsCollection(enabled: boolean = true) {
  useEffect(() => {
    // Only collect metrics if enabled (i.e., setup is complete)
    if (!enabled) {
      return;
    }

    // Collect metrics immediately on mount
    const collectMetrics = async () => {
      try {
        await metricsAPI.collectNow();
        console.log('Metrics collected successfully');
      } catch (error) {
        console.error('Failed to collect metrics:', error);
      }
    };

    // Initial collection
    collectMetrics();

    // Setup interval for periodic collection
    const intervalId = setInterval(collectMetrics, COLLECTION_INTERVAL);

    // Cleanup on unmount
    return () => clearInterval(intervalId);
  }, [enabled]);
}
