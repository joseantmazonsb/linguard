/**
 * Setup Storage Utility
 * Manages setup wizard state persistence in localStorage
 */

export type SetupStep = 'welcome' | 'database' | 'account' | 'globals' | 'server' | 'peer' | 'complete';

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

/**
 * Save current setup state to localStorage
 */
export function saveSetupState(state: SetupState): void {
  try {
    const stateToSave = {
      ...state,
      lastUpdated: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
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
    
    if (hoursDiff > 24) {
      // State is too old, clear it
      clearSetupState();
      return null;
    }

    return state;
  } catch (error) {
    console.error('Failed to load setup state:', error);
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
