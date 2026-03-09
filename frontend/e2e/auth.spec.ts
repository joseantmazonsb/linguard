import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should redirect to login when not authenticated', async ({ page }) => {
    // If setup is complete, should redirect to login
    await page.waitForURL(/\/(login|setup)/, { timeout: 5000 });
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    // Assume setup is already complete for this test
    // Navigate to login
    await page.goto('/login');
    
    // Fill in credentials
    await page.fill('input[name="username"], input[type="text"]', 'admin');
    await page.fill('input[name="password"], input[type="password"]', 'SecurePassword123!');
    
    // Submit form
    await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")');
    
    // Should redirect to dashboard
    await page.waitForURL(/\/(dashboard|home|$)/, { timeout: 5000 });
    
    // Verify user is logged in
    const userMenu = page.locator('button:has-text("Account"), [data-testid="user-menu"], button:has-text("admin")');
    await expect(userMenu).toBeVisible({ timeout: 3000 });
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('input[name="username"], input[type="text"]', 'wronguser');
    await page.fill('input[name="password"], input[type="password"]', 'wrongpass');
    
    await page.click('button[type="submit"]');
    
    // Should show error message
    await expect(page.locator('text=/incorrect|invalid|error|failed/i')).toBeVisible({ timeout: 3000 });
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('input[name="username"], input[type="text"]', 'admin');
    await page.fill('input[name="password"], input[type="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');
    
    await page.waitForURL(/\/(dashboard|home)/, { timeout: 5000 });
    
    // Click user menu or logout button
    const userMenuButton = page.locator('button:has-text("Account"), [data-testid="user-menu"], button:has-text("admin")').first();
    await userMenuButton.click();
    
    // Click logout
    await page.click('button:has-text("Logout"), a:has-text("Logout"), [role="menuitem"]:has-text("Logout")');
    
    // Should redirect to login
    await page.waitForURL('/login', { timeout: 5000 });
  });

  test('should validate required fields', async ({ page }) => {
    await page.goto('/login');
    
    // Try to submit empty form
    await page.click('button[type="submit"]');
    
    // Should show validation errors or prevent submission
    const username = page.locator('input[name="username"], input[type="text"]');
    const isRequired = await username.evaluate(el => (el as HTMLInputElement).required);
    expect(isRequired).toBe(true);
  });
});
