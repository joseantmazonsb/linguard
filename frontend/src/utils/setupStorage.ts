/**
 * Setup Storage Utility
 * Manages setup wizard state persistence in localStorage
 */

export type SetupStep = 'welcome' | 'database' | 'account' | 'globals' | 'auth' | 'server' | 'peer' | 'complete';

export interface SetupState {
  currentStep: SetupStep;
  data: {
    database?: {
      database_type?: string;
    };
    account?: {
      username?: string;
      email?: string;
    };
    globals?: {
      dns_primary?: string;
      dns_secondary?: string;
      default_ipv4_pool?: string;
      default_ipv6_pool?: string;
    };
    auth?: {
      skipped?: boolean;
      auth_mode?: string;
      oidc_client_id?: string;
      oidc_scopes?: string;
      oidc_auto_provision?: boolean;
      oidc_admin_groups?: string;
    };
    server?: {
      server_id?: number;
      name?: string;
      endpoint?: string;
      listen_port?: number;
      ipv4_address?: string;
      ipv6_address?: string;
    };
    peer?: {
      peer_id?: number;
      name?: string;
      ipv4_address?: string;
      ipv6_address?: string;
    };
  };
  lastUpdated: string;
}

const STORAGE_KEY = 'linguard_setup_state';

// Persist only fields needed to resume setup, never credentials or connection strings.
const PERSISTED_FIELDS = [
  'currentStep', 'lastUpdated', 'data', 'database', 'account', 'globals', 'auth', 'server', 'peer',
  'database_type', 'username', 'email', 'userId', 'dns_primary', 'dns_secondary',
  'default_ipv4_pool', 'default_ipv6_pool', 'algorithm', 'access_token_expire_minutes',
  'disable_auth', 'log_level', 'log_path', 'backup_dir', 'backup_retention_days',
  'backup_auto_cleanup_enabled', 'backup_periodic_enabled', 'backup_schedule_frequency',
  'backup_schedule_hour', 'backup_schedule_minute', 'skipped', 'auth_mode',
  'oidc_client_id', 'oidc_scopes', 'oidc_auto_provision',
  'oidc_admin_groups', 'server_id', 'serverId', 'serverName', 'peer_id', 'peerId',
  'peerName', 'name', 'endpoint', 'listen_port', 'ipv4_address', 'ipv6_address',
  'wireguardMissing', 'skipPeer',
];

/**
 * Save current setup state to localStorage
 */
export function saveSetupState(state: SetupState): void {
  try {
    const stateToSave = {
      ...state,
      lastUpdated: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave, PERSISTED_FIELDS));
  } catch (error) {
    console.error('Failed to save setup state:', error);
  }
}

/**
 * Load setup state from localStorage
 */
export function loadSetupState(): SetupState | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;

    const state = JSON.parse(stored) as SetupState;
    
    // Check if state is older than 24 hours
    const lastUpdated = new Date(state.lastUpdated);
    const now = new Date();
    const hoursDiff = (now.getTime() - lastUpdated.getTime()) / (1000 * 60 * 60);
    
    if (!state.data || !state.currentStep || !Number.isFinite(hoursDiff) || hoursDiff > 24) {
      // State is too old, clear it
      clearSetupState();
      return null;
    }

    const sanitized = JSON.stringify(state, PERSISTED_FIELDS);
    if (sanitized !== stored) localStorage.setItem(STORAGE_KEY, sanitized);
    return JSON.parse(sanitized) as SetupState;
  } catch (error) {
    console.error('Failed to load setup state:', error);
    clearSetupState();
    return null;
  }
}

/**
 * Clear setup state from localStorage
 */
export function clearSetupState(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to clear setup state:', error);
  }
}

/**
 * Update specific step data
 */
export function updateSetupStepData(step: keyof SetupState['data'], data: any): void {
  try {
    const currentState = loadSetupState();
    if (currentState) {
      currentState.data[step] = { ...currentState.data[step], ...data };
      saveSetupState(currentState);
    }
  } catch (error) {
    console.error('Failed to update setup step data:', error);
  }
}

/**
 * Update current step
 */
export function updateCurrentStep(step: SetupStep): void {
  try {
    const currentState = loadSetupState();
    if (currentState) {
      currentState.currentStep = step;
      saveSetupState(currentState);
    } else {
      // Create new state if none exists
      saveSetupState({
        currentStep: step,
        data: {},
        lastUpdated: new Date().toISOString(),
      });
    }
  } catch (error) {
    console.error('Failed to update current step:', error);
  }
}
