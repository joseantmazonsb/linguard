import { expect, test, type Page } from '@playwright/test';

const profile = { id: 1, username: 'alice', email: 'alice@example.com', role: 'standard', auth_provider: 'local' };

async function setup(page: Page) {
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ json: profile }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: true, auth_mode: 'both', provider_name: 'Example' } }));
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('test-initialized')) {
      sessionStorage.setItem('test-initialized', '1');
      localStorage.setItem('token', 'original-token');
      localStorage.setItem('role', 'standard');
    }
  });
}

async function beginLink(page: Page, callbackState = 'expected-state') {
  await page.route('**/api/v1/auth/oidc/login', route => route.fulfill({ json: {
    authorization_url: `${new URL(page.url()).origin}/oidc-callback?code=example-code&state=${callbackState}`,
  } }));
  await page.goto('/profile');
  await page.getByRole('button', { name: 'Link Single Sign-On' }).click();
}

test('should link an authenticated account without persisting the password or replacing the session', async ({ page }) => {
  await setup(page);
  let linkRequest: { body: unknown; authorization: string | undefined } | undefined;
  await page.route('**/api/v1/auth/oidc/link', route => {
    linkRequest = { body: route.request().postDataJSON(), authorization: route.request().headers().authorization };
    return route.fulfill({ json: profile });
  });
  await beginLink(page);
  await page.getByLabel('Current password').fill('secret-password');
  expect(await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))).not.toContain('secret-password');
  await page.getByRole('button', { name: 'Confirm link' }).click();
  await expect(page.getByText('Single Sign-On account linked successfully')).toBeVisible();
  expect(linkRequest).toEqual({ body: { code: 'example-code', state: 'expected-state', password: 'secret-password' }, authorization: 'Bearer original-token' });
  expect(await page.evaluate(() => [localStorage.getItem('token'), localStorage.getItem('role')])).toEqual(['original-token', 'standard']);
});

test('should reject a callback state that does not match the initiated link', async ({ page }) => {
  await setup(page);
  let exchanges = 0;
  await page.route('**/api/v1/auth/oidc/link', route => { exchanges++; return route.fulfill({ json: profile }); });
  await page.route('**/api/v1/auth/oidc/callback', route => { exchanges++; return route.fulfill({ json: {} }); });
  await page.route('**/api/v1/auth/oidc/login', route => route.fulfill({ json: {
    authorization_url: `${new URL(page.url()).origin}/oidc-callback?code=example-code&state=expected-state`,
  } }));
  await page.goto('/profile');
  await page.getByRole('button', { name: 'Link Single Sign-On' }).click();
  await page.getByLabel('Current password').waitFor();
  await page.goto('/oidc-callback?code=attacker-code&state=wrong-state');
  await expect(page.getByText(/invalid or expired.*link/i)).toBeVisible();
  expect(exchanges).toBe(0);
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('original-token');
});

test('should preserve the session and require restarting after a failed link', async ({ page }) => {
  await setup(page);
  let calls = 0;
  await page.route('**/api/v1/auth/oidc/link', route => { calls++; return route.fulfill({ status: 401, json: { detail: 'Unable to link local account' } }); });
  await beginLink(page);
  await page.getByLabel('Current password').fill('wrong-password');
  await page.getByRole('button', { name: 'Confirm link' }).click();
  await expect(page.getByText('Unable to link local account')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Back to profile' })).toBeVisible();
  await expect(page.getByLabel('Current password')).toHaveCount(0);
  expect(calls).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('original-token');
});

test('should preserve ordinary OIDC login behavior without a link in progress', async ({ page }) => {
  await setup(page);
  await page.route('**/api/v1/auth/oidc/login', route => route.fulfill({ json: {
    authorization_url: `${new URL(page.url()).origin}/oidc-callback?code=login-code&state=login-state`,
  } }));
  await page.route('**/api/v1/auth/oidc/callback', route => route.fulfill({ json: { access_token: 'oidc-token', user: { role: 'admin' } } }));
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in with Example' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(await page.evaluate(() => [localStorage.getItem('token'), localStorage.getItem('role')])).toEqual(['oidc-token', 'admin']);
  expect(await page.evaluate(() => sessionStorage.getItem('oidc-login'))).toBeNull();
});

test('should reject unsolicited and mismatched login callbacks without replacing the session', async ({ page }) => {
  await setup(page);
  let exchanges = 0;
  await page.route('**/api/v1/auth/oidc/callback', route => { exchanges++; return route.fulfill({ json: { access_token: 'attacker' } }); });
  await page.goto('/oidc-callback?code=attacker&state=attacker-state');
  await expect(page.getByText(/invalid or expired.*sign-in/i)).toBeVisible();
  await page.evaluate(() => sessionStorage.setItem('oidc-login', 'expected-state'));
  await page.goto('/oidc-callback?code=attacker&state=attacker-state');
  await expect(page.getByText(/invalid or expired.*sign-in/i)).toBeVisible();
  expect(exchanges).toBe(0);
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('original-token');
});

test('should consume login state before exchange and reject replay and duplicate state', async ({ page }) => {
  await setup(page);
  let exchanges = 0;
  await page.route('**/api/v1/auth/oidc/callback', route => { exchanges++; return route.fulfill({ status: 401, json: { detail: 'Exchange failed' } }); });
  await page.goto('/login');
  await page.evaluate(() => sessionStorage.setItem('oidc-login', 'expected-state'));
  await page.goto('/oidc-callback?code=login-code&state=expected-state&state=attacker');
  await expect(page.getByText(/invalid or expired.*sign-in/i)).toBeVisible();
  expect(exchanges).toBe(0);
  await page.evaluate(() => sessionStorage.setItem('oidc-login', 'expected-state'));
  await page.goto('/oidc-callback?code=login-code&state=expected-state');
  await expect(page.getByText('Exchange failed')).toBeVisible();
  await page.goto('/oidc-callback?code=login-code&state=expected-state');
  await expect(page.getByText(/invalid or expired.*sign-in/i)).toBeVisible();
  expect(exchanges).toBe(1);
});

test('should refuse invalid authorization URLs before redirecting', async ({ page }) => {
  await setup(page);
  await page.route('**/api/v1/auth/oidc/login', route => route.fulfill({ json: { authorization_url: 'https://idp.example/authorize?state=a&state=b' } }));
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in with Example' }).click();
  await expect(page.getByText('Invalid Single Sign-On authorization URL.')).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('oidc-login'))).toBeNull();
  await expect(page).toHaveURL(/\/login$/);
});

