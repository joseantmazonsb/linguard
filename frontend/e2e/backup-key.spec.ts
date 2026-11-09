import { test, expect, type Page } from '@playwright/test';

const secret = 'backup-key-not-for-storage';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/settings/backup-key', route => route.fulfill({ json: { configured: false } }));
});

async function mockApp(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'admin-token');
    localStorage.setItem('role', 'admin');
  });
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/setup/status')) return route.fulfill({ json: { setup_completed: true, requires_setup: false } });
    if (path.endsWith('/settings/global')) return route.fulfill({ json: { id: 1 } });
    if (path.endsWith('/backups')) return route.fulfill({ json: [{ id: 1, filename: 'encrypted.json', file_size: 10, is_encrypted: true, is_legacy_unauthenticated: false, created_by_username: 'admin', created_at: '2026-01-01' }] });
    return route.fulfill({ json: {} });
  });
}

async function expectNoSecret(page: Page) {
  expect(await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))).not.toContain(secret);
}

test('should save the setup key before rotating authentication without persisting it', async ({ page }) => {
  let logins = 0;
  let authorization = '';
  const operations: string[] = [];
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: ++logins === 1 ? 'old' : 'new', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/configure-globals', route => {
    operations.push('globals');
    expect(route.request().postData()).not.toContain(secret);
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/v1/settings/backup-key', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { configured: false } });
    operations.push('backup-key');
    authorization = route.request().headers().authorization;
    expect(route.request().postDataJSON()).toEqual({ key: secret });
    return route.fulfill({ json: { configured: true } });
  });
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  const field = page.getByLabel('Backup encryption key (optional)');
  await expect(field).toHaveAttribute('type', 'password');
  await field.fill(secret);
  await expectNoSecret(page);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(authorization).toBe('Bearer old');
  expect(operations).toEqual(['backup-key', 'globals']);
  await expectNoSecret(page);
});

test('should replace and clear the configured key explicitly', async ({ page }) => {
  await mockApp(page);
  let configured = false;
  const methods: string[] = [];
  await page.route('**/api/v1/settings/backup-key', route => {
    const method = route.request().method();
    methods.push(method);
    if (method === 'PUT') {
      expect(route.request().postDataJSON()).toEqual({ key: secret });
      configured = true;
    }
    if (method === 'DELETE') configured = false;
    return route.fulfill({ json: { configured } });
  });
  await page.goto('/settings');
  await expect(page.getByText('Backup key not configured')).toBeVisible();
  await expect(page.getByText(/Unencrypted backups expose secrets/)).toBeVisible();
  const field = page.getByLabel('Backup encryption key (optional)');
  await expect(field).toHaveAttribute('type', 'password');
  await field.fill(secret);
  await expectNoSecret(page);
  await page.getByRole('button', { name: 'Save backup key' }).click();
  await expect(page.getByText('Backup key configured', { exact: true })).toBeVisible();
  await expect(field).toHaveValue('');
  await expect(page.getByText(/Keep old keys/)).toBeVisible();
  await field.fill(secret);
  await page.getByRole('button', { name: 'Replace backup key' }).click();
  await expect(page.getByText('Existing backups still require their original key.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm replace key' }).click();
  await expect(field).toHaveValue('');
  await page.getByRole('button', { name: 'Clear backup key' }).click();
  await expect(page.getByText(/Future backups will be unencrypted/)).toBeVisible();
  await page.getByRole('button', { name: 'Confirm clear key' }).click();
  await expect(page.getByText('Backup key not configured')).toBeVisible();
  expect(methods).toContain('PUT');
  expect(methods).toContain('DELETE');
  await expectNoSecret(page);
});

