import { expect, test, type Page } from '@playwright/test';

const scriptType = {
  type: 'script', name: 'Custom Script', description: 'Execute shell scripts',
  config_schema: {}, enabled: true, icon: 'code',
};
const webhookType = {
  type: 'webhook', name: 'Webhook', description: 'Send requests',
  config_schema: {}, enabled: true, icon: 'link',
};

async function mockApp(page: Page, includeStaleType = true) {
  let script: any = {
    id: 1, name: 'Legacy script', type: 'script', config: { script_path: '/bin/false' },
    events_subscribed: ['server.created'], enabled: true, total_triggered: 0,
    created_at: '2026-01-01T00:00:00Z',
  };
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('role', 'admin');
  });
  await page.routeWebSocket('**/ws?*', (socket) => socket.close());
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    const method = route.request().method();
    if (path.endsWith('/integrations/1') && method === 'DELETE') {
      script = null;
      return route.fulfill({ status: 204 });
    }
    if (path.endsWith('/integrations/1') && method === 'PUT') {
      script = { ...script, ...route.request().postDataJSON() };
      return route.fulfill({ json: script });
    }
    let data: unknown = [];
    if (path.endsWith('/setup/status')) data = { setup_completed: true, requires_setup: false };
    else if (path.endsWith('/integrations/types/available')) data = includeStaleType ? [scriptType, webhookType] : [webhookType];
    else if (path.endsWith('/integrations')) data = script ? [script] : [];
    else if (path.endsWith('/notifications/unread/count')) data = { count: 0 };
    else if (path.endsWith('/version/current')) data = { version: 'test' };
    else if (path.endsWith('/version/check-updates')) data = {};
    await route.fulfill({ json: data });
  });
}

test('should not offer script even when stale type data includes it', async ({ page }) => {
  await mockApp(page);
  await page.goto('/integrations');
  await page.getByRole('button', { name: 'Add Integration' }).click();
  const form = page.locator('form');
  await expect(form.getByRole('button', { name: /Webhook - Send requests/ })).toBeVisible();
  await form.getByRole('button', { name: /Webhook - Send requests/ }).click();
  await expect(form.getByRole('button', { name: /Custom Script/ })).toHaveCount(0);
});

test('should identify and manage a stored unsupported script', async ({ page }) => {
  await mockApp(page, false);
  await page.goto('/integrations');
  const card = page.locator('div').filter({ has: page.getByRole('heading', { name: 'Legacy script' }) })
    .filter({ has: page.getByRole('button', { name: 'Edit', exact: true }) }).last();
  await expect(card.getByText('Script integrations are not supported and will not execute.')).toBeVisible();
  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  const form = page.locator('form');
  await expect(form.getByText('Script integrations are not supported and will not execute.')).toBeVisible();
  await expect(form.getByText(/Script.*unsupported/i).first()).toBeVisible();
  await form.getByRole('switch', { name: 'Enabled' }).click();
  await form.getByRole('button', { name: 'Update Integration' }).click();
  await expect(page.getByText('Integration updated successfully')).toBeVisible();
  await expect(card.getByRole('switch')).toBeDisabled();
  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(form.getByRole('switch', { name: 'Enabled' })).toBeDisabled();
  await form.getByRole('button', { name: 'Cancel' }).click();
  await card.getByRole('button', { name: 'Delete', exact: true }).click();
  await page.getByRole('heading', { name: 'Delete Integration' }).locator('..').locator('..').locator('..')
    .getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Legacy script' })).toHaveCount(0);
});
