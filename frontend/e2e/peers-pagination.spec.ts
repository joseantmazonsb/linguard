import { test, expect, type Page } from '@playwright/test';

const peers = Array.from({ length: 205 }, (_, i) => ({
  id: i + 1,
  name: `Peer ${i + 1}`,
  description: i >= 150 ? 'remote group' : '',
  ipv4_address: `10.0.${Math.floor(i / 255)}.${i % 255}`,
  public_key: 'test-public-key',
  allowed_ips: '0.0.0.0/0',
  server_id: i < 102 ? 1 : 2,
  enabled: i % 2 === 0,
  is_online: i >= 200,
}));

async function mockApp(page: Page, failLaterPage = false) {
  const requests: number[] = [];
  const currentPeers = peers.map((peer) => ({ ...peer }));
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('role', 'admin');
  });
  await page.routeWebSocket('**/ws?*', () => {});
  await page.route('**/health', (route) => route.fulfill({ json: { checks: { wireguard: { status: 'healthy' } } } }));
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (path.endsWith('/setup/status')) data = { setup_completed: true, requires_setup: false };
    else if (path.endsWith('/peers')) {
      const skip = Number(url.searchParams.get('skip') ?? 0);
      const limit = Number(url.searchParams.get('limit') ?? 50);
      requests.push(skip);
      if (failLaterPage && skip >= 100) return route.fulfill({ status: 500, json: { detail: 'Page failed' } });
      const serverId = url.searchParams.get('server_id');
      const filtered = serverId ? currentPeers.filter((peer) => peer.server_id === Number(serverId)) : currentPeers;
      data = filtered.slice(skip, skip + limit);
    } else if (route.request().method() === 'PUT' && /\/peers\/\d+$/.test(path)) {
      const peer = currentPeers.find((item) => item.id === Number(path.split('/').pop()));
      if (peer) Object.assign(peer, route.request().postDataJSON());
      data = peer;
    } else if (path.endsWith('/servers')) data = [{ id: 1, name: 'Server One' }, { id: 2, name: 'Server Two' }];
    else if (path.endsWith('/metrics/peers/aggregate')) data = { hourly_metrics: [], peers: [], current_totals: {} };
    else if (path.endsWith('/notifications/unread/count')) data = { count: 0 };
    else if (path.endsWith('/version/current')) data = { version: 'test' };
    else if (path.endsWith('/version/check-updates')) data = {};
    await route.fulfill({ json: data });
  });
  return requests;
}

function summary(page: Page, label: string) {
  return page.getByText(label, { exact: true }).locator('..');
}

test('should count all peers and search beyond the first page', async ({ page }) => {
  const requests = await mockApp(page);
  await page.goto('/peers');
  await expect(summary(page, 'Total Peers')).toContainText('205');
  await expect(summary(page, 'Active')).toContainText('103');
  await expect(summary(page, 'Connected')).toContainText('5');
  await expect(summary(page, 'Offline')).toContainText('200');
  expect(requests).toContain(200);
  await expect(page.getByRole('heading', { name: 'Peer 205', exact: true })).toHaveCount(0);
  await page.getByPlaceholder('Search by name, IP, or description...').fill('peer 205');
  await expect(page.getByRole('heading', { name: 'Peer 205', exact: true })).toBeVisible();
  await expect(page.getByText('Found 1 peer matching')).toBeVisible();
});

test('should paginate search results and apply server filter to counts and search', async ({ page }) => {
  await mockApp(page);
  await page.goto('/peers');
  await expect(summary(page, 'Total Peers')).toContainText('205');
  await page.getByPlaceholder('Search by name, IP, or description...').fill('remote group');
  await expect(page.getByText('Found 55 peers matching')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Peer 205', exact: true })).toHaveCount(0);
  await page.getByText('Scroll for more').scrollIntoViewIfNeeded();
  await expect(page.getByRole('heading', { name: 'Peer 205', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'All Servers' }).click();
  await page.getByRole('button', { name: 'Server One', exact: true }).click();
  await expect(summary(page, 'Total Peers')).toContainText('102');
  await expect(summary(page, 'Active')).toContainText('51');
  await expect(summary(page, 'Connected')).toContainText('0');
  await expect(summary(page, 'Offline')).toContainText('102');
  await expect(page.getByText('No peers found')).toBeVisible();
  await page.getByPlaceholder('Search by name, IP, or description...').fill('peer 101');
  await expect(page.getByRole('heading', { name: 'Peer 101', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Server One' }).click();
  await page.getByRole('button', { name: 'Server Two', exact: true }).click();
  await expect(summary(page, 'Total Peers')).toContainText('103');
  await expect(summary(page, 'Connected')).toContainText('5');
  await page.getByPlaceholder('Search by name, IP, or description...').fill('peer 205');
  await expect(page.getByRole('heading', { name: 'Peer 205', exact: true })).toBeVisible();
});

test('should refresh complete counts after updating a peer beyond the first page', async ({ page }) => {
  await mockApp(page);
  await page.goto('/peers');
  await expect(summary(page, 'Active')).toContainText('103');
  await page.getByPlaceholder('Search by name, IP, or description...').fill('peer 205');
  const card = page.getByRole('heading', { name: 'Peer 205', exact: true }).locator('../..').locator('../..');
  await card.getByTitle('Disable peer').click();
  await expect(summary(page, 'Active')).toContainText('102');
  await expect(card.getByTitle('Enable peer')).toBeVisible();
});

test('should not report partial counts when a later page fails', async ({ page }) => {
  await mockApp(page, true);
  await page.goto('/peers');
  await expect(page.getByText('Error loading peers:')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('Total Peers', { exact: true })).toHaveCount(0);
});
