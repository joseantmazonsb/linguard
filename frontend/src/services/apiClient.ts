import axios from 'axios';

// Empty base URL = same origin (works behind reverse proxies like nginx).
// Set VITE_API_URL to override (e.g. direct backend access during development).
const API_URL = import.meta.env.VITE_API_URL || '';

// DEBUG: report what this executing bundle actually uses
console.log(
  `[Linguard] API_URL=${JSON.stringify(API_URL)} origin=${location.origin} page=${location.href}`
);

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: async (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const response = await api.post('/auth/token', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  getProfile: async () => {
    const response = await api.get('/auth/profile');
    return response.data;
  },
  updateProfile: async (data: { email: string }) => {
    const response = await api.put('/auth/profile', data);
    return response.data;
  },
  changePassword: async (data: { current_password: string; new_password: string }) => {
    const response = await api.post('/auth/change-password', data);
    return response.data;
  },
  listUsers: async () => {
    const response = await api.get('/auth/users');
    return response.data;
  },
  updateUserRole: async (userId: number, role: 'admin' | 'standard') => {
    const response = await api.put(`/auth/users/${userId}`, { role });
    return response.data;
  },
};

export const oidcAPI = {
  getConfig: async () => {
    const response = await api.get('/auth/oidc/config');
    return response.data as { oidc_enabled: boolean; auth_mode: string; provider_name: string | null };
  },
  getLogin: async () => {
    const response = await api.get('/auth/oidc/login');
    return response.data as { authorization_url: string };
  },
  callback: async (code: string, state: string) => {
    const response = await api.post('/auth/oidc/callback', { code, state });
    return response.data;
  },
  test: async (data: { discovery_url: string; client_id: string; client_secret: string; scopes: string }) => {
    const response = await api.post('/auth/oidc/test', data);
    return response.data as { success: boolean; provider_name: string | null; message: string };
  },
};

export const serversAPI = {
  list: async () => {
    const response = await api.get('/servers');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/servers/${id}`);
    return response.data;
  },
  getDefaults: async () => {
    const response = await api.get('/servers/defaults/autofill');
    return response.data;
  },
  create: async (data: any) => {
    const response = await api.post('/servers', data);
    return response.data;
  },
  update: async (id: number, data: any) => {
    const response = await api.put(`/servers/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/servers/${id}`);
    return response.data;
  },
  start: async (id: number) => {
    const response = await api.post(`/servers/${id}/start`);
    return response.data;
  },
  stop: async (id: number) => {
    const response = await api.post(`/servers/${id}/stop`);
    return response.data;
  },
  reload: async (id: number) => {
    const response = await api.post(`/servers/${id}/reload`);
    return response.data;
  },
  getConfig: async (id: number) => {
    const response = await api.get(`/servers/${id}/config`);
    return response.data;
  },
  import: async (file: File) => {
    const formData = new FormData();
    formData.append('config_file', file);
    const response = await api.post('/servers/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

export const peersAPI = {
  list: async (serverId?: number, skip?: number, limit?: number) => {
    const params: any = {};
    if (serverId !== undefined) params.server_id = serverId;
    if (skip !== undefined) params.skip = skip;
    if (limit !== undefined) params.limit = limit;
    const response = await api.get('/peers', { params });
    return response.data;
  },
  count: async (serverId?: number) => {
    const params: any = {};
    if (serverId !== undefined) params.server_id = serverId;
    const response = await api.get('/peers/count', { params });
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/peers/${id}`);
    return response.data;
  },
  getDefaults: async (serverId: number) => {
    const response = await api.get(`/peers/defaults/${serverId}`);
    return response.data;
  },
  create: async (data: any) => {
    const response = await api.post('/peers', data);
    return response.data;
  },
  update: async (id: number, data: any) => {
    const response = await api.put(`/peers/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/peers/${id}`);
    return response.data;
  },
  migrate: async (id: number, migrationData: any) => {
    const response = await api.post(`/peers/${id}/migrate`, migrationData);
    return response.data;
  },
  getConfig: async (id: number) => {
    const response = await api.get(`/peers/${id}/config`);
    return response.data;
  },
  getQRCode: async (id: number) => {
    const response = await api.get(`/peers/${id}/qrcode`, {
      responseType: 'blob',
    });
    return response.data;
  },
  import: async (serverId: number, file: File) => {
    const formData = new FormData();
    formData.append('config_file', file);
    const response = await api.post(`/peers/import?server_id=${serverId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

export const settingsAPI = {
  getGlobal: async () => {
    const response = await api.get('/settings/global');
    return response.data;
  },
  updateGlobal: async (data: any) => {
    const response = await api.put('/settings/global', data);
    return response.data;
  },
};

export const auditAPI = {
  list: async (params?: {
    action?: string;
    resource_type?: string;
    resource_id?: number;
    user_id?: number;
    start_date?: string;
    end_date?: string;
    search?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/audit', { params });
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/audit/${id}`);
    return response.data;
  },
  getResourceHistory: async (resourceType: string, resourceId: number) => {
    const response = await api.get(`/audit/resource/${resourceType}/${resourceId}`);
    return response.data;
  },
  getUserActions: async (userId: number) => {
    const response = await api.get(`/audit/user/${userId}/actions`);
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/audit/stats/summary');
    return response.data;
  },
};