test('should retry an encrypted restore with the original key in JSON only', async ({ page }) => {
  await mockApp(page);
  const consoleMessages: string[] = [];
  page.on('console', message => consoleMessages.push(message.text()));
  const attempts: unknown[] = [];
  await page.route('**/api/v1/backups/1/restore*', route => {
    expect(new URL(route.request().url()).search).toBe('');
    attempts.push(route.request().postDataJSON());
    return attempts.length < 3
      ? route.fulfill({ status: 400, json: { detail: 'Invalid passphrase or encrypted backup' } })
      : route.fulfill({ json: { success: true } });
  });
  await page.goto('/backup');
  await expect(page.getByText('Encrypted', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  const field = page.getByLabel('Original backup key');
  await expect(field).toHaveAttribute('type', 'password');
  await expect(page.getByRole('button', { name: 'Confirm legacy restore' })).toHaveCount(0);
  await field.fill(secret);
  await expectNoSecret(page);
  await page.getByRole('button', { name: 'Retry Restore' }).click();
  await expect(field).toHaveValue('');
  await field.fill(secret);
  await page.getByRole('button', { name: 'Retry Restore' }).click();
  await expect(page.getByText('Backup restored successfully!')).toBeVisible();
  expect(attempts).toEqual([{ overwrite: true }, { overwrite: true, passphrase: secret }, { overwrite: true, passphrase: secret }]);
  await expectNoSecret(page);
  expect(consoleMessages.join('\n')).not.toContain(secret);
});

test('should require a separate confirmation before restoring a legacy backup', async ({ page }) => {
  await mockApp(page);
  const attempts: unknown[] = [];
  await page.route('**/api/v1/backups/1/restore*', route => {
    expect(new URL(route.request().url()).search).toBe('');
    attempts.push(route.request().postDataJSON());
    return attempts.length < 3
      ? route.fulfill({ status: 400, json: { detail: 'Legacy unauthenticated backup requires explicit opt-in' } })
      : route.fulfill({ json: { success: true } });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Restore Legacy Backup?' })).toBeVisible();
  await expect(page.getByText(/not encryption.*integrity cannot be verified/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Yes, Restore Backup' })).toHaveCount(0);
  expect(attempts).toEqual([{ overwrite: true }]);
  await page.getByRole('button', { name: 'Cancel legacy restore' }).click();
  await expect(page.getByRole('heading', { name: 'Restore Legacy Backup?' })).toHaveCount(0);
  expect(attempts).toHaveLength(1);
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Restore Legacy Backup?' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm legacy restore' }).click();
  await expect(page.getByText('Backup restored successfully!')).toBeVisible();
  expect(attempts).toEqual([{ overwrite: true }, { overwrite: true }, { overwrite: true, allow_legacy_unauthenticated: true }]);
});

test('should not offer legacy confirmation for other backend errors', async ({ page }) => {
  await mockApp(page);
  let detail = 'Passphrase required for encrypted backup';
  await page.route('**/api/v1/backups/1/restore', route => route.fulfill({ status: 400, json: { detail } }));
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByLabel('Original backup key')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirm legacy restore' })).toHaveCount(0);
  detail = 'Invalid passphrase or encrypted backup';
  await page.getByLabel('Original backup key').fill(secret);
  await page.getByRole('button', { name: 'Retry Restore' }).click();
  await expect(page.getByLabel('Original backup key')).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Confirm legacy restore' })).toHaveCount(0);
});

test('should require fresh consent after a failed legacy restore', async ({ page }) => {
  await mockApp(page);
  const attempts: unknown[] = [];
  await page.route('**/api/v1/backups/1/restore', route => {
    attempts.push(route.request().postDataJSON());
    return attempts.length === 2
      ? route.fulfill({ status: 400, json: { detail: 'Invalid legacy backup format' } })
      : route.fulfill({ status: 400, json: { detail: 'Legacy unauthenticated backup requires explicit opt-in' } });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await page.getByRole('button', { name: 'Confirm legacy restore' }).click();
  await expect(page.getByText('Invalid legacy backup format')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Yes, Restore Backup' })).toBeVisible();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Restore Legacy Backup?' })).toBeVisible();
  expect(attempts).toEqual([{ overwrite: true }, { overwrite: true, allow_legacy_unauthenticated: true }, { overwrite: true }]);
});

test('should restore an encrypted backup using the configured server key without prompting', async ({ page }) => {
  await mockApp(page);
  let body: unknown;
  await page.route('**/api/v1/backups/1/restore', route => {
    body = route.request().postDataJSON();
    return route.fulfill({ json: {} });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByText('Backup restored successfully!')).toBeVisible();
  expect(body).toEqual({ overwrite: true });
  await expect(page.getByLabel('Original backup key')).toHaveCount(0);
});

test('should save the setup key even when reauthentication after globals fails', async ({ page }) => {
  let logins = 0;
  let keyRequests = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => ++logins === 2
    ? route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } })
    : route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/configure-globals', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/settings/backup-key', route => { if (route.request().method() === 'GET') return route.fulfill({ json: { configured: false } }); keyRequests++; return route.fulfill({ json: {} }); });
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to continue setup' })).toBeVisible();
  expect(keyRequests).toBe(1);
  await expectNoSecret(page);
});

test('should import encrypted JSON and not prompt for a key for unrelated restore errors', async ({ page }) => {
  await mockApp(page);
  let uploaded = false;
  await page.route('**/api/v1/backups/upload', route => {
    uploaded = route.request().postData()?.includes('encrypted.json') ?? false;
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/v1/backups/1/restore', route => route.fulfill({ status: 400, json: { detail: 'Invalid decrypted backup format' } }));
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.locator('input[type="file"]')).toHaveAttribute('accept', /\.json/);
  await page.locator('input[type="file"]').setInputFiles({ name: 'encrypted.json', mimeType: 'application/json', buffer: Buffer.from('{"format":"encrypted"}') });
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.getByText('Backup imported successfully!')).toBeVisible();
  expect(uploaded).toBe(true);
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByText('Invalid decrypted backup format')).toBeVisible();
  await expect(page.getByLabel('Original backup key')).toHaveCount(0);
});

