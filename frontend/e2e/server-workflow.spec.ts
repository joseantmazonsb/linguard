import { test, expect } from '@playwright/test';

test.describe('Server Subnet Conflict and Toast Notifications', () => {
  test('should complete setup, then test subnet conflicts with toast notifications', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes
    
    // Track console errors for React hook issues
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // === SETUP WIZARD ===
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Step 1: Welcome
    await page.locator('button:has-text("Get Started")').click();
    
    // Step 2: Account Creation
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="email"]').fill('admin@example.com');
    await page.locator('input[name="password"]').fill('admin123');
    await page.locator('input[name="confirmPassword"]').fill('admin123');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);
    
    // Step 3: Global Settings
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 4: Create First Server (10.0.0.1/24)
    await page.locator('input[name="name"]').fill('Main VPN Server');
    await page.locator('input[name="endpoint"]').fill('vpn.example.com:51820');
    await page.locator('input[name="listen_port"]').fill('51820');
    await page.locator('input[name="ipv4_address"]').fill('10.0.0.1/24');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 5: Create First Peer
    await page.locator('input[name="name"]').fill('Test Client');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 6: Wait for completion
    await page.waitForSelector('button:has-text("Go to Login")', { timeout: 15000 });
    await page.locator('button:has-text("Go to Login")').click();
    await page.waitForURL(/\/login/, { timeout: 10000 });

    // === LOGIN ===
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    
    // === NAVIGATE TO SERVERS ===
    await page.click('a[href="/servers"]');
    await page.waitForLoadState('networkidle');
    
    // Verify we're on servers page and can see the existing server
    await expect(page.locator('text=Main VPN Server')).toBeVisible();
    
    // === TEST 1: TRY TO CREATE SERVER WITH OVERLAPPING SUBNET ===
    await page.click('button:has-text("Add Server")');
    await page.waitForSelector('input[name="name"]');
    
    await page.fill('input[name="name"]', 'Conflicting Server');
    await page.fill('input[name="endpoint"]', '192.168.1.101:51821');
    await page.fill('input[name="listen_port"]', '51821');
    await page.fill('input[name="address"]', '10.0.0.50/32'); // Conflicts with 10.0.0.1/24
    
    // Submit form
    await page.click('button:has-text("Create")');
    
    // Wait for error toast to appear
    const errorToast = page.locator('.Toastify__toast--error');
    await expect(errorToast).toBeVisible({ timeout: 5000 });
    
    // Verify error message mentions subnet or conflict
    const errorText = await errorToast.textContent();
    console.log('Error toast message:', errorText);
    expect(errorText).toMatch(/subnet|conflict/i);
    
    // Close the form
    await page.click('button:has-text("Cancel")');
    await page.waitForTimeout(500);
    
    // === TEST 2: CREATE SERVER WITH NON-CONFLICTING SUBNET ===
    await page.click('button:has-text("Add Server")');
    await page.waitForSelector('input[name="name"]');
    
    await page.fill('input[name="name"]', 'Valid Server');
    await page.fill('input[name="endpoint"]', '192.168.1.200:51822');
    await page.fill('input[name="listen_port"]', '51822');
    await page.fill('input[name="address"]', '10.100.0.1/24'); // No conflict
    
    // Submit form
    await page.click('button:has-text("Create")');
    
    // Wait for success toast
    const successToast = page.locator('.Toastify__toast--success');
    await expect(successToast).toBeVisible({ timeout: 5000 });
    
    // Verify success message
    const successText = await successToast.textContent();
    console.log('Success toast message:', successText);
    expect(successText).toMatch(/success|created/i);
    
    // Verify new server appears in the list
    await expect(page.locator('text=Valid Server')).toBeVisible({ timeout: 5000 });
    
    // === VERIFY NO REACT HOOK ERRORS ===
    const hasHookError = consoleErrors.some(error => 
      error.includes('Invalid hook call') || 
      error.includes('resolveDispatcher') ||
      error.includes('useState')
    );
    
    if (consoleErrors.length > 0) {
      console.log('=== All Console Errors ===');
      consoleErrors.forEach((error, i) => console.log(`${i + 1}. ${error}`));
    }
    
    expect(hasHookError, 'Should not have React hook errors').toBe(false);
    console.log('✓ No React hook errors detected');
    console.log('✓ Toast notifications working correctly');
    console.log('✓ Server subnet conflict validation working');
  });
});