export const backupAPI = {
  list: async () => {
    const response = await api.get('/backups');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/backups/${id}`);
    return response.data;
  },
  create: async (data: { description?: string; encrypt?: boolean; passphrase?: string }) => {
    const response = await api.post('/backups', data);
    return response.data;
  },
  restore: async (id: number, passphrase?: string, overwrite: boolean = false) => {
    const response = await api.post(`/backups/${id}/restore`, null, {
      params: { passphrase, overwrite },
    });
    return response.data;
  },
  download: async (id: number) => {
    const response = await api.get(`/backups/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },
  upload: async (file: File, description?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) {
      formData.append('description', description);
    }
    const response = await api.post('/backups/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/backups/${id}`);
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/backups/stats/summary');
    return response.data;
  },
};

export const versionAPI = {
  getCurrent: async () => {
    const response = await api.get('/version/current');
    return response.data;
  },
  checkUpdates: async () => {
    const response = await api.get('/version/check-updates');
    return response.data;
  },
  getChangelog: async () => {
    const response = await api.get('/version/changelog');
    return response.data;
  },
};

export const systemAPI = {
  getInfo: async () => {
    const response = await api.get('/system');
    return response.data;
  },
};

export const setupAPI = {
  getStatus: async () => {
    const response = await api.get('/setup/status');
    return response.data;
  },
  reset: async () => {
    const response = await api.post('/setup/reset');
    return response.data;
  },
  configureDatabase: async (data: { database_type: string; database_url: string }) => {
    const response = await api.post('/setup/configure-database', data);
    return response.data;
  },
  initialize: async (data: { username: string; email: string; password: string }) => {
    const response = await api.post('/setup/initialize', data);
    return response.data;
  },
  configureGlobals: async (data: {
    // DNS Configuration
    dns_primary?: string;
    dns_secondary?: string;
    // Security Settings
    secret_key: string;  // Required
    algorithm?: string;
    access_token_expire_minutes?: number;
    disable_auth?: boolean;
    // Logging Settings
    log_level?: string;
    log_path?: string | null;
    // Backup Settings
    backup_dir: string;  // Required
    backup_retention_days?: number;
    backup_auto_cleanup_enabled?: boolean;
    backup_periodic_enabled?: boolean;
    backup_schedule_frequency?: string;
    backup_schedule_hour?: number;
    backup_schedule_minute?: number;
  }) => {
    const response = await api.post('/setup/configure-globals', data);
    return response.data;
  },
  configureAuth: async (data: {
    skip: boolean;
    auth_mode?: string;
    oidc_discovery_url?: string;
    oidc_client_id?: string;
    oidc_client_secret?: string;
    oidc_scopes?: string;
    oidc_auto_provision?: boolean;
    oidc_admin_groups?: string;
  }) => {
    const response = await api.post('/setup/configure-auth', data);
    return response.data;
  },
  createServer: async (data: any) => {
    const response = await api.post('/setup/create-server', data);
    return response.data;
  },
  createPeer: async (data: any) => {
    const response = await api.post('/setup/create-peer', data);
    return response.data;
  },
  complete: async () => {
    const response = await api.post('/setup/complete');
    return response.data;
  },
};