test('should preserve the configured OIDC secret unless a replacement is entered', async ({ page }) => {
  await mockApp(page);
  let submissions: any[] = [];
  await page.route('**/api/v1/settings/global', route => {
    if (route.request().method() === 'PUT') {
      submissions.push(route.request().postDataJSON());
    }
    return route.fulfill({ json: { id: 1, auth_mode: 'both', oidc_client_secret_configured: true } });
  });
  await page.goto('/settings');
  await expect(page.getByText('Client secret configured')).toBeVisible();
  await page.getByRole('button', { name: 'Edit Settings' }).click();
  const field = page.getByLabel('Client Secret', { exact: true });
  await field.fill('temporary');
  await field.clear();
  await page.getByRole('button', { name: 'Save Settings' }).click();
  await expect.poll(() => submissions.length).toBe(1);
  expect(submissions[0]).not.toHaveProperty('oidc_client_secret');
  await page.getByRole('button', { name: 'Edit Settings' }).click();
  await field.fill('replacement-secret');
  await page.getByRole('button', { name: 'Save Settings' }).click();
  await expect.poll(() => submissions.length).toBe(2);
  expect(submissions[1].oidc_client_secret).toBe('replacement-secret');
});

test('should recover a missing backup key through the recovery endpoint', async ({ page }) => {
  await mockApp(page);
  let recovered = false;
  await page.route('**/api/v1/settings/backup-key**', route => {
    if (route.request().method() === 'PUT') {
      expect(new URL(route.request().url()).pathname).toBe('/api/v1/settings/backup-key/recover');
      expect(route.request().postDataJSON()).toEqual({ key: secret });
      recovered = true;
      return route.fulfill({ json: { configured: true } });
    }
    return route.fulfill({ json: recovered ? { configured: true } : { configured: true, status: 'missing' } });
  });
  await page.goto('/settings');
  await expect(page.getByText('Backup key missing', { exact: true })).toBeVisible();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Recover backup key' }).click();
  await page.getByRole('button', { name: 'Confirm recover key' }).click();
  await expect(page.getByText('Backup key configured', { exact: true })).toBeVisible();
  await expectNoSecret(page);
});

test('should explain unsafe key status without offering blind recovery', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/settings/backup-key', route => route.fulfill({ status: 503, json: { detail: 'Cannot read backup key file' } }));
  await page.goto('/settings');
  await expect(page.getByText(/local operator must repair/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Recover backup key' })).toHaveCount(0);
});

test('should explain an unsafe key operation without exposing backend details', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/settings/backup-key', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { configured: true, status: 'missing' } })
    : route.fulfill({ status: 503, json: { detail: `unsafe ${secret}` } }));
  await page.route('**/api/v1/settings/backup-key/recover', route => route.fulfill({ status: 503, json: { detail: `unsafe ${secret}` } }));
  await page.goto('/settings');
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Recover backup key' }).click();
  await page.getByRole('button', { name: 'Confirm recover key' }).click();
  await expect(page.getByText(/local operator must inspect and repair/)).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);
});

test('should block setup when backup key status is unsafe', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'globals' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/settings/backup-key', route => route.fulfill({ status: 503, json: { detail: 'Cannot read backup key file' } }));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText(/local operator must repair/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeDisabled();
});

