import { test, expect } from '@playwright/test';

test.describe('Setup Wizard Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Enable all console logs
    page.on('console', msg => {
      console.log(`[Browser ${msg.type()}]:`, msg.text());
    });
    
    // Enable page errors
    page.on('pageerror', error => {
      console.log('[Page Error]:', error.message);
    });
    
    // Enable request failures
    page.on('requestfailed', request => {
      console.log('[Request Failed]:', request.url(), request.failure()?.errorText);
    });
    
    // Navigate to the app - should redirect to /setup if not set up
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Wait for React to load
    await page.waitForTimeout(3000);
  });

  test('complete setup wizard end-to-end', async ({ page }) => {
    test.setTimeout(60000); // 60 seconds timeout
    
    // Step 1: Welcome - verify and click Get Started
    await expect(page.locator('h2')).toContainText('Welcome');
    await page.locator('button:has-text("Get Started")').click();
    
    // Step 2: Account Creation
    await expect(page.locator('h2')).toContainText('Create Admin Account');
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="email"]').fill('admin@example.com');
    await page.locator('input[name="password"]').fill('testpassword123');
    await page.locator('input[name="confirmPassword"]').fill('testpassword123');
    await page.locator('button[type="submit"]').click();
    
    // Wait for account creation and auto-login
    await page.waitForTimeout(3000);
    
    // Step 3: Global Settings - should appear after successful account creation
    await expect(page.locator('h2')).toContainText('Global Settings', { timeout: 10000 });
    
    // Fields are pre-filled, just submit
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 4: Create First Server
    await expect(page.locator('h2')).toContainText(/server/i, { timeout: 10000 });
    
    await page.locator('input[name="name"]').fill('Main VPN Server');
    await page.locator('input[name="endpoint"]').fill('vpn.example.com:51820');
    await page.locator('input[name="listen_port"]').fill('51820');
    await page.locator('input[name="ipv4_address"]').fill('10.0.0.1/24');
    
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 5: Create First Peer
    await expect(page.locator('h2')).toContainText(/peer|client/i, { timeout: 10000 });
    
    await page.locator('input[name="name"]').fill('Test Client');
    // IP address should be auto-filled by backend
    
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 6: Completion
    await expect(page.locator('h2')).toContainText(/complete|completing/i, { timeout: 10000 });
    
    // Wait for completion to finish
    await expect(page.locator('h2')).toContainText('Setup Complete!', { timeout: 15000 });
    
    // Click the "Go to Login" button
    await page.locator('button:has-text("Go to Login")').click();
    
    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 10000 });
  });
});
