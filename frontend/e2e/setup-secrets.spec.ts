import { test, expect } from '@playwright/test';

const key = 'linguard_setup_state';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/settings/backup-key', route => route.fulfill({ json: { configured: false } }));
});

test('should resume globals with re-entered credentials and reauthenticate after saving', async ({ page }) => {
  const logins: unknown[] = [];
  await page.route('**/api/v1/auth/token', async route => {
    logins.push(route.request().postData());
    await route.fulfill({ json: { access_token: 'token', user: { role: 'admin' } } });
  });
  await page.route('**/api/v1/setup/configure-globals', route => route.fulfill({ json: { success: true } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'globals', lastUpdated: new Date().toISOString(),
    data: { username: 'admin', password: 'legacy-password', serverId: 42 },
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await expect(page.locator('input[name="password"]')).toBeVisible();
  await page.locator('input[name="password"]').fill('new-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(logins).toHaveLength(2);
  expect(logins[0]).toContain('new-password');
  expect(logins[1]).toContain('new-password');
  const stored = await page.evaluate(key => localStorage.getItem(key), key);
  expect(stored).not.toContain('legacy-password');
  expect(stored).not.toContain('new-password');
  expect(JSON.parse(stored!).data.serverId).toBe(42);
});

test('should keep the admin password only in memory through global settings', async ({ page }) => {
  const logins: string[] = [];
  await page.route('**/api/v1/auth/token', async route => {
    logins.push(route.request().postData() ?? '');
    await route.fulfill({ json: { access_token: 'token', user: { role: 'admin' } } });
  });
  await page.route('**/api/v1/setup/initialize', route => route.fulfill({ json: { user_id: 1, username: 'admin' } }));
  await page.route('**/api/v1/setup/configure-globals', route => route.fulfill({ json: { success: true } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'account', lastUpdated: new Date().toISOString(), data: {},
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="email"]').fill('admin@example.com');
  await page.locator('input[name="password"]').fill('admin-password');
  await page.locator('input[name="confirmPassword"]').fill('admin-password');
  await page.getByRole('button', { name: 'Create Account & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  expect(await page.evaluate(key => localStorage.getItem(key), key)).not.toContain('admin-password');
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(logins).toHaveLength(2);
  expect(logins[1]).toContain('admin-password');
  const stored = await page.evaluate(key => localStorage.getItem(key), key);
  expect(stored).not.toContain('admin-password');
  expect(stored).not.toContain('secret_key');
  await page.getByRole('button', { name: 'Back' }).click();
  await expect(page.locator('input[name="username"]')).toHaveValue('admin');
});

test('should allow retrying invalid resume credentials without leaving the wizard', async ({ page }) => {
  await page.route('**/api/v1/auth/token', route => route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' },
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('wrong-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Unable to sign in');
  await expect(page).toHaveURL(/\/setup$/);
});

test('should submit OIDC secret without saving it and resume at the next step', async ({ page }) => {
  let submitted: any;
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ json: { role: 'admin' } }));
  await page.route('**/api/v1/setup/configure-auth', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ json: { success: true } });
  });
  await page.addInitScript(({ key }) => {
    if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify({
      currentStep: 'auth', lastUpdated: new Date().toISOString(), data: { username: 'admin' },
    }));
  }, { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Set up Single Sign-On (OIDC)' }).click();
  await page.locator('input[name="oidc_discovery_url"]').fill('https://idp.example.com');
  await page.locator('input[name="oidc_client_id"]').fill('client');
  await page.locator('input[name="oidc_client_secret"]').fill('oidc-secret');
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Create First Server' })).toBeVisible();
  expect(submitted.oidc_client_secret).toBe('oidc-secret');
  expect(await page.evaluate(key => localStorage.getItem(key), key)).not.toContain('oidc-secret');
  await page.reload();
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await expect(page.getByRole('heading', { name: 'Create First Server' })).toBeVisible();
});

test('should prompt for sign-in after a setup request rejects an expired token', async ({ page }) => {
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ json: { role: 'admin' } }));
  await page.route('**/api/v1/setup/create-server', route => route.fulfill({ status: 401, json: { detail: 'Expired token' } }));
  await page.addInitScript(({ key }) => {
    localStorage.setItem('token', 'expired-token');
    localStorage.setItem(key, JSON.stringify({ currentStep: 'server', lastUpdated: new Date().toISOString(), data: { username: 'admin' } }));
  }, { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="endpoint"]').fill('vpn.example.com');
  await page.getByRole('button', { name: 'Create Server' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('expired');
  await expect(page).toHaveURL(/\/setup$/);
});

test('should reject a non-admin login during setup resume', async ({ page }) => {
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'user-token', user: { role: 'standard' } } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'server', lastUpdated: new Date().toISOString(), data: { username: 'user' },
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('user-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('administrator');
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
});

test('should recover from a failed login after creating the account', async ({ page }) => {
  await page.route('**/api/v1/auth/token', route => route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } }));
  await page.route('**/api/v1/setup/initialize', route => route.fulfill({ json: { user_id: 1, username: 'admin' } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'account', lastUpdated: new Date().toISOString(), data: {},
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="email"]').fill('admin@example.com');
  await page.locator('input[name="password"]').fill('password123');
  await page.locator('input[name="confirmPassword"]').fill('password123');
  await page.getByRole('button', { name: 'Create Account & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  await expect(page).toHaveURL(/\/setup$/);
});

test('should stay in setup if reauthentication after changing the signing key fails', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/v1/auth/token', route => {
    attempts += 1;
    return attempts === 1
      ? route.fulfill({ json: { access_token: 'old-token', user: { role: 'admin' } } })
      : route.fulfill({ status: 401, json: { detail: 'Login failed' } });
  });
  await page.route('**/api/v1/setup/configure-globals', route => route.fulfill({ json: { success: true } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' },
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  await expect(page).toHaveURL(/\/setup$/);
});

test('should send the current admin token to all setup mutations after account creation', async ({ page }) => {
  let logins = 0;
  const authorizations: Record<string, string> = {};
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: ++logins === 1 ? 'before-key-change' : 'after-key-change', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/initialize', route => route.fulfill({ json: { user_id: 1, username: 'admin' } }));
  await page.route('**/api/v1/setup/configure-globals', route => {
    authorizations.globals = route.request().headers().authorization;
    return route.fulfill({ json: { success: true } });
  });
  await page.route('**/api/v1/setup/configure-auth', route => {
    authorizations.auth = route.request().headers().authorization;
    return route.fulfill({ json: { success: true } });
  });
  await page.route('**/api/v1/setup/create-server', route => {
    authorizations.server = route.request().headers().authorization;
    return route.fulfill({ json: { server_id: 42, server_name: 'VPN' } });
  });
  await page.route('**/api/v1/setup/create-peer', route => {
    authorizations.peer = route.request().headers().authorization;
    return route.fulfill({ json: { peer_id: 1, peer_name: 'Laptop' } });
  });
  await page.route('**/api/v1/setup/complete', route => {
    authorizations.complete = route.request().headers().authorization;
    return route.fulfill({ json: { success: true } });
  });
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'account', lastUpdated: new Date().toISOString(), data: {},
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="email"]').fill('admin@example.com');
  await page.locator('input[name="password"]').fill('password123');
  await page.locator('input[name="confirmPassword"]').fill('password123');
  await page.getByRole('button', { name: 'Create Account & Continue' }).click();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await page.getByRole('button', { name: 'Set up Single Sign-On (OIDC)' }).click();
  await expect(page.locator('select[name="auth_mode_select"] option[value="oidc_only"]')).toBeDisabled();
  await expect(page.getByText('OIDC-only mode can be enabled after setup')).toBeVisible();
  await page.locator('input[name="oidc_discovery_url"]').fill('https://idp.example.com');
  await page.locator('input[name="oidc_client_id"]').fill('client');
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await page.locator('input[name="endpoint"]').fill('vpn.example.com');
  await page.getByRole('button', { name: 'Create Server' }).click();
  await page.getByRole('button', { name: 'Create Peer' }).click();
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
  expect(authorizations).toEqual({
    globals: 'Bearer before-key-change', auth: 'Bearer after-key-change',
    server: 'Bearer after-key-change', peer: 'Bearer after-key-change', complete: 'Bearer after-key-change',
  });
});

test('should clean legacy setup secrets even when setup is already complete', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'complete', lastUpdated: new Date().toISOString(), data: { password: 'legacy-password', auth: { oidc_client_secret: 'legacy-secret' } },
  })), { key });
  await page.goto('/login');
  await expect.poll(() => page.evaluate(key => localStorage.getItem(key), key)).toBeNull();
});

test('should require admin authentication before resuming protected steps and send the bearer token', async ({ page }) => {
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'fresh-admin-token', user: { role: 'admin' } } }));
  let authorization = '';
  await page.route('**/api/v1/setup/create-server', async route => {
    authorization = route.request().headers().authorization ?? '';
    await route.fulfill({ json: { server_id: 42, server_name: 'VPN' } });
  });
  await page.addInitScript(({ key }) => localStorage.setItem(key, JSON.stringify({
    currentStep: 'server', lastUpdated: new Date().toISOString(), data: { username: 'admin', auth: { auth_mode: 'oidc_only' } },
  })), { key });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.locator('input[name="endpoint"]').fill('vpn.example.com');
  await page.getByRole('button', { name: 'Create Server' }).click();
  await expect(page.getByRole('heading', { name: 'Create First Peer' })).toBeVisible();
  expect(authorization).toBe('Bearer fresh-admin-token');
});