test('should explicitly clear an OIDC client secret', async ({ page }) => {
  await mockApp(page);
  let submitted: any;
  await page.route('**/api/v1/settings/global', route => {
    if (route.request().method() === 'PUT') submitted = route.request().postDataJSON();
    return route.fulfill({ json: { id: 1, auth_mode: 'both', oidc_client_secret_configured: true } });
  });
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Edit Settings' }).click();
  await page.getByLabel('Clear client secret').check();
  await page.getByRole('button', { name: 'Save Settings' }).click();
  await expect.poll(() => submitted).toBeTruthy();
  expect(submitted.oidc_client_secret).toBeNull();
});

test('should label legacy backups as not encrypted', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/backups', route => route.fulfill({ json: [{ id: 1, filename: 'old.json', file_size: 10, is_encrypted: false, is_legacy_unauthenticated: true, created_by_username: 'admin', created_at: '2026-01-01' }] }));
  await page.goto('/backup');
  await expect(page.getByText('Legacy (not encrypted)')).toBeVisible();
  await page.route('**/api/v1/backups/1/restore', route => route.fulfill({ status: 400, json: { detail: 'Legacy unauthenticated backup requires explicit opt-in' } }));
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Restore Legacy Backup?' })).toBeVisible();
});

test('should allow a manual key for a backup with unknown encryption status', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/backups', route => route.fulfill({ json: [{ id: 1, filename: 'old.json', file_size: 10, is_encrypted: null, is_legacy_unauthenticated: false, created_by_username: 'admin', created_at: '2026-01-01' }] }));
  await page.goto('/backup');
  await expect(page.getByText('Encryption status unknown')).toBeVisible();
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Use original backup key' }).click();
  await expect(page.getByLabel('Original backup key')).toBeVisible();
});

test('should label unverified encrypted format and retry restore with the original key', async ({ page }) => {
  await mockApp(page);
  const attempts: unknown[] = [];
  await page.route('**/api/v1/backups', route => route.fulfill({ json: [{ id: 1, filename: 'backup.json', file_size: 10, is_encrypted: null, is_encrypted_format: true, is_legacy_unauthenticated: false, created_by_username: 'admin', created_at: '2026-01-01' }] }));
  await page.route('**/api/v1/backups/1/restore', route => {
    attempts.push(route.request().postDataJSON());
    return attempts.length === 1 ? route.fulfill({ status: 400, json: { detail: 'Invalid passphrase or encrypted backup' } }) : route.fulfill({ json: {} });
  });
  await page.goto('/backup');
  await expect(page.getByText('Encrypted format (unverified)')).toBeVisible();
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await page.getByLabel('Original backup key').fill(secret);
  await page.getByRole('button', { name: 'Retry Restore' }).click();
  await expect(page.getByText('Backup restored successfully!')).toBeVisible();
  expect(attempts).toEqual([{ overwrite: true }, { overwrite: true, passphrase: secret }]);
  await expectNoSecret(page);
});

for (const action of ['keep', 'replace', 'delete'] as const) {
  test(`should explicitly ${action} a configured setup key before globals`, async ({ page }) => {
    const calls: string[] = [];
    await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'globals' } }));
    await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
    await page.route('**/api/v1/settings/backup-key', route => {
      if (route.request().method() === 'GET') return route.fulfill({ json: { configured: true } });
      calls.push(route.request().method());
      return route.fulfill({ json: { configured: action !== 'delete' } });
    });
    await page.route('**/api/v1/setup/configure-globals', route => { calls.push('globals'); return route.fulfill({ json: {} }); });
    await page.goto('/setup');
    await page.getByRole('button', { name: 'Resume Setup' }).click();
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="password"]').fill('admin-password');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByText('Backup key configured', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeDisabled();
    await page.getByLabel(action === 'keep' ? 'Keep current key' : action === 'replace' ? 'Replace current key' : 'Delete backup key').check();
    if (action === 'replace') await page.getByLabel('Backup encryption key (optional)').fill(secret);
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
    expect(calls).toEqual(action === 'keep' ? ['globals'] : [action === 'delete' ? 'DELETE' : 'PUT', 'globals']);
    await expectNoSecret(page);
  });
}

test('should require a choice for a retained setup key and recover a missing key before globals', async ({ page }) => {
  let status = 'missing';
  const operations: string[] = [];
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'globals' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/settings/backup-key**', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: status === 'missing' ? { configured: true, status } : { configured: true } });
    expect(new URL(route.request().url()).pathname).toBe('/api/v1/settings/backup-key/recover');
    operations.push('recover');
    status = 'configured';
    return route.fulfill({ json: { configured: true } });
  });
  await page.route('**/api/v1/setup/configure-globals', route => { operations.push('globals'); return route.fulfill({ json: {} }); });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText('Backup key missing', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeDisabled();
  await page.getByLabel('Recover missing key').check();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(operations).toEqual(['recover', 'globals']);
  await expectNoSecret(page);
});

