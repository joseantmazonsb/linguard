import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './contexts/ThemeContext'

console.log('[Linguard] bundle: relative-api v2 (2026-10-10 21:00)')

// Kill any orphaned service worker left by an older deployment — it can
// intercept XHRs and rewrite them to stale hardcoded API URLs. Linguard
// does not use a service worker, so unregistering everything is always safe.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (const registration of registrations) {
      registration.unregister();
      console.log('[Linguard] unregistered stale service worker:', registration.scope);
    }
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
)
