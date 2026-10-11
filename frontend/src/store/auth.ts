import { create } from 'zustand';

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  role: string | null;
  setRole: (role: string) => void;
  login: (token: string, role?: string) => void;
  logout: () => void;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  isAuthenticated: false,
  role: null,

  // Initialize auth state from localStorage on app load
  initialize: () => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    if (token) {
      set({ token, isAuthenticated: true, role });
    }
  },

  setRole: (role: string) => {
    localStorage.setItem('role', role);
    set({ role });
  },

  login: (token: string, role?: string) => {
    localStorage.setItem('token', token);
    if (role) {
      localStorage.setItem('role', role);
    }
    set({ token, isAuthenticated: true, role: role ?? null });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    set({ token: null, isAuthenticated: false, role: null });
  },
}));
