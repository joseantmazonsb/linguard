import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '../store/auth';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 5;

export interface WebSocketMessage {
  type: 'connected' | 'pong' | 'metrics_update' | 'notification' | 'server_status_change' | 'health_update';
  data?: any;
  message?: string;
}

export interface MetricsData {
  servers: {
    total_rx_bytes: number;
    total_tx_bytes: number;
    top_servers: Array<{
      id: number;
      name: string;
      rx_bytes: number;
      tx_bytes: number;
    }>;
  };
  peers: {
    total_rx_bytes: number;
    total_tx_bytes: number;
    top_peers: Array<{
      id: number;
      name: string;
      rx_bytes: number;
      tx_bytes: number;
    }>;
  };
  timestamp: string;
}

export interface NotificationData {
  id: number;
  title: string;
  message: string;
  type: 'success' | 'warning' | 'error' | 'info' | 'event';
  link?: string;
  read: boolean;
  created_at: string;
}

export interface ServerStatusChangeData {
  server_id: number;
  name: string;
  status: string;
  event_type: string;
  detected?: boolean;
}

export interface HealthCheckData {
  status: string;
  message: string | null;
}

export interface HealthData {
  status: string;
  timestamp: string;
  checks: {
    database: HealthCheckData;
    wireguard: HealthCheckData;
    ip_forwarding: HealthCheckData;
    firewall: HealthCheckData;
  };
}

interface UseWebSocketOptions {
  enabled?: boolean;
  onMetricsUpdate?: (data: MetricsData) => void;
  onNotification?: (data: NotificationData) => void;
  onServerStatusChange?: (data: ServerStatusChangeData) => void;
  onHealthUpdate?: (data: HealthData) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    enabled = true,
    onMetricsUpdate,
    onNotification,
    onServerStatusChange,
    onHealthUpdate,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<number | null>(null);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const token = useAuthStore((state) => state.token);
  
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    // Don't connect if disabled or not authenticated
    if (!enabled || !isAuthenticated || !token) {
      console.log('WebSocket connection skipped:', { enabled, isAuthenticated, hasToken: !!token });
      return;
    }

    // Don't reconnect if already connected or connecting
    if (ws.current?.readyState === WebSocket.OPEN || ws.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      console.log('Connecting to WebSocket:', WS_URL);
      
      // Create WebSocket connection with token as query param
      const wsUrl = `${WS_URL}?token=${encodeURIComponent(token)}`;
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;
        onConnect?.();
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('WebSocket message:', message);

          switch (message.type) {
            case 'connected':
              console.log('WebSocket handshake complete');
              break;

            case 'metrics_update':
              onMetricsUpdate?.(message.data as MetricsData);
              break;

            case 'notification':
              onNotification?.(message.data as NotificationData);
              break;

            case 'server_status_change':
              onServerStatusChange?.(message.data as ServerStatusChangeData);
              break;

            case 'health_update':
              onHealthUpdate?.(message.data as HealthData);
              break;

            case 'pong':
              // Heartbeat response
              break;

            default:
              console.warn('Unknown WebSocket message type:', message.type);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        onDisconnect?.();

        // Attempt to reconnect
        if (enabled && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.current += 1;
          console.log(`Reconnecting... Attempt ${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS}`);
          
          reconnectTimeout.current = window.setTimeout(() => {
            connect();
          }, RECONNECT_INTERVAL);
        } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error('Max reconnection attempts reached. Giving up.');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [enabled, isAuthenticated, token, onConnect, onDisconnect, onError, onMetricsUpdate, onNotification, onServerStatusChange, onHealthUpdate]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(message);
    } else {
      console.warn('WebSocket is not connected. Cannot send message:', message);
    }
  }, []);

  const ping = useCallback(() => {
    sendMessage('ping');
  }, [sendMessage]);

  // Connect on mount if enabled and authenticated
  useEffect(() => {
    if (enabled && isAuthenticated && token) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [enabled, isAuthenticated, token, connect, disconnect]);

  // Setup heartbeat to keep connection alive
  useEffect(() => {
    if (!isConnected) return;

    const heartbeatInterval = setInterval(() => {
      ping();
    }, 30000); // Ping every 30 seconds

    return () => clearInterval(heartbeatInterval);
  }, [isConnected, ping]);

  return {
    isConnected,
    sendMessage,
    ping,
    reconnect: connect,
    disconnect,
  };
}
