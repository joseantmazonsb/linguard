import { test, expect } from '@playwright/test';

test('should complete setup using a newly signed admin token after globals change', async ({ page }) => {
  let initialized = false;
  let keyVersion = 0;
  let completed = false;
  const mutations: string[] = [];
  const issuedTokens: string[] = [];
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');
    if (path === '/setup/status') return route.fulfill({ json: { setup_completed: completed, requires_setup: !completed } });
    if (path === '/auth/token') {
      expect(request.postData()).toContain('password123');
      const token = `admin-key-${keyVersion}`;
      issuedTokens.push(token);
      return route.fulfill({ json: { access_token: token, user: { role: 'admin' } } });
    }
    if (path.startsWith('/setup/') && request.method() === 'POST') {
      mutations.push(path);
      if (initialized && request.headers().authorization !== `Bearer admin-key-${keyVersion}`) {
        return route.fulfill({ status: 401, json: { detail: 'Admin authentication required for setup.' } });
      }
      if (path === '/setup/initialize') initialized = true;
      if (path === '/setup/configure-globals') keyVersion++;
      if (path === '/setup/complete') completed = true;
      const response: Record<string, unknown> = { success: true };
      if (path === '/setup/initialize') Object.assign(response, { user_id: 1, username: 'admin' });
      if (path === '/setup/create-server') Object.assign(response, { server_id: 42, server_name: 'VPN' });
      if (path === '/setup/create-peer') Object.assign(response, { peer_id: 7, peer_name: 'Laptop' });
      return route.fulfill({ json: response });
    }
    return route.fulfill({ status: 404, json: {} });
  });

  await page.goto('/setup');
  await page.getByRole('button', { name: 'Get Started' }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="email"]').fill('admin@example.com');
  await page.locator('input[name="password"]').fill('password123');
  await page.locator('input[name="confirmPassword"]').fill('password123');
  await page.getByRole('button', { name: 'Create Account & Continue' }).click();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await page.getByRole('button', { name: 'Continue with Local Auth' }).click();
  await page.locator('input[name="endpoint"]').fill('vpn.example.com');
  await page.getByRole('button', { name: 'Create Server' }).click();
  await page.getByRole('button', { name: 'Create Peer' }).click();
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
  expect(mutations).toEqual(['/setup/configure-database', '/setup/initialize', '/setup/configure-globals', '/setup/configure-auth', '/setup/create-server', '/setup/create-peer', '/setup/complete']);
  expect(issuedTokens).toEqual(['admin-key-0', 'admin-key-1']);
  const storage = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
  expect(storage).not.toContain('password123');
});

test('should show a retry instead of success when setup completion fails', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ json: { role: 'admin' } }));
  await page.route('**/api/v1/setup/complete', route => ++attempts === 1
    ? route.fulfill({ status: 503, json: { detail: 'Cannot verify setup state.' } })
    : route.fulfill({ json: { success: true, backup_id: null } }));
  await page.addInitScript(() => {
    localStorage.setItem('token', 'admin-token');
    localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'complete', lastUpdated: new Date().toISOString(), data: { username: 'admin' } }));
  });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await expect(page.getByRole('alert')).toContainText('Failed to complete setup');
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeHidden();
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
  expect(attempts).toBe(2);
});

test('should explain why OIDC-only setup cannot use a local password', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ status: 403, json: { detail: 'Local password login is disabled (OIDC-only mode). Sign in with your identity provider.' } }));
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'server', lastUpdated: new Date().toISOString(), data: { username: 'admin', auth: { auth_mode: 'oidc_only' } } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Local password login is disabled');
});

test('should recover stranded OIDC-only setup before completing', async ({ page }) => {
  let localEnabled = false;
  let recoverAttempts = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/complete', route => localEnabled
    ? route.fulfill({ json: { success: true } })
    : route.fulfill({ status: 400, json: { detail: 'Enable local login before completing setup.' } }));
  await page.route('**/api/v1/setup/configure-auth', route => {
    expect(route.request().headers().authorization).toBe('Bearer admin-token');
    expect(route.request().postDataJSON().skip).toBe(true);
    if (++recoverAttempts === 1) return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    localEnabled = true;
    return route.fulfill({ json: { success: true, skipped: true } });
  });
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'complete', lastUpdated: new Date().toISOString(), data: { username: 'admin', auth: { auth_mode: 'oidc_only' } } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Enable local login before completing setup');
  await page.getByRole('button', { name: 'Enable local login' }).click();
  await expect(page.getByRole('alert')).toContainText('Failed to enable local login');
  await page.getByRole('button', { name: 'Enable local login' }).click();
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
});

test('should discard the old token if login after rotating the signing key is rejected', async ({ page }) => {
  let logins = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => ++logins === 1
    ? route.fulfill({ json: { access_token: 'old-token', user: { role: 'admin' } } })
    : route.fulfill({ status: 403, json: { detail: 'Login disabled' } }));
  await page.route('**/api/v1/setup/configure-globals', route => {
    expect(route.request().headers().authorization).toBe('Bearer old-token');
    return route.fulfill({ json: { success: true } });
  });
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
});

test('should request sign-in when the authenticated OIDC test expires', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ json: { role: 'admin' } }));
  await page.route('**/api/v1/auth/oidc/test', route => {
    expect(route.request().headers().authorization).toBe('Bearer expired-token');
    return route.fulfill({ status: 401, json: { detail: 'Expired token' } });
  });
  await page.addInitScript(() => {
    localStorage.setItem('token', 'expired-token');
    localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'auth', lastUpdated: new Date().toISOString(), data: { username: 'admin' } }));
  });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.getByRole('button', { name: 'Set up Single Sign-On (OIDC)' }).click();
  await page.locator('input[name="oidc_discovery_url"]').fill('https://idp.example.com');
  await page.locator('input[name="oidc_client_id"]').fill('client');
  await page.getByRole('button', { name: 'Test Connection' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  await expect(page).toHaveURL(/\/setup$/);
});
