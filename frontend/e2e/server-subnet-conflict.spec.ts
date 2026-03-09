import { test, expect } from '@playwright/test';
import { setupAndLogin } from './helpers';

test.describe('Server Subnet Conflict Validation', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(120000); // 2 minutes for setup + navigation
    
    // Complete setup and login
    await setupAndLogin(page);
    
    // Navigate to Servers page
    await page.click('a[href="/servers"]', { timeout: 60000 });
    await page.waitForLoadState('networkidle');
  });

  test('should show toast error when creating server with overlapping subnet', async ({ page }) => {
    // Track console errors
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Create first server with subnet 10.0.0.1/24
    await page.click('button:has-text("Add Server")');
    await page.waitForSelector('input[name="name"]');
    
    await page.fill('input[name="name"]', 'Test Server 1');
    await page.fill('input[name="endpoint"]', '192.168.1.100:51820');
    await page.fill('input[name="listen_port"]', '51820');
    await page.fill('input[name="address"]', '10.0.0.1/24');
    
    // Submit form
    await page.click('button:has-text("Create")');
    
    // Wait for success toast
    await page.waitForSelector('.Toastify__toast--success', { timeout: 5000 });
    await page.waitForTimeout(1000);
    
    // Close the form if still open
    const cancelButton = page.locator('button:has-text("Cancel")');
    if (await cancelButton.isVisible()) {
      await cancelButton.click();
    }
    
    // Wait for form to close
    await page.waitForTimeout(500);
    
    // Try to create second server with overlapping IP 10.0.0.50/32
    await page.click('button:has-text("Add Server")');
    await page.waitForSelector('input[name="name"]');
    
    await page.fill('input[name="name"]', 'Test Server 2');
    await page.fill('input[name="endpoint"]', '192.168.1.101:51821');
    await page.fill('input[name="listen_port"]', '51821');
    await page.fill('input[name="address"]', '10.0.0.50/32');
    
    // Submit form
    await page.click('button:has-text("Create")');
    
    // Wait for error toast to appear
    const errorToast = page.locator('.Toastify__toast--error');
    await expect(errorToast).toBeVisible({ timeout: 5000 });
    
    // Verify error message mentions subnet conflict
    const toastText = await errorToast.textContent();
    expect(toastText).toMatch(/subnet|conflict/i);
    
    // Verify no React hook errors occurred
    const hasHookError = consoleErrors.some(error => 
      error.includes('Invalid hook call') || 
      error.includes('resolveDispatcher') ||
      error.includes('useState')
    );
    
    if (hasHookError) {
      console.log('=== Console Errors ===');
      consoleErrors.forEach((error, i) => console.log(`${i + 1}. ${error}`));
    }
    
    expect(hasHookError, 'Should not have React hook errors').toBe(false);
  });

  test('should show toast success when creating server without conflicts', async ({ page }) => {
    // Track console errors
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Create server with unique subnet
    await page.click('button:has-text("Add Server")');
    await page.waitForSelector('input[name="name"]');
    
    await page.fill('input[name="name"]', 'Valid Server');
    await page.fill('input[name="endpoint"]', '192.168.1.200:51820');
    await page.fill('input[name="listen_port"]', '51820');
    await page.fill('input[name="address"]', '10.100.0.1/24');
    
    // Submit form
    await page.click('button:has-text("Create")');
    
    // Wait for success toast
    const successToast = page.locator('.Toastify__toast--success');
    await expect(successToast).toBeVisible({ timeout: 5000 });
    
    // Verify success message
    const toastText = await successToast.textContent();
    expect(toastText).toMatch(/success|created/i);
    
    // Verify no React hook errors occurred
    const hasHookError = consoleErrors.some(error => 
      error.includes('Invalid hook call') || 
      error.includes('resolveDispatcher') ||
      error.includes('useState')
    );
    
    expect(hasHookError, 'Should not have React hook errors').toBe(false);
  });
});