test('should fail closed when session storage is unavailable', async ({ page }) => {
  await setup(page);
  await page.addInitScript(() => {
    Object.defineProperty(window, 'sessionStorage', { get() { throw new Error('Storage unavailable'); } });
  });
  let exchanges = 0;
  await page.route('**/api/v1/auth/oidc/callback', route => { exchanges++; return route.fulfill({ json: {} }); });
  await page.goto('/oidc-callback?code=code&state=state');
  await expect(page.getByText(/unable to verify your sign-in/i)).toBeVisible();
  expect(exchanges).toBe(0);
});

test('should consume matching login state on provider cancellation', async ({ page }) => {
  await setup(page);
  let exchanges = 0;
  await page.route('**/api/v1/auth/oidc/callback', route => { exchanges++; return route.fulfill({ json: {} }); });
  await page.goto('/login');
  await page.evaluate(() => sessionStorage.setItem('oidc-login', 'expected-state'));
  await page.goto('/oidc-callback?error=access_denied&state=expected-state');
  await expect(page.getByText('The identity provider refused the login attempt.')).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('oidc-login'))).toBeNull();
  expect(exchanges).toBe(0);
});

test('should reject a link if the authenticated account changes before confirmation', async ({ page }) => {
  await setup(page);
  let calls = 0;
  await page.route('**/api/v1/auth/oidc/link', route => { calls++; return route.fulfill({ json: profile }); });
  await beginLink(page);
  await page.getByLabel('Current password').fill('secret-password');
  await page.evaluate(() => localStorage.setItem('token', 'different-token'));
  await page.getByRole('button', { name: 'Confirm link' }).click();
  await expect(page.getByText('Your session changed. Please restart account linking.')).toBeVisible();
  expect(calls).toBe(0);
});

test('should show provider cancellation without signing out', async ({ page }) => {
  await setup(page);
  await beginLink(page);
  await page.getByLabel('Current password').waitFor();
  await page.goto('/oidc-callback?error=access_denied&state=expected-state');
  await expect(page.getByText('The identity provider refused account linking.')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('original-token');
  expect(await page.evaluate(() => sessionStorage.getItem('oidc-link'))).toBeNull();
});

test('should not offer linking when both modes are not enabled', async ({ page }) => {
  await setup(page);
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: true, auth_mode: 'oidc_only', provider_name: 'Example' } }));
  await page.goto('/profile');
  await expect(page.getByText('alice@example.com')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Link Single Sign-On' })).toHaveCount(0);
});

test('should explain how to link securely on an insecure HTTP origin', async ({ page }) => {
  await page.route('http://insecure.example/**', async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({ url: `http://localhost:5173${url.pathname}${url.search}` });
    await route.fulfill({ response });
  });
  await setup(page);
  let loginRequests = 0;
  await page.route('**/api/v1/auth/oidc/login', route => {
    loginRequests++;
    return route.fulfill({ json: {} });
  });
  await page.goto('http://insecure.example/profile');
  expect(await page.evaluate(() => [window.isSecureContext, !!window.crypto.subtle])).toEqual([false, false]);
  await page.evaluate(() => sessionStorage.setItem('oidc-link', 'stale'));
  await page.getByRole('button', { name: 'Link Single Sign-On' }).click();
  await expect(page.getByText(/account linking requires.*HTTPS.*localhost/i)).toBeVisible();
  expect(loginRequests).toBe(0);
  expect(await page.evaluate(() => [sessionStorage.getItem('oidc-link'), localStorage.getItem('token')])).toEqual([null, 'original-token']);
  await expect(page).toHaveURL('http://insecure.example/profile');
});

test('should explain when Web Crypto is unavailable in a secure context', async ({ page }) => {
  await setup(page);
  await page.addInitScript(() => Object.defineProperty(window.crypto, 'subtle', { value: undefined }));
  let loginRequests = 0;
  await page.route('**/api/v1/auth/oidc/login', route => {
    loginRequests++;
    return route.fulfill({ json: {} });
  });
  await page.goto('/profile');
  expect(await page.evaluate(() => window.isSecureContext)).toBe(true);
  await page.getByRole('button', { name: 'Link Single Sign-On' }).click();
  await expect(page.getByText(/account linking requires.*Web Crypto.*browser/i)).toBeVisible();
  expect(loginRequests).toBe(0);
});