test('should manually restore with an original key after a server error', async ({ page }) => {
  await mockApp(page);
  const attempts: unknown[] = [];
  await page.route('**/api/v1/backups/1/restore', route => {
    attempts.push(route.request().postDataJSON());
    return attempts.length === 1 ? route.fulfill({ status: 500, json: { detail: 'Failed to restore backup: Cannot read backup key file' } }) : route.fulfill({ json: {} });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await page.locator('form').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, Restore Backup' }).click();
  await expect(page.getByText('Failed to restore backup: Cannot read backup key file')).toBeVisible();
  await expect(page.getByLabel('Original backup key')).toHaveCount(0);
  await page.getByRole('button', { name: 'Use original backup key' }).click();
  await page.getByLabel('Original backup key').fill(secret);
  await page.getByRole('button', { name: 'Retry Restore' }).click();
  await expect(page.getByText('Backup restored successfully!')).toBeVisible();
  expect(attempts).toEqual([{ overwrite: true }, { overwrite: true, passphrase: secret }]);
  await expectNoSecret(page);
});

test('should require separate confirmation to upload a legacy backup', async ({ page }) => {
  await mockApp(page);
  const bodies: string[] = [];
  await page.route('**/api/v1/backups/upload', route => {
    bodies.push(route.request().postData() ?? '');
    return route.fulfill({ json: {} });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.locator('input[type="file"]')).toHaveAttribute('accept', /\.enc/);
  await page.locator('input[type="file"]').setInputFiles({ name: 'old.enc', mimeType: 'text/plain', buffer: Buffer.from('eyJ2ZXJzaW9uIjoiMS4wIn0=') });
  await page.getByLabel('Import legacy base64 backup').check();
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Import Legacy Backup?' })).toBeVisible();
  await expect(page.locator('form').getByRole('button', { name: 'Import Backup', includeHidden: true })).toBeHidden();
  await expect(page.getByText(/not encryption.*integrity cannot be verified/i)).toBeVisible();
  expect(bodies).toHaveLength(0);
  await page.getByRole('button', { name: 'Cancel legacy import' }).click();
  expect(bodies).toHaveLength(0);
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await page.getByRole('button', { name: 'Confirm legacy import' }).click();
  await expect(page.getByText('Backup imported successfully!')).toBeVisible();
  expect(bodies[0]).toContain('name="allow_legacy_unauthenticated"');
  expect(bodies[0]).toContain('true');
});

test('should send no legacy opt-in for normal imports', async ({ page }) => {
  await mockApp(page);
  let body = '';
  await page.route('**/api/v1/backups/upload', route => {
    body = route.request().postData() ?? '';
    return route.fulfill({ json: {} });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Import Backup' }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: 'backup.json', mimeType: 'application/json', buffer: Buffer.from('{"version":"1.0"}') });
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.getByText('Backup imported successfully!')).toBeVisible();
  expect(body).not.toContain('allow_legacy_unauthenticated');
});

test('should require new confirmation if legacy upload fails', async ({ page }) => {
  await mockApp(page);
  let calls = 0;
  await page.route('**/api/v1/backups/upload', route => {
    calls++;
    return route.fulfill({ status: 400, json: { detail: 'Invalid legacy backup format' } });
  });
  await page.goto('/backup');
  await page.getByRole('button', { name: 'Import Backup' }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: 'old.enc', mimeType: 'text/plain', buffer: Buffer.from('broken') });
  await page.getByLabel('Import legacy base64 backup').check();
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await page.getByRole('button', { name: 'Confirm legacy import' }).click();
  await expect(page.getByText('Invalid legacy backup format')).toBeVisible();
  expect(calls).toBe(1);
  await page.locator('form').getByRole('button', { name: 'Import Backup' }).click();
  await expect(page.getByRole('heading', { name: 'Import Legacy Backup?' })).toBeVisible();
  expect(calls).toBe(1);
});

test('should keep setup retryable when saving the key fails', async ({ page }) => {
  let attempts = 0;
  let globals = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/configure-globals', route => { globals++; return route.fulfill({ json: {} }); });
  await page.route('**/api/v1/settings/backup-key', route => route.request().method() === 'GET' ? route.fulfill({ json: { configured: false } }) : ++attempts === 1
    ? route.fulfill({ status: 500, json: { detail: 'Unavailable' } })
    : route.fulfill({ json: { configured: true } }));
  await page.addInitScript(() => localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } })));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Failed to save backup key');
  expect(globals).toBe(0);
  await expectNoSecret(page);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(globals).toBe(1);
  expect(attempts).toBe(2);
});

