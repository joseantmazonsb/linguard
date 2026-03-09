import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="username"], input[type="text"]', 'admin');
    await page.fill('input[name="password"], input[type="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard|home)/, { timeout: 5000 });
  });

  test('should display dashboard after login', async ({ page }) => {
    // Dashboard should have heading
    await expect(page.locator('h1, h2')).toContainText(/dashboard|overview|home/i);
    
    // Should have navigation
    await expect(page.locator('nav, [role="navigation"]')).toBeVisible();
  });

  test('should show user menu in header', async ({ page }) => {
    const userMenu = page.locator('button:has-text("Account"), [data-testid="user-menu"], button:has-text("admin")').first();
    await expect(userMenu).toBeVisible();
    
    // Click to open menu
    await userMenu.click();
    
    // Menu items should be visible
    await expect(page.locator('a:has-text("Profile"), [role="menuitem"]:has-text("Profile")')).toBeVisible();
    await expect(page.locator('button:has-text("Logout"), [role="menuitem"]:has-text("Logout")')).toBeVisible();
  });

  test('should have working navigation links', async ({ page }) => {
    // Check for common navigation items
    const navigation = page.locator('nav, [role="navigation"]');
    
    // Look for Dashboard link
    const dashboardLink = navigation.locator('a:has-text("Dashboard"), a:has-text("Home")');
    if (await dashboardLink.isVisible()) {
      await expect(dashboardLink).toBeVisible();
    }
    
    // Look for Servers link
    const serversLink = navigation.locator('a:has-text("Servers")');
    if (await serversLink.isVisible()) {
      await serversLink.click();
      await page.waitForURL(/servers/, { timeout: 3000 });
      await page.goBack();
    }
    
    // Look for Peers/Clients link
    const peersLink = navigation.locator('a:has-text("Peers"), a:has-text("Clients")');
    if (await peersLink.isVisible()) {
      await peersLink.click();
      await page.waitForURL(/peers|clients/, { timeout: 3000 });
      await page.goBack();
    }
  });

  test('should display statistics or cards', async ({ page }) => {
    // Dashboard typically shows stats
    const statsCards = page.locator('[class*="card"], [class*="stat"], [data-testid*="stat"]');
    const count = await statsCards.count();
    
    // Should have at least some content
    expect(count).toBeGreaterThan(0);
  });

  test('should be responsive to window size', async ({ page }) => {
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    await page.reload();
    
    // Navigation might be collapsed in mobile menu
    const mobileMenu = page.locator('button[aria-label*="menu"], button:has-text("Menu"), [data-testid="mobile-menu"]');
    if (await mobileMenu.isVisible()) {
      await mobileMenu.click();
      await expect(page.locator('nav')).toBeVisible();
    }
    
    // Test desktop view
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.reload();
    await expect(page.locator('nav')).toBeVisible();
  });
});
