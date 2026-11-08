import { expect, test } from '@playwright/test';

test('should stream and download logs using authorization headers without URL credentials', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'secret-test-token');
    localStorage.setItem('role', 'admin');
    const originalFetch = window.fetch;
    window.fetch = async (input, init) => {
      const url = String(input);
      if (!url.includes('/api/v1/logs/')) return originalFetch(input, init);
      (window as any).logRequests ??= [];
      (window as any).logRequests.push({ url, authorization: new Headers(init?.headers).get('authorization') });
      if (url.includes('/stream')) {
        const encoder = new TextEncoder();
        return new Response(new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode('data: first'));
            controller.enqueue(encoder.encode(' line\n\ndata: \n\ndata: second line\n\n'));
          },
        }), { headers: { 'Content-Type': 'text/event-stream' } });
      }
      return new Response('downloaded log', { status: 200 });
    };
  });
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/setup/status')) return route.fulfill({ json: { setup_completed: true, requires_setup: false } });
    if (path.endsWith('/logs/info')) return route.fulfill({ json: { path: '/test.log', size_bytes: 10, size_human: '10 B', line_count: 2, last_modified: 0 } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/logs');
  await page.getByRole('button', { name: 'Start Live Tail' }).click();
  await expect(page.getByText('first line', { exact: true })).toBeVisible();
  await expect(page.getByText('second line', { exact: true })).toBeVisible();
  await expect(page.getByText('Live tailing')).toContainText('3 lines loaded');
  await page.getByRole('button', { name: 'Stop Live Tail' }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('linguard.log');
  const requests = await page.evaluate(() => (window as any).logRequests);
  expect(requests).toHaveLength(2);
  for (const request of requests) {
    expect(request.authorization).toBe('Bearer secret-test-token');
    expect(request.url).not.toContain('secret-test-token');
    expect(new URL(request.url, 'http://localhost:5173').searchParams.has('token')).toBe(false);
  }
});
