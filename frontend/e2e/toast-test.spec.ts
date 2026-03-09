import { test, expect } from '@playwright/test';

test.describe('Toast Notification Test', () => {
  test('should load application without React hook errors', async ({ page }) => {
    // Listen for console errors
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Listen for page errors
    const pageErrors: Error[] = [];
    page.on('pageerror', (error) => {
      pageErrors.push(error);
    });

    // Navigate to the app
    await page.goto('/');
    
    // Wait for the page to be fully loaded
    await page.waitForLoadState('networkidle');
    
    // Give React time to initialize
    await page.waitForTimeout(2000);

    // Always log all errors for debugging
    if (consoleErrors.length > 0) {
      console.log('=== Console Errors Found ===');
      consoleErrors.forEach((error, i) => console.log(`${i + 1}. ${error}`));
    }
    
    if (pageErrors.length > 0) {
      console.log('=== Page Errors Found ===');
      pageErrors.forEach((error, i) => console.log(`${i + 1}. ${error.message}`));
    }

    // Check for React hook errors
    const hasHookError = consoleErrors.some(error => 
      error.includes('Invalid hook call') || 
      error.includes('resolveDispatcher') ||
      error.includes('useState')
    ) || pageErrors.some(error => 
      error.message.includes('Invalid hook call') || 
      error.message.includes('resolveDispatcher') ||
      error.message.includes('useState')
    );

    expect(hasHookError, 'Application should not have React hook errors').toBe(false);
    
    // Verify the app rendered
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
  });
});
