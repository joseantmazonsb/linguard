import { expect, test } from '@playwright/test';

test('should keep invalid login errors on the login page', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ status: 401, json: { detail: 'Incorrect username or password' } }));
  await page.goto('/login');
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('wrong');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Incorrect username or password')).toBeVisible();
  await expect(page.getByLabel('Username')).toHaveValue('admin');
});

test('should deny admin pages when the stored role is missing', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.addInitScript(() => localStorage.setItem('token', 'token-with-unknown-role'));
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/forbidden$/);
});

test('should clear a previous role when a new login omits its role', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'new-token', user: {} } }));
  await page.addInitScript(() => { localStorage.setItem('token', 'old-token'); localStorage.setItem('role', 'admin'); });
  await page.goto('/login');
  await page.getByLabel('Username').fill('user');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/forbidden$/);
  expect(await page.evaluate(() => localStorage.getItem('role'))).toBeNull();
});

test('should sign out when the current session is rejected', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.route('**/api/v1/auth/profile', route => route.fulfill({ status: 401, json: { detail: 'Expired' } }));
  await page.addInitScript(() => { if (!sessionStorage.getItem('initialized')) { sessionStorage.setItem('initialized', 'yes'); localStorage.setItem('token', 'expired'); localStorage.setItem('role', 'admin'); } });
  await page.goto('/profile');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel('Username')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
});

test('should retry an unavailable setup status without entering setup', async ({ page }) => {
  let available = false;
  await page.route('**/api/v1/setup/status', route => !available
    ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } })
    : route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.goto('/login');
  await expect(page.getByRole('alert')).toContainText('Unable to check setup status');
  await expect(page.getByRole('heading', { name: 'Welcome to Linguard' })).toBeHidden();
  available = true;
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByLabel('Username')).toBeVisible();
});

test('should clear cached profile data on logout and login as another user', async ({ page }) => {
  let allowSecondProfile: () => void = () => {};
  const secondProfile = new Promise<void>(resolve => { allowSecondProfile = resolve; });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'second-token', user: { role: 'standard' } } }));
  await page.route('**/api/v1/auth/profile', async route => {
    const second = route.request().headers().authorization === 'Bearer second-token';
    if (second) await secondProfile;
    await route.fulfill({ json: { username: second ? 'second-user' : 'first-user', email: second ? 'second@example.com' : 'first@example.com', role: 'standard' } });
  });
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('initialized')) {
      sessionStorage.setItem('initialized', 'yes');
      localStorage.setItem('token', 'first-token');
      localStorage.setItem('role', 'standard');
    }
  });
  await page.goto('/profile');
  await expect(page.getByText('first@example.com')).toBeVisible();
  await page.getByRole('button', { name: /account|user menu/i }).first().click();
  await page.getByRole('button', { name: 'Logout' }).first().click();
  await page.getByLabel('Username').fill('second-user');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Go to profile' }).click();
  await expect(page.getByText('Loading profile...')).toBeVisible();
  await expect(page.getByText('first@example.com')).toBeHidden();
  allowSecondProfile();
  await expect(page.getByText('second@example.com')).toBeVisible();
});

test('should remove cached data when switching tokens without logging out', async ({ page }) => {
  let release: () => void = () => {};
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: true, requires_setup: false } }));
  await page.route('**/api/v1/auth/oidc/config', route => route.fulfill({ json: { oidc_enabled: false, auth_mode: 'both' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'second-token', user: { role: 'standard' } } }));
  await page.route('**/api/v1/auth/profile', async route => {
    const second = route.request().headers().authorization === 'Bearer second-token';
    if (second) await pending;
    return route.fulfill({ json: { username: second ? 'second' : 'first', email: second ? 'second@example.com' : 'first@example.com', role: 'standard' } });
  });
  await page.addInitScript(() => { if (!sessionStorage.getItem('initialized')) { sessionStorage.setItem('initialized', 'yes'); localStorage.setItem('token', 'first-token'); localStorage.setItem('role', 'standard'); } });
  await page.goto('/profile');
  await expect(page.getByText('first@example.com')).toBeVisible();
  await page.evaluate(() => { history.pushState({}, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate')); });
  await page.getByLabel('Username').fill('second');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Go to profile' }).click();
  await expect(page.getByText('Loading profile...')).toBeVisible();
  await expect(page.getByText('first@example.com')).toBeHidden();
  release();
  await expect(page.getByText('second@example.com')).toBeVisible();
});
