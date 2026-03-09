// Server types
export type Server = {
  id: number;
  name: string;
  description?: string;
  interface?: string;  // Auto-detected
  listen_port: number;
  endpoint: string;
  public_key: string;
  private_key: string;
  ipv4_address?: string;
  ipv6_address?: string;
  dns_primary?: string;
  dns_secondary?: string;
  bounce_via_server_id?: number;
  status: string;
  enabled: boolean;
  autostart: boolean;  // Auto-start server on application boot
  needs_reload?: boolean;  // Server needs reload after peer changes
  peer_count?: number;  // Number of peers associated with this server
  rx_bytes?: number;
  tx_bytes?: number;
  created_at: string;
  updated_at?: string;
  last_started_at?: string;
  last_stopped_at?: string;
}

// Peer types
export type Peer = {
  id: number;
  name: string;
  description?: string;
  server_id: number;
  public_key: string;
  private_key: string;
  preshared_key?: string;
  address: string;
  ipv4_address?: string;
  ipv6_address?: string;
  allowed_ips: string;
  dns_primary?: string;
  dns_secondary?: string;
  persistent_keepalive: number;
  enabled: boolean;
  is_online?: boolean;
  rx_bytes?: number;
  tx_bytes?: number;
  last_handshake?: string;
  created_at: string;
  updated_at: string;
}

// Traffic Metrics types
export type TrafficMetric = {
  recorded_at: string;
  rx_bytes: number;
  tx_bytes: number;
  rx_bytes_delta: number;
  tx_bytes_delta: number;
  is_connected: boolean;
  handshake_at?: string;
}

export type MetricsData = {
  metrics: TrafficMetric[];
  summary: {
    total_data_points: number;
    time_range_hours: number;
  };
}

// Integration types
export type Integration = {
  id: number;
  name: string;
  description?: string;
  type: string;
  config: Record<string, any>;
  events_subscribed: string[];
  enabled: boolean;
  total_triggered: number;
  last_triggered_at?: string;
  created_at: string;
  updated_at?: string;
}

export type IntegrationType = {
  type: string;
  name: string;
  description: string;
  config_schema: Record<string, any>;
  icon: string;
  enabled: boolean;
}

// Notification types
export type Notification = {
  id: number;
  user_id: number;
  title: string;
  message: string;
  type: string;
  link?: string;
  event_type?: string;
  source_type?: string;
  source_id?: number;
  read: boolean;
  created_at: string;
  read_at?: string;
}

// Traffic Trigger types
export type TrafficScope = 'peer' | 'server' | 'global';
export type TrafficDirection = 'rx_only' | 'tx_only' | 'combined';
export type ThresholdWindow = 'last_hour' | 'last_24_hours' | 'last_7_days' | 'last_30_days';

export type TrafficTrigger = {
  id: number;
  name: string;
  scope: TrafficScope;
  peer_id?: number;
  peer_name?: string;
  server_id?: number;
  server_name?: string;
  direction: TrafficDirection;
  threshold_bytes: number;
  window: ThresholdWindow;
  cooldown_minutes: number;
  enabled: boolean;
  integration_ids: number[];
  integrations?: Array<{
    id: number;
    name: string;
    type: string;
  }>;
  last_triggered_at?: string;
  total_triggers: number;
  created_at: string;
  updated_at?: string;
}

export type TrafficTriggerCreate = {
  name: string;
  scope: TrafficScope;
  peer_id?: number;
  server_id?: number;
  direction: TrafficDirection;
  threshold_bytes: number;
  window: ThresholdWindow;
  cooldown_minutes: number;
  enabled: boolean;
  integration_ids: number[];
}

export type TrafficTriggerUpdate = {
  name?: string;
  threshold_bytes?: number;
  cooldown_minutes?: number;
  enabled?: boolean;
  integration_ids?: number[];
}

export type TrafficTriggerTestResponse = {
  trigger_id: number;
  trigger_name: string;
  would_fire: boolean;
  current_bytes: number;
  threshold_bytes: number;
  exceeded_by_bytes?: number;
  exceeded_by_percent?: number;
  in_cooldown: boolean;
  cooldown_remaining_minutes?: number;
  rx_bytes: number;
  tx_bytes: number;
  window_start: string;
  window_end: string;
}
