import { test, expect } from '@playwright/test';

/**
 * Full setup workflow e2e test.
 *
 * Resets the backend (drops DB + deletes config) and walks through the entire
 * setup wizard via the UI: welcome → database → account → globals → auth →
 * server → peer → complete → dashboard.
 *
 * Requires the backend (:8000) and the vite dev server (:5173) to be running;
 * requests go through the vite proxy so no CORS is involved.
 */

test.describe('Full setup workflow', () => {
  test.beforeEach(async ({ request }) => {
    // Reset the backend to a clean, fresh-install state
    const response = await request.post('/api/v1/setup/reset');
    expect(response.ok()).toBeTruthy();
  });

  test('reset → full wizard → dashboard as admin', async ({ page }) => {
    test.setTimeout(120000);

    // Clear browser state (setup resume data, auth token/role) once, before
    // the wizard flow starts
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.reload({ waitUntil: 'domcontentloaded' });

    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Step 1: Welcome
    await expect(page.locator('h2')).toContainText('Welcome', { timeout: 15000 });
    await page.locator('button:has-text("Get Started")').click();

    // Step 2: Database (SQLite is the default selection)
    await expect(page.locator('h2')).toContainText('Choose Database', { timeout: 10000 });
    await page.locator('button[type="submit"]:has-text("Continue")').click();
    await expect(page.locator('h2')).not.toContainText('Choose Database', { timeout: 30000 });

    // Step 3: Account — creates the admin and auto-logs in
    await expect(page.locator('h2')).toContainText('Create Admin Account', { timeout: 15000 });
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="email"]').fill('admin@example.com');
    await page.locator('input[name="password"]').fill('testpassword123');
    await page.locator('input[name="confirmPassword"]').fill('testpassword123');
    await page.locator('button:has-text("Create Account & Continue")').click();

    // Step 4: Global settings (fields pre-filled)
    await expect(page.locator('h2')).toContainText('Settings', { timeout: 20000 });
    await page.locator('button:has-text("Save & Continue")').click();

    // Step 5: Authentication — skip OIDC, continue with local auth
    await expect(page.locator('h2')).toContainText('Authentication', { timeout: 20000 });
    await page.locator('button:has-text("Local authentication only")').click();
    await page.locator('button:has-text("Continue with Local Auth")').click();

    // Step 6: First server (WireGuard is available in this environment)
    await expect(page.locator('h2')).toContainText('Create First Server', { timeout: 20000 });
    await page.locator('input[name="endpoint"]').fill('vpn.example.com');
    await page.locator('input[name="listen_port"]').fill('51820');
    await page.locator('input[name="ipv4_address"]').fill('10.0.0.1/24');
    await page.locator('button:has-text("Create Server")').click();

    // Step 7: First peer
    await expect(page.locator('h2')).toContainText(/peer/i, { timeout: 30000 });
    await page.locator('input[name="name"]').fill('Test Client');
    await page.locator('button:has-text("Create Peer")').click();

    // Step 8: Completion
    await expect(page.locator('h2')).toContainText('Setup Complete!', { timeout: 30000 });
    await page.locator('button:has-text("Go to Dashboard")').click();

    // Lands on the dashboard, authenticated as admin
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });

    const role = await page.evaluate(() => localStorage.getItem('role'));
    expect(role).toBe('admin');
    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeTruthy();

    // Setup state is cleaned up after completion
    const setupState = await page.evaluate(() => localStorage.getItem('linguard_setup_state'));
    expect(setupState).toBeNull();
  });

  test('login page has no SSO button when local-only auth was chosen', async ({ page, request }) => {
    test.setTimeout(120000);

    // Run the full wizard via the API (faster than the UI for this check)
    await request.post('/api/v1/setup/configure-database', {
      data: { database_type: 'sqlite', database_url: './data/linguard.db' },
    });
    await request.post('/api/v1/setup/initialize', {
      data: { username: 'admin', email: 'admin@example.com', password: 'testpassword123' },
    });
    await request.post('/api/v1/setup/configure-globals', {
      data: {
        secret_key: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        backup_dir: './backups',
      },
    });
    await request.post('/api/v1/setup/configure-auth', { data: { skip: true } });
    await request.post('/api/v1/setup/update-progress', { data: { current_step: 'complete' } });
    await request.post('/api/v1/setup/complete');

    // The login page must NOT offer SSO in local-only mode
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('button:has-text("Sign in with")')).toHaveCount(0);
    await expect(page.locator('input[name="username"]')).toBeVisible();
  });
});
