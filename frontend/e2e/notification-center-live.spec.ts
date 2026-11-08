import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';

async function mockApp(page: Page, initiallyAvailable = true) {
  const sockets: WebSocketRoute[] = [];
  const requests = { list: 0, count: 0, profile: 0 };
  let available = initiallyAvailable;
  let title = 'Initial notification';
  let count = 1;

  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('role', 'standard');
  });
  await page.routeWebSocket('**/ws?*', socket => {
    if (!available) {
      socket.close();
      return;
    }
    sockets.push(socket);
    socket.onClose(() => {
      const index = sockets.indexOf(socket);
      if (index >= 0) sockets.splice(index, 1);
    });
  });
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    let data: unknown = {};
    if (path.endsWith('/setup/status')) data = { setup_completed: true, requires_setup: false };
    else if (path.endsWith('/ws/ticket')) data = { ticket: 'ticket' };
    else if (path.endsWith('/notifications/unread/count')) {
      requests.count++;
      data = { count };
    } else if (path.endsWith('/notifications')) {
      requests.list++;
      expect(url.searchParams.get('unread_only')).toBe('false');
      expect(url.searchParams.get('limit')).toBe('20');
      expect(url.searchParams.get('offset')).toBe('0');
      data = [{ id: 1, title, message: 'Message', type: 'info', read: false, created_at: new Date().toISOString() }];
    } else if (path.endsWith('/auth/profile')) {
      requests.profile++;
      data = { username: 'test', email: 'test@example.com', role: 'standard' };
    }
    await route.fulfill({ json: data });
  });
  return {
    sockets, requests,
    setData: (newTitle: string, newCount: number) => { title = newTitle; count = newCount; },
    disconnect: () => { available = false; for (const socket of [...sockets]) socket.close(); },
    reconnect: () => { available = true; },
  };
}

async function openNotifications(page: Page) {
  await page.locator('nav button.relative.p-2:not([title])').click();
  await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible();
}

test('should poll notification data while the socket is unavailable', async ({ page }) => {
  const app = await mockApp(page, false);
  await page.clock.install();
  await page.goto('/profile');
  await openNotifications(page);
  await expect(page.getByText('Initial notification')).toBeVisible();
  await expect(page.locator('nav button.relative.p-2:not([title])')).toContainText('1');
  const before = { ...app.requests };
  app.setData('Polled notification', 2);
  await page.clock.fastForward(300_001);
  await expect(page.getByText('Polled notification')).toBeVisible();
  await expect(page.locator('nav button.relative.p-2:not([title])')).toContainText('2');
  expect(app.requests.list).toBeGreaterThan(before.list);
  expect(app.requests.count).toBeGreaterThan(before.count);
  expect(app.requests.profile).toBe(before.profile);
});

test('should resume polling after an established socket disconnects', async ({ page }) => {
  const app = await mockApp(page);
  await page.clock.install();
  await page.goto('/profile');
  await openNotifications(page);
  await expect(page.getByText('Initial notification')).toBeVisible();
  await expect.poll(() => app.sockets.length).toBe(1);
  const disconnected = page.waitForEvent('console', { predicate: message => message.text() === 'WebSocket disconnected' });
  app.disconnect();
  await disconnected;
  app.setData('After disconnect', 2);
  await page.clock.fastForward(300_001);
  await expect(page.getByText('After disconnect')).toBeVisible();
  await expect(page.locator('nav button.relative.p-2:not([title])')).toContainText('2');
});

test('should refresh missed notifications on reconnect and stop polling when connected', async ({ page }) => {
  const app = await mockApp(page);
  await page.clock.install();
  await page.goto('/profile');
  await openNotifications(page);
  await expect(page.getByText('Initial notification')).toBeVisible();
  await expect.poll(() => app.sockets.length).toBe(1);
  app.disconnect();
  await expect.poll(() => app.sockets.length).toBe(0);
  app.setData('Missed notification', 3);
  const profileRequests = app.requests.profile;
  app.reconnect();
  await page.clock.fastForward(3_001);
  await expect.poll(() => app.sockets.length).toBe(1);
  await expect(page.getByText('Missed notification')).toBeVisible();
  await expect(page.locator('nav button.relative.p-2:not([title])')).toContainText('3');
  const before = { ...app.requests };
  await page.clock.fastForward(300_001);
  expect(app.requests.list).toBe(before.list);
  expect(app.requests.count).toBe(before.count);
  expect(app.requests.profile).toBe(profileRequests);
});

test('should refresh notification data and show a toast for a live event', async ({ page }) => {
  const app = await mockApp(page);
  await page.goto('/profile');
  await openNotifications(page);
  await expect(page.getByText('Initial notification')).toBeVisible();
  await expect.poll(() => app.sockets.length).toBe(1);
  const profileRequests = app.requests.profile;
  app.setData('Live notification', 4);
  app.sockets[0].send(JSON.stringify({ type: 'notification', data: { type: 'info', message: 'Live toast' } }));
  await expect(page.getByText('Live notification')).toBeVisible();
  await expect(page.locator('nav button.relative.p-2:not([title])')).toContainText('4');
  await expect(page.getByText('Live toast')).toBeVisible();
  expect(app.requests.profile).toBe(profileRequests);
});
