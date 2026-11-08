import { expect, test } from '@playwright/test';

for (const expired of [false, true]) {
  test(`should resume peer setup from server progress ${expired ? 'with expired storage' : 'in a new browser'}`, async ({ page }) => {
    let peerBody: any;
    await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'peer' } }));
    await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
    await page.route('**/api/v1/servers', route => {
      expect(route.request().headers().authorization).toBe('Bearer admin-token');
      return route.fulfill({ json: [{ id: 42, name: 'Existing VPN' }] });
    });
    await page.route('**/api/v1/setup/create-peer', route => {
      expect(route.request().headers().authorization).toBe('Bearer admin-token');
      peerBody = route.request().postDataJSON();
      return route.fulfill({ json: { success: true, peer_id: 7, peer_name: 'Laptop' } });
    });
    await page.route('**/api/v1/setup/complete', route => route.fulfill({ json: { success: true } }));
    if (expired) await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'account', lastUpdated: '2000-01-01T00:00:00Z', data: {} })));
    await page.goto('/setup');
    await page.getByRole('button', { name: 'Resume Setup' }).click();
    await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="password"]').fill('password123');
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Create First Peer' })).toBeVisible();
    await page.getByRole('button', { name: 'Create Peer' }).click();
    await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
    expect(peerBody.server_id).toBe(42);
  });
}

test('should use server progress instead of stale local progress', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'auth' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'account', lastUpdated: new Date().toISOString(), data: {} })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
});

test('should never reset on backdrop and require explicit confirmation', async ({ page }) => {
  let resets = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'account' } }));
  await page.route('**/api/v1/setup/reset', route => { resets++; return route.fulfill({ json: { success: true } }); });
  await page.goto('/setup');
  await expect(page.getByRole('heading', { name: 'Resume Setup?' })).toBeVisible();
  await page.mouse.click(5, 5);
  expect(resets).toBe(0);
  await page.getByRole('button', { name: 'Start Fresh' }).click();
  await expect(page.getByText('This will permanently delete')).toBeVisible();
  expect(resets).toBe(0);
  await page.getByRole('button', { name: 'Cancel' }).click();
  expect(resets).toBe(0);
  await page.getByRole('button', { name: 'Start Fresh' }).click();
  await page.getByRole('button', { name: 'Confirm Reset' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to Linguard' })).toBeVisible();
  expect(resets).toBe(1);
});

test('should require a server choice when resuming peer with multiple servers', async ({ page }) => {
  let peerBody: any;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'peer' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/servers', route => route.fulfill({ json: [{ id: 12, name: 'One' }, { id: 34, name: 'Two' }] }));
  await page.route('**/api/v1/setup/create-peer', route => { peerBody = route.request().postDataJSON(); return route.fulfill({ json: { success: true } }); });
  await page.route('**/api/v1/setup/complete', route => route.fulfill({ json: { success: true } }));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Create Peer' })).toBeDisabled();
  await page.getByRole('combobox', { name: 'Server' }).selectOption('34');
  await page.getByRole('button', { name: 'Create Peer' }).click();
  await expect.poll(() => peerBody?.server_id).toBe(34);
});

test('should not trust a stale browser server ID when resuming server peer progress', async ({ page }) => {
  let peerBody: any;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'peer' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/servers', route => route.fulfill({ json: [{ id: 42, name: 'Current server' }] }));
  await page.route('**/api/v1/setup/create-peer', route => { peerBody = route.request().postDataJSON(); return route.fulfill({ json: { success: true } }); });
  await page.route('**/api/v1/setup/complete', route => route.fulfill({ json: { success: true } }));
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'peer', lastUpdated: new Date().toISOString(), data: { serverId: 99 } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Create Peer' }).click();
  await expect.poll(() => peerBody?.server_id).toBe(42);
});

test('should allow explicit completion when peer progress has no server', async ({ page }) => {
  let completions = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'peer' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/servers', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/setup/complete', route => { completions++; return route.fulfill({ json: { success: true } }); });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('password123');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('No server was found');
  await expect(page.getByRole('button', { name: 'Create Peer' })).toBeDisabled();
  expect(completions).toBe(0);
  await page.getByRole('button', { name: 'Continue without server' }).click();
  await expect(page.getByRole('heading', { name: 'Setup Complete!' })).toBeVisible();
  expect(completions).toBe(1);
});

test('should reject unknown server progress rather than start fresh', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'unknown' } }));
  await page.goto('/setup');
  await expect(page.getByRole('alert')).toContainText('Unable to check setup status');
  await expect(page.getByRole('heading', { name: 'Welcome to Linguard' })).toBeHidden();
});
