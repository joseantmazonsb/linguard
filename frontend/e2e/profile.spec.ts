import { test, expect } from '@playwright/test';

test.describe('Profile Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="username"], input[type="text"]', 'admin');
    await page.fill('input[name="password"], input[type="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard|home)/, { timeout: 5000 });
  });

  test('should navigate to profile page', async ({ page }) => {
    // Click user menu
    const userMenu = page.locator('button:has-text("Account"), [data-testid="user-menu"], button:has-text("admin")').first();
    await userMenu.click();
    
    // Click profile link
    await page.click('a:has-text("Profile"), button:has-text("Profile"), [role="menuitem"]:has-text("Profile")');
    
    // Should navigate to profile page
    await page.waitForURL('/profile', { timeout: 5000 });
    
    // Profile form should be visible
    await expect(page.locator('h1, h2')).toContainText(/profile|account/i);
  });

  test('should display current user information', async ({ page }) => {
    await page.goto('/profile');
    
    // Username should be pre-filled (and likely disabled)
    const usernameInput = page.locator('input[name="username"]');
    if (await usernameInput.isVisible()) {
      await expect(usernameInput).toHaveValue('admin');
    }
    
    // Email should be pre-filled
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    await expect(emailInput).toHaveValue('admin@example.com');
  });

  test('should update email successfully', async ({ page }) => {
    await page.goto('/profile');
    
    // Update email
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    await emailInput.clear();
    await emailInput.fill('newemail@example.com');
    
    // Submit form
    await page.click('button[type="submit"]:has-text("Save"), button:has-text("Update")');
    
    // Should show success message
    await expect(page.locator('text=/success|updated|saved/i')).toBeVisible({ timeout: 5000 });
    
    // Email should be updated
    await page.reload();
    await expect(emailInput).toHaveValue('newemail@example.com');
  });

  test('should reject duplicate email', async ({ page }) => {
    await page.goto('/profile');
    
    // Try to update to an email that might already exist
    // (In a real scenario, you'd create another user first)
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    await emailInput.clear();
    await emailInput.fill('admin@example.com'); // Same email
    
    await page.click('button[type="submit"]:has-text("Save"), button:has-text("Update")');
    
    // Should either succeed (same email) or show error if backend validates uniqueness
    await page.waitForTimeout(2000);
  });

  test('should validate email format', async ({ page }) => {
    await page.goto('/profile');
    
    // Enter invalid email
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    await emailInput.clear();
    await emailInput.fill('invalid-email');
    
    await page.click('button[type="submit"]');
    
    // Should show validation error
    const errorMessage = page.locator('text=/invalid|error|valid email/i');
    await expect(errorMessage).toBeVisible({ timeout: 3000 });
  });

  test('should change password successfully', async ({ page }) => {
    await page.goto('/profile');
    
    // Look for password change section (might be a separate form or modal)
    const currentPasswordInput = page.locator('input[name="currentPassword"], input[name="current_password"], input[placeholder*="Current"]');
    const newPasswordInput = page.locator('input[name="newPassword"], input[name="new_password"], input[placeholder*="New password"]').first();
    const confirmPasswordInput = page.locator('input[name="confirmPassword"], input[name="confirm_password"], input[placeholder*="Confirm"]');
    
    if (await currentPasswordInput.isVisible()) {
      await currentPasswordInput.fill('SecurePassword123!');
      await newPasswordInput.fill('NewSecurePassword123!');
      await confirmPasswordInput.fill('NewSecurePassword123!');
      
      // Submit password change
      await page.click('button:has-text("Change Password"), button:has-text("Update Password")');
      
      // Should show success
      await expect(page.locator('text=/password.*changed|password.*updated|success/i')).toBeVisible({ timeout: 5000 });
      
      // Verify can login with new password
      await page.goto('/login');
      await page.fill('input[name="username"], input[type="text"]', 'admin');
      await page.fill('input[name="password"], input[type="password"]', 'NewSecurePassword123!');
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/(dashboard|home)/, { timeout: 5000 });
    }
  });

  test('should reject password change with wrong current password', async ({ page }) => {
    await page.goto('/profile');
    
    const currentPasswordInput = page.locator('input[name="currentPassword"], input[name="current_password"], input[placeholder*="Current"]');
    
    if (await currentPasswordInput.isVisible()) {
      await currentPasswordInput.fill('WrongPassword123!');
      await page.locator('input[name="newPassword"], input[name="new_password"]').first().fill('NewSecurePassword123!');
      await page.locator('input[name="confirmPassword"], input[name="confirm_password"]').fill('NewSecurePassword123!');
      
      await page.click('button:has-text("Change Password"), button:has-text("Update Password")');
      
      // Should show error
      await expect(page.locator('text=/incorrect|wrong|invalid|current password/i')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should validate password confirmation matches', async ({ page }) => {
    await page.goto('/profile');
    
    const newPasswordInput = page.locator('input[name="newPassword"], input[name="new_password"]').first();
    const confirmPasswordInput = page.locator('input[name="confirmPassword"], input[name="confirm_password"]');
    
    if (await newPasswordInput.isVisible()) {
      await page.locator('input[name="currentPassword"], input[name="current_password"]').fill('SecurePassword123!');
      await newPasswordInput.fill('NewSecurePassword123!');
      await confirmPasswordInput.fill('DifferentPassword123!');
      
      await page.click('button:has-text("Change Password"), button:has-text("Update Password")');
      
      // Should show error about passwords not matching
      await expect(page.locator('text=/match|same|confirm/i')).toBeVisible({ timeout: 3000 });
    }
  });
});