export const integrationsAPI = {
  list: async () => {
    const response = await api.get('/integrations');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/integrations/${id}`);
    return response.data;
  },
  create: async (data: any) => {
    const response = await api.post('/integrations', data);
    return response.data;
  },
  update: async (id: number, data: any) => {
    const response = await api.put(`/integrations/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/integrations/${id}`);
    return response.data;
  },
  getTypes: async () => {
    const response = await api.get('/integrations/types/available');
    return response.data;
  },
};

export const notificationsAPI = {
  list: async (unreadOnly: boolean = false, limit: number = 50, offset: number = 0) => {
    const response = await api.get('/notifications', {
      params: { unread_only: unreadOnly, limit, offset },
    });
    return response.data;
  },
  getUnreadCount: async () => {
    const response = await api.get('/notifications/unread/count');
    return response.data;
  },
  markAsRead: async (id: number) => {
    const response = await api.put(`/notifications/${id}`, { read: true });
    return response.data;
  },
  markAllAsRead: async () => {
    const response = await api.put('/notifications/read/all');
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/notifications/${id}`);
    return response.data;
  },
  deleteAll: async () => {
    const response = await api.delete('/notifications/all');
    return response.data;
  },
};

export const logsAPI = {
  getInfo: async () => {
    const response = await api.get('/logs/info');
    return response.data;
  },
  // Note: Stream endpoint is accessed directly via EventSource in the component
  // Download endpoint is accessed via window.open
};

export const utilsAPI = {
  generateKeypair: async () => {
    const response = await api.get('/utils/generate-keypair');
    return response.data;
  },
  generatePresharedKey: async () => {
    const response = await api.get('/utils/generate-preshared-key');
    return response.data;
  },
  derivePublicKey: async (privateKey: string) => {
    const response = await api.post('/utils/derive-public-key', { private_key: privateKey });
    return response.data;
  },
};

export const metricsAPI = {
  collectNow: async () => {
    const response = await api.post('/metrics/collect');
    return response.data;
  },
  getServerMetrics: async (serverId: number, hours: number = 24) => {
    const response = await api.get(`/metrics/server/${serverId}`, { params: { hours } });
    return response.data;
  },
  getPeerMetrics: async (peerId: number, hours: number = 24) => {
    const response = await api.get(`/metrics/peer/${peerId}`, { params: { hours } });
    return response.data;
  },
  getDashboardMetrics: async (hours: number = 24) => {
    const response = await api.get('/metrics/dashboard', { params: { hours } });
    return response.data;
  },
  getServersAggregateMetrics: async (hours: number = 24) => {
    const response = await api.get('/metrics/servers/aggregate', { params: { hours } });
    return response.data;
  },
  getPeersAggregateMetrics: async (hours: number = 24) => {
    const response = await api.get('/metrics/peers/aggregate', { params: { hours } });
    return response.data;
  },
};

export const healthAPI = {
  check: async () => {
    const response = await axios.get(`${API_URL}/health`);
    return response.data;
  },
};

export const trafficTriggersAPI = {
  list: async (params?: { enabled_only?: boolean; scope?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/traffic-triggers', { params });
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/traffic-triggers/${id}`);
    return response.data;
  },
  create: async (data: any) => {
    const response = await api.post('/traffic-triggers', data);
    return response.data;
  },
  update: async (id: number, data: any) => {
    const response = await api.put(`/traffic-triggers/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/traffic-triggers/${id}`);
    return response.data;
  },
  test: async (id: number) => {
    const response = await api.post(`/traffic-triggers/${id}/test`);
    return response.data;
  },
};

export const pluginsAPI = {
  list: async () => {
    const response = await api.get('/plugins');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/plugins/${id}`);
    return response.data;
  },
  discover: async () => {
    const response = await api.post('/plugins/discover');
    return response.data;
  },
  enable: async (id: number) => {
    const response = await api.post(`/plugins/${id}/enable`);
    return response.data;
  },
  disable: async (id: number) => {
    const response = await api.post(`/plugins/${id}/disable`);
    return response.data;
  },
  updateConfig: async (id: number, config: any) => {
    const response = await api.put(`/plugins/${id}/config`, { config });
    return response.data;
  },
  delete: async (id: number) => {
    const response = await api.delete(`/plugins/${id}`);
    return response.data;
  },
};
