import { expect, test, type WebSocketRoute } from '@playwright/test';

test('exchanges bearer credentials for a fresh ticket on each connection', async ({ page }) => {
  const tickets: string[] = [];
  const socketUrls: string[] = [];
  const sockets: WebSocketRoute[] = [];
  await page.addInitScript(() => {
    localStorage.setItem('token', 'secret-bearer');
    localStorage.setItem('role', 'admin');
  });
  await page.routeWebSocket('**/ws?*', (socket) => {
    socketUrls.push(socket.url());
    sockets.push(socket);
  });
  await page.route('**/health', (route) => route.fulfill({ json: { status: 'healthy', checks: {} } }));
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/v1/ws/ticket') {
      expect(route.request().method()).toBe('POST');
      expect(route.request().headers().authorization).toBe('Bearer secret-bearer');
      const ticket = `ticket-${tickets.length + 1}`;
      tickets.push(ticket);
      await route.fulfill({ json: { ticket } });
      return;
    }
    const data = path.endsWith('/setup/status') ? { setup_completed: true, requires_setup: false }
      : path.endsWith('/notifications/unread/count') ? { count: 0 }
      : path.endsWith('/metrics/dashboard') ? {
        servers: { current_totals: {}, hourly_metrics: [], top_servers: [] },
        peers: { current_totals: {}, hourly_metrics: [], top_peers: [] },
      }
      : path.includes('/metrics/') ? { hourly_metrics: [], peers: [], current_totals: {} }
      : [];
    await route.fulfill({ json: data });
  });
  await page.goto('/dashboard');
  await expect.poll(() => socketUrls.length).toBeGreaterThanOrEqual(2);
  const initialCount = socketUrls.length;
  sockets.at(-1)?.close();
  await expect.poll(() => socketUrls.length, { timeout: 15000 }).toBeGreaterThan(initialCount);
  for (const url of socketUrls) {
    expect(url).not.toContain('secret-bearer');
    expect(new URL(url).searchParams.get('ticket')).toMatch(/^ticket-\d+$/);
  }
  expect(new Set(socketUrls).size).toBe(socketUrls.length);
});
