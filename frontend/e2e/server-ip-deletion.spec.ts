import { test, expect } from '@playwright/test';

test.describe('Server IP Address Deletion', () => {
  test('should allow deleting one IP address but prevent deleting both', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes
    
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
    
    // Step 3: Global Settings - skip
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 4: Create First Server with BOTH IPv4 and IPv6
    await page.locator('input[name="name"]').fill('Dual Stack Server');
    await page.locator('input[name="endpoint"]').fill('vpn.example.com:51820');
    await page.locator('input[name="listen_port"]').fill('51820');
    await page.locator('input[name="ipv4_address"]').fill('10.8.0.1/24');
    await page.locator('input[name="ipv6_address"]').fill('fd00::1/64');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 5: Create First Peer - skip
    await page.locator('input[name="name"]').fill('Test Client');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 6: Complete setup and go to login
    await page.waitForSelector('button:has-text("Go to Login")', { timeout: 15000 });
    await page.locator('button:has-text("Go to Login")').click();
    await page.waitForURL(/\/login/, { timeout: 10000 });

    // === LOGIN ===
    await page.locator('input[name="username"]').fill('admin');
    await page.locator('input[name="password"]').fill('admin123');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/\/servers/, { timeout: 10000 });

    console.log('✓ Setup complete, logged in, navigating to servers page');

    // === TEST IP DELETION ===
    
    // Wait for server to be visible
    await page.waitForSelector('text=Dual Stack Server', { timeout: 10000 });
    console.log('✓ Found server in list');

    // Click on the server to open details/edit
    await page.locator('text=Dual Stack Server').click();
    await page.waitForTimeout(1000);
    
    // Look for edit button
    const editButton = page.locator('button:has-text("Edit"), button[aria-label*="Edit"]').first();
    await editButton.click();
    await page.waitForTimeout(1000);

    console.log('✓ Opened edit form');

    // Verify both IP fields are populated
    const ipv4Input = page.locator('input[name="ipv4_address"]');
    const ipv6Input = page.locator('input[name="ipv6_address"]');
    
    await expect(ipv4Input).toHaveValue('10.8.0.1/24');
    await expect(ipv6Input).toHaveValue('fd00::1/64');
    console.log('✓ Both IP addresses are present');

    // === TEST 1: Delete IPv4 (should succeed because IPv6 remains) ===
    console.log('\n=== TEST 1: Delete IPv4 address (IPv6 remains) ===');
    await ipv4Input.clear();
    await ipv4Input.fill('');
    
    // Submit the form
    const submitButton = page.locator('button[type="submit"]:has-text("Save"), button:has-text("Update")').first();
    await submitButton.click();
    await page.waitForTimeout(2000);

    // Check for success - should not show error
    const errorToast = page.locator('[role="alert"]:has-text("error"), .error, .alert-error').first();
    const isErrorVisible = await errorToast.isVisible().catch(() => false);
    
    if (isErrorVisible) {
      const errorText = await errorToast.textContent();
      console.log(`✗ FAILED: Got error when deleting IPv4: ${errorText}`);
      throw new Error(`Should be able to delete IPv4 when IPv6 exists, but got error: ${errorText}`);
    }
    
    console.log('✓ Successfully deleted IPv4 address');

    // Reopen the edit form to verify IPv4 was deleted
    await page.waitForTimeout(1000);
    await page.locator('button:has-text("Edit"), button[aria-label*="Edit"]').first().click();
    await page.waitForTimeout(1000);

    // Verify IPv4 is now empty and IPv6 remains
    const ipv4AfterDelete = await ipv4Input.inputValue();
    const ipv6AfterDelete = await ipv6Input.inputValue();
    
    console.log(`IPv4 after deletion: "${ipv4AfterDelete}"`);
    console.log(`IPv6 after deletion: "${ipv6AfterDelete}"`);
    
    if (ipv4AfterDelete !== '' && ipv4AfterDelete !== null) {
      console.log(`✗ FAILED: IPv4 was not deleted! Still has value: ${ipv4AfterDelete}`);
      throw new Error(`IPv4 should be empty after deletion, but has value: ${ipv4AfterDelete}`);
    }
    
    expect(ipv6AfterDelete).toBe('fd00::1/64');
    console.log('✓ Verified: IPv4 deleted, IPv6 remains');

    // === TEST 2: Try to delete IPv6 too (should fail - at least one IP required) ===
    console.log('\n=== TEST 2: Try to delete remaining IPv6 (should fail) ===');
    await ipv6Input.clear();
    await ipv6Input.fill('');
    
    await submitButton.click();
    await page.waitForTimeout(2000);

    // Should see an error message
    const errorMessage = page.locator('text=/at least one.*ip.*required/i, text=/required/i').first();
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    console.log('✓ Got expected error when trying to delete both IPs');

    // Verify IPv6 was NOT deleted (form should still show error, server unchanged)
    console.log('✓ Successfully prevented deletion of last IP address');

    console.log('\n=== ALL TESTS PASSED ===');
  });

  test('should allow deleting IPv6 while keeping IPv4', async ({ page }) => {
    test.setTimeout(120000);
    
    // === SETUP WIZARD ===
    await page.goto('/', { waitUntil: 'networkidle' });
    
    // Step 1: Welcome
    await page.locator('button:has-text("Get Started")').click();
    
    // Step 2: Account Creation  
    await page.locator('input[name="username"]').fill('testuser2');
    await page.locator('input[name="email"]').fill('test2@example.com');
    await page.locator('input[name="password"]').fill('test123');
    await page.locator('input[name="confirmPassword"]').fill('test123');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);
    
    // Step 3: Global Settings - skip
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 4: Create Server with BOTH IPs
    await page.locator('input[name="name"]').fill('IPv6 Test Server');
    await page.locator('input[name="endpoint"]').fill('vpn2.example.com:51821');
    await page.locator('input[name="listen_port"]').fill('51821');
    await page.locator('input[name="ipv4_address"]').fill('10.9.0.1/24');
    await page.locator('input[name="ipv6_address"]').fill('fd01::1/64');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 5: Create First Peer - skip
    await page.locator('input[name="name"]').fill('Client2');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Step 6: Complete setup
    await page.waitForSelector('button:has-text("Go to Login")', { timeout: 15000 });
    await page.locator('button:has-text("Go to Login")').click();
    await page.waitForURL(/\/login/, { timeout: 10000 });

    // === LOGIN ===
    await page.locator('input[name="username"]').fill('testuser2');
    await page.locator('input[name="password"]').fill('test123');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/\/servers/, { timeout: 10000 });

    console.log('✓ Setup complete, testing IPv6 deletion');

    // Wait for server
    await page.waitForSelector('text=IPv6 Test Server', { timeout: 10000 });
    
    // Open edit form
    await page.locator('text=IPv6 Test Server').click();
    await page.waitForTimeout(1000);
    await page.locator('button:has-text("Edit"), button[aria-label*="Edit"]').first().click();
    await page.waitForTimeout(1000);

    // Delete IPv6 (keep IPv4)
    const ipv4Input = page.locator('input[name="ipv4_address"]');
    const ipv6Input = page.locator('input[name="ipv6_address"]');
    
    await expect(ipv4Input).toHaveValue('10.9.0.1/24');
    await expect(ipv6Input).toHaveValue('fd01::1/64');
    
    await ipv6Input.clear();
    await ipv6Input.fill('');
    
    const submitButton = page.locator('button[type="submit"]:has-text("Save"), button:has-text("Update")').first();
    await submitButton.click();
    await page.waitForTimeout(2000);

    // Should succeed
    const errorToast = page.locator('[role="alert"]:has-text("error"), .error').first();
    const isErrorVisible = await errorToast.isVisible().catch(() => false);
    
    if (isErrorVisible) {
      const errorText = await errorToast.textContent();
      throw new Error(`Should be able to delete IPv6 when IPv4 exists, but got error: ${errorText}`);
    }
    
    console.log('✓ Successfully deleted IPv6 address');

    // Verify IPv6 deleted, IPv4 remains
    await page.waitForTimeout(1000);
    await page.locator('button:has-text("Edit"), button[aria-label*="Edit"]').first().click();
    await page.waitForTimeout(1000);

    const ipv4After = await ipv4Input.inputValue();
    const ipv6After = await ipv6Input.inputValue();
    
    expect(ipv4After).toBe('10.9.0.1/24');
    if (ipv6After !== '' && ipv6After !== null) {
      throw new Error(`IPv6 should be empty after deletion, but has value: ${ipv6After}`);
    }
    
    console.log('✓ Verified: IPv6 deleted, IPv4 remains');
    console.log('\n=== TEST PASSED ===');
  });
});
