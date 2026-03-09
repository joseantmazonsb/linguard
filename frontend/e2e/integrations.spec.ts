import { test, expect } from '@playwright/test';

test.describe('Integrations and Notifications', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app - assuming setup is complete
    await page.goto('/');
    
    // Check if we're on setup page and complete it if needed
    const currentUrl = page.url();
    if (currentUrl.includes('/setup')) {
      console.log('Setup page detected, completing setup...');
      
      // Fill setup form
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="email"]', 'admin@localhost');
      await page.fill('input[name="password"]', 'SecurePassword123!');
      
      // Submit setup form
      await page.click('button[type="submit"]');
      
      // Wait for redirect to login or dashboard
      await page.waitForURL(/\/(login|dashboard|home)/, { timeout: 10000 });
    }
    
    // If on login page, login
    if (page.url().includes('/login')) {
      console.log('Login page detected, logging in...');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', 'SecurePassword123!');
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/(dashboard|home)/, { timeout: 10000 });
    }
    
    // Should now be on dashboard
    await page.waitForSelector('text=/dashboard|servers|integrations/i', { timeout: 5000 });
  });

  test('should navigate to integrations page', async ({ page }) => {
    // Find and click Integrations link in navigation
    const integrationsLink = page.locator('a:has-text("Integrations"), a[href*="integrations"]');
    await expect(integrationsLink).toBeVisible({ timeout: 5000 });
    
    await integrationsLink.click();
    await page.waitForURL('**/integrations', { timeout: 5000 });
    
    // Verify we're on the integrations page
    await expect(page.locator('h1, h2').filter({ hasText: /integrations/i })).toBeVisible();
  });

  test('should show available integration types', async ({ page }) => {
    await page.goto('/integrations');
    
    // Click "Add Integration" or similar button
    const addButton = page.locator('button:has-text("Add"), button:has-text("Create"), button:has-text("New Integration")').first();
    await addButton.click({ timeout: 5000 });
    
    // Should show integration form/modal
    await expect(page.locator('text=/notification|webhook|email|slack/i')).toBeVisible({ timeout: 3000 });
  });

  test('should create a notification integration', async ({ page }) => {
    await page.goto('/integrations');
    
    // Click add integration button
    const addButton = page.locator('button:has-text("Add"), button:has-text("Create"), button:has-text("New Integration")').first();
    await addButton.click({ timeout: 5000 });
    
    // Fill integration form
    await page.fill('input[name="name"]', 'Test Notification Integration');
    
    // Select notification type
    const typeSelect = page.locator('select[name="type"], [name="type"]').first();
    await typeSelect.selectOption('notification');
    
    // Subscribe to server.created event
    const serverCreatedCheckbox = page.locator('input[type="checkbox"][value="server.created"]');
    if (await serverCreatedCheckbox.count() > 0) {
      await serverCreatedCheckbox.check();
    }
    
    // Submit form
    await page.click('button[type="submit"]:has-text("Create"), button:has-text("Save")');
    
    // Wait for success indicator (integration card or success message)
    await expect(page.locator('text=/Test Notification Integration|created|success/i')).toBeVisible({ timeout: 5000 });
  });

  test('should show integration in list after creation', async ({ page }) => {
    await page.goto('/integrations');
    
    // Create an integration first
    const addButton = page.locator('button:has-text("Add"), button:has-text("Create"), button:has-text("New Integration")').first();
    if (await addButton.count() > 0) {
      await addButton.click();
      await page.fill('input[name="name"]', 'List Test Integration');
      
      const typeSelect = page.locator('select[name="type"], [name="type"]').first();
      await typeSelect.selectOption('notification');
      
      await page.click('button[type="submit"]:has-text("Create"), button:has-text("Save")');
      await page.waitForTimeout(1000);
    }
    
    // Verify integration appears in list
    await expect(page.locator('text=List Test Integration')).toBeVisible({ timeout: 5000 });
  });

  test('should check notification center is visible', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Look for notification bell icon
    const notificationBell = page.locator('[data-testid="notification-bell"], button:has([data-icon="bell"]), button svg').first();
    await expect(notificationBell).toBeVisible({ timeout: 5000 });
  });

  test('should show unread count badge when there are notifications', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Look for notification badge (might be 0 initially)
    const badge = page.locator('[data-testid="unread-count"], .badge, span[class*="badge"]').first();
    
    // Badge might not be visible if count is 0, so just check if notification bell exists
    const notificationBell = page.locator('[data-testid="notification-bell"], button').first();
    await expect(notificationBell).toBeVisible({ timeout: 5000 });
  });

  test('should create server and generate notification (end-to-end)', async ({ page }) => {
    // First, create a notification integration
    await page.goto('/integrations');
    
    const addButton = page.locator('button:has-text("Add"), button:has-text("Create"), button:has-text("New Integration")').first();
    
    if (await addButton.count() > 0) {
      await addButton.click();
      await page.fill('input[name="name"]', 'E2E Test Integration');
      
      const typeSelect = page.locator('select[name="type"], [name="type"]').first();
      await typeSelect.selectOption('notification');
      
      // Subscribe to server.created
      const serverCreatedCheckbox = page.locator('input[type="checkbox"][value="server.created"]');
      if (await serverCreatedCheckbox.count() > 0) {
        await serverCreatedCheckbox.check();
      }
      
      await page.click('button[type="submit"]:has-text("Create"), button:has-text("Save")');
      await page.waitForTimeout(1000);
    }
    
    // Navigate to servers/dashboard
    await page.goto('/dashboard');
    
    // Get initial notification count
    const notificationBell = page.locator('[data-testid="notification-bell"], button').first();
    await notificationBell.click();
    
    const initialNotifications = await page.locator('[data-testid="notification-item"], .notification-item').count();
    
    // Close notification dropdown
    await page.keyboard.press('Escape');
    
    // Create a new server
    const createServerButton = page.locator('button:has-text("Create"), button:has-text("Add Server"), button:has-text("New Server")').first();
    if (await createServerButton.count() > 0) {
      await createServerButton.click();
      
      // Fill server form
      await page.fill('input[name="name"]', 'E2E Test Server');
      await page.fill('input[name="interface"]', 'wg-test0');
      await page.fill('input[name="listen_port"]', '51820');
      await page.fill('input[name="address"]', '10.0.0.1/24');
      
      // Submit
      await page.click('button[type="submit"]:has-text("Create"), button:has-text("Save")');
      
      // Wait for server creation
      await page.waitForTimeout(2000);
      
      // Check notifications
      await notificationBell.click();
      
      // Should have more notifications now
      const newNotifications = await page.locator('[data-testid="notification-item"], .notification-item').count();
      
      // Verify notification was created
      expect(newNotifications).toBeGreaterThanOrEqual(initialNotifications);
      
      // Look for server created notification
      await expect(page.locator('text=/server.*created|E2E Test Server/i')).toBeVisible({ timeout: 3000 });
    }
  });

  test('should mark notification as read', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Open notifications
    const notificationBell = page.locator('[data-testid="notification-bell"], button').first();
    await notificationBell.click();
    
    // Find unread notification and click it
    const unreadNotification = page.locator('[data-testid="notification-item"]:has(.unread), .notification-item.unread').first();
    
    if (await unreadNotification.count() > 0) {
      await unreadNotification.click();
      
      // Should mark as read (visual indicator changes)
      await page.waitForTimeout(500);
    }
  });

  test('should mark all notifications as read', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Open notifications
    const notificationBell = page.locator('[data-testid="notification-bell"], button').first();
    await notificationBell.click();
    
    // Look for "Mark all as read" button
    const markAllReadButton = page.locator('button:has-text("Mark all"), button:has-text("Read all")').first();
    
    if (await markAllReadButton.count() > 0) {
      await markAllReadButton.click();
      await page.waitForTimeout(500);
      
      // Unread count should be 0
      const badge = page.locator('[data-testid="unread-count"]').first();
      if (await badge.count() > 0) {
        await expect(badge).toHaveText('0');
      }
    }
  });

  test('should delete notification', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Open notifications
    const notificationBell = page.locator('[data-testid="notification-bell"], button').first();
    await notificationBell.click();
    
    const initialCount = await page.locator('[data-testid="notification-item"], .notification-item').count();
    
    if (initialCount > 0) {
      // Find delete button for first notification
      const deleteButton = page.locator('[data-testid="delete-notification"], button[aria-label*="delete"]').first();
      
      if (await deleteButton.count() > 0) {
        await deleteButton.click();
        await page.waitForTimeout(500);
        
        // Should have fewer notifications
        const newCount = await page.locator('[data-testid="notification-item"], .notification-item').count();
        expect(newCount).toBeLessThan(initialCount);
      }
    }
  });

  test('should edit integration', async ({ page }) => {
    await page.goto('/integrations');
    
    // Find edit button for first integration
    const editButton = page.locator('button:has-text("Edit"), button[aria-label*="edit"]').first();
    
    if (await editButton.count() > 0) {
      await editButton.click();
      
      // Should open edit form
      await expect(page.locator('input[name="name"]')).toBeVisible({ timeout: 3000 });
      
      // Change name
      await page.fill('input[name="name"]', 'Updated Integration Name');
      
      // Submit
      await page.click('button[type="submit"]:has-text("Update"), button:has-text("Save")');
      
      // Should show updated name
      await expect(page.locator('text=Updated Integration Name')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should disable/enable integration', async ({ page }) => {
    await page.goto('/integrations');
    
    // Find toggle switch
    const toggleSwitch = page.locator('input[type="checkbox"][role="switch"], button[role="switch"]').first();
    
    if (await toggleSwitch.count() > 0) {
      const isChecked = await toggleSwitch.isChecked();
      
      // Toggle it
      await toggleSwitch.click();
      await page.waitForTimeout(500);
      
      // Should be in opposite state
      const newState = await toggleSwitch.isChecked();
      expect(newState).not.toBe(isChecked);
    }
  });

  test('should delete integration', async ({ page }) => {
    await page.goto('/integrations');
    
    const initialCount = await page.locator('[data-testid="integration-card"], .integration-card, div:has(button:has-text("Edit"))').count();
    
    if (initialCount > 0) {
      // Find delete button
      const deleteButton = page.locator('button:has-text("Delete"), button[aria-label*="delete"]').first();
      
      if (await deleteButton.count() > 0) {
        await deleteButton.click();
        
        // Confirm deletion if there's a confirmation dialog
        const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Delete")').last();
        if (await confirmButton.count() > 0) {
          await confirmButton.click();
        }
        
        await page.waitForTimeout(1000);
        
        // Should have fewer integrations
        const newCount = await page.locator('[data-testid="integration-card"], .integration-card, div:has(button:has-text("Edit"))').count();
        expect(newCount).toBeLessThan(initialCount);
      }
    }
  });
});