test('should resume at globals after a key save failure and require a decision after reload', async ({ page }) => {
  let step = 'globals';
  let configured = false;
  let fail = true;
  let globals = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: step } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/setup/configure-globals', route => { globals++; step = 'auth'; return route.fulfill({ json: {} }); });
  await page.route('**/api/v1/settings/backup-key', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { configured } });
    if (fail) return route.fulfill({ status: 400, json: { detail: 'Backup key is too long' } });
    configured = true;
    return route.fulfill({ json: { configured } });
  });
  await page.addInitScript(() => {
    if (!localStorage.getItem('linguard_setup_state')) localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } }));
  });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Backup key is too long');
  expect(step).toBe('globals');
  expect(globals).toBe(0);
  await expectNoSecret(page);
  await page.reload();
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText(/previously entered backup key was not confirmed/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeDisabled();
  fail = false;
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(configured).toBe(true);
  expect(step).toBe('auth');
  await expectNoSecret(page);
});

test('should show safe key validation errors without revealing server supplied secrets', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/settings/backup-key', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { configured: false } })
    : route.fulfill({ status: 400, json: { detail: `Invalid key ${secret}` } }));
  await page.goto('/settings');
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save backup key' }).click();
  await expect(page.getByText('Failed to save backup key')).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);
});

test('should retain saved key status after globals fails and setup reloads', async ({ page }) => {
  let step = 'globals';
  let keyWrites = 0;
  let globals = 0;
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: step } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.route('**/api/v1/settings/backup-key', route => { if (route.request().method() === 'GET') return route.fulfill({ json: { configured: keyWrites > 0 } }); keyWrites++; return route.fulfill({ json: { configured: true } }); });
  await page.route('**/api/v1/setup/configure-globals', route => {
    expect(keyWrites).toBe(1);
    if (++globals === 1) return route.fulfill({ status: 500, json: { detail: 'Global settings unavailable' } });
    step = 'auth';
    return route.fulfill({ json: {} });
  });
  await page.addInitScript(() => {
    if (!localStorage.getItem('linguard_setup_state')) localStorage.setItem('linguard_setup_state', JSON.stringify({ currentStep: 'globals', lastUpdated: new Date().toISOString(), data: { username: 'admin' } }));
  });
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('alert')).toContainText('Global settings unavailable');
  await page.reload();
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText('Backup key saved during setup. Enter a key only to replace it.')).toBeVisible();
  await page.getByLabel('Keep current key').check();
  await page.getByRole('button', { name: 'Save & Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Authentication' })).toBeVisible();
  expect(keyWrites).toBe(1);
  expect(step).toBe('auth');
  await expectNoSecret(page);
});

test('should display an allowed validation error in Settings', async ({ page }) => {
  await mockApp(page);
  await page.route('**/api/v1/settings/backup-key', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { configured: false } })
    : route.fulfill({ status: 400, json: { detail: 'Backup key is too long' } }));
  await page.goto('/settings');
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await page.getByRole('button', { name: 'Save backup key' }).click();
  await expect(page.getByText('Backup key is too long')).toBeVisible();
});

test('should preserve the unsaved-key warning in a fresh browser resumed from server globals', async ({ page }) => {
  await page.route('**/api/v1/setup/status', route => route.fulfill({ json: { setup_completed: false, requires_setup: true, current_step: 'globals' } }));
  await page.route('**/api/v1/auth/token', route => route.fulfill({ json: { access_token: 'admin-token', user: { role: 'admin' } } }));
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Backup encryption key (optional)').fill(secret);
  await expectNoSecret(page);
  await page.reload();
  await page.getByRole('button', { name: 'Resume Setup' }).click();
  await page.locator('input[name="password"]').fill('admin-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText(/previously entered backup key was not confirmed/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeDisabled();
  await page.getByRole('button', { name: 'Discard unsaved key' }).click();
  await expect(page.getByRole('button', { name: 'Save & Continue' })).toBeEnabled();
});
