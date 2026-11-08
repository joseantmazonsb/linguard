import { test, expect, type Page, type WebSocketRoute } from '@playwright/test';

const peers = Array.from({ length: 205 }, (_, i) => ({
  id: i + 1, name: `Peer ${i + 1}`, address: `10.0.0.${i + 1}`,
  enabled: true, is_online: i >= 200, public_key: 'test-public-key',
  allowed_ips: '0.0.0.0/0', server_id: 1,
}));

const health = (status: string) => ({
  status, timestamp: new Date().toISOString(),
  checks: Object.fromEntries(['database', 'wireguard', 'ip_forwarding', 'firewall']
    .map((key) => [key, { status, message: null }])),
});

async function mockApp(page: Page) {
  const sockets: WebSocketRoute[] = [];
  const peerRequests: { skip: number; limit: number }[] = [];
  const metricHours: number[] = [];
  let healthStatus = 'healthy';
  let metricBytes = 1024;
  let rejectSockets = false;

  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('role', 'admin');
  });
  await page.routeWebSocket('**/ws?*', (socket) => {
    if (rejectSockets) {
      socket.close();
      return;
    }
    sockets.push(socket);
    socket.onClose(() => {
      const index = sockets.indexOf(socket);
      if (index >= 0) sockets.splice(index, 1);
    });
  });
  await page.route('**/health', (route) => route.fulfill({ json: health(healthStatus) }));
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (path.endsWith('/setup/status')) data = { setup_completed: true, requires_setup: false };
    else if (path.endsWith('/peers')) {
      const skip = Number(url.searchParams.get('skip') ?? 0);
      const limit = Number(url.searchParams.get('limit') ?? 50);
      peerRequests.push({ skip, limit });
      data = peers.slice(skip, skip + limit);
    } else if (path.endsWith('/metrics/dashboard')) {
      metricHours.push(Number(url.searchParams.get('hours')));
      data = {
        servers: { current_totals: { total_rx_bytes: metricBytes, total_tx_bytes: 0 }, hourly_metrics: [], top_servers: [] },
        peers: { current_totals: { total_rx_bytes: 0, total_tx_bytes: 0 }, hourly_metrics: [], top_peers: [] },
      };
    } else if (path.endsWith('/notifications/unread/count')) data = { count: 0 };
    else if (path.endsWith('/metrics/peers/aggregate')) data = { hourly_metrics: [], peers: [], current_totals: {} };
    else if (path.endsWith('/version/current')) data = { version: 'test' };
    else if (path.endsWith('/version/check-updates')) data = {};
    await route.fulfill({ json: data });
  });
  return {
    sockets, peerRequests, metricHours,
    setHealth: (status: string) => { healthStatus = status; },
    setMetricBytes: (bytes: number) => { metricBytes = bytes; },
    disconnect: () => { rejectSockets = true; for (const socket of [...sockets]) socket.close(); },
  };
}

test('should count all peers on the dashboard', async ({ page }) => {
  const app = await mockApp(page);
  await page.goto('/dashboard');
  const card = page.locator('a').filter({ hasText: 'Total Peers' });
  await expect(card).toContainText('205');
  await expect(card).toContainText('5 connected');
  expect(app.peerRequests).toEqual([{ skip: 0, limit: 100 }, { skip: 100, limit: 100 }, { skip: 200, limit: 100 }]);
});

test('should offer peers beyond the first page in traffic triggers', async ({ page }) => {
  const app = await mockApp(page);
  await page.goto('/traffic-triggers');
  await page.getByRole('button', { name: 'Add Your First Trigger' }).click();
  await expect.poll(() => app.peerRequests.length).toBe(3);
  await page.getByRole('button', { name: 'Select a peer...' }).click();
  await expect(page.getByRole('button', { name: 'Peer 205 (10.0.0.205)' })).toBeVisible();
});

test('should refresh metrics for the selected range and recover health after disconnect', async ({ page }) => {
  const app = await mockApp(page);
  await page.goto('/dashboard');
  await expect(page.getByText('Healthy', { exact: true })).toBeVisible();
  await expect.poll(() => app.sockets.length).toBeGreaterThan(0);
  await page.getByRole('button', { name: '7d' }).first().click();
  await expect.poll(() => app.metricHours.includes(168)).toBe(true);
  await expect(page.getByText('1.00 KB', { exact: true })).toBeVisible();
  app.setMetricBytes(2048);
  const priorRequests = app.metricHours.length;
  for (const socket of app.sockets) socket.send(JSON.stringify({ type: 'metrics_update', data: {} }));
  await expect.poll(() => app.metricHours.length).toBeGreaterThan(priorRequests);
  expect(app.metricHours.at(-1)).toBe(168);
  await expect(page.getByText('2.00 KB', { exact: true })).toBeVisible();
  for (const socket of app.sockets) socket.send(JSON.stringify({ type: 'health_update', data: health('warning') }));
  await expect(page.getByText('Warning', { exact: true })).toBeVisible();
  app.setHealth('healthy');
  await page.getByText('System Health', { exact: true }).click();
  await page.getByRole('button', { name: 'Test Health Now' }).click();
  await expect(page.getByText('Healthy', { exact: true }).first()).toBeVisible();
  await page.getByRole('heading', { name: 'System Health Details' }).locator('..').getByRole('button').click();
  for (const socket of app.sockets) socket.send(JSON.stringify({ type: 'health_update', data: health('warning') }));
  await expect(page.getByText('Warning', { exact: true })).toBeVisible();
  app.setHealth('healthy');
  app.setMetricBytes(4096);
  app.disconnect();
  await expect(page.getByText('Healthy', { exact: true })).toBeVisible();
  await expect(page.getByText('4.00 KB', { exact: true })).toBeVisible();
});

test('should poll while the websocket is unavailable', async ({ page }) => {
  const app = await mockApp(page);
  await page.clock.install();
  await page.goto('/dashboard');
  await expect(page.getByText('Healthy', { exact: true })).toBeVisible();
  await expect.poll(() => app.sockets.length).toBeGreaterThan(0);
  app.disconnect();
  await expect.poll(() => app.metricHours.length).toBeGreaterThan(1);
  const beforePolling = app.metricHours.length;
  app.setHealth('warning');
  app.setMetricBytes(8192);
  await page.clock.fastForward(300_001);
  await expect.poll(() => app.metricHours.length).toBeGreaterThan(beforePolling);
  await expect(page.getByText('Warning', { exact: true })).toBeVisible();
  await expect(page.getByText('8.00 KB', { exact: true })).toBeVisible();
});

test('should keep all-peers and infinite-peers query shapes separate', async ({ page }) => {
  await mockApp(page);
  await page.goto('/dashboard');
  await expect(page.locator('a').filter({ hasText: 'Total Peers' })).toContainText('205');
  await page.locator('a').filter({ hasText: 'Total Peers' }).click();
  await expect(page.getByText('Peer 1', { exact: true })).toBeVisible();
  await page.goto('/dashboard');
  await expect(page.locator('a').filter({ hasText: 'Total Peers' })).toContainText('205');
});
