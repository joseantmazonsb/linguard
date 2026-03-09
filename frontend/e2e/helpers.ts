import { Page } from '@playwright/test';

/**
 * Complete the setup wizard flow
 */
export async function completeSetupWizard(page: Page) {
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

  // Step 4: Create First Server
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
  
  // Wait for redirect to login
  await page.waitForURL(/\/login/, { timeout: 10000 });
}

/**
 * Login to the application
 */
export async function login(page: Page, username = 'admin', password = 'admin123') {
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

/**
 * Complete setup and login
 */
export async function setupAndLogin(page: Page) {
  await page.goto('/', { waitUntil: 'networkidle' });
  
  // Check if setup is needed
  const isSetupPage = await page.locator('h2:has-text("Welcome to Linguard")').count() > 0;
  
  if (isSetupPage) {
    await completeSetupWizard(page);
  }
  
  // Check if we need to login
  const isLoginPage = await page.locator('input[type="text"]').count() > 0;
  if (isLoginPage) {
    await login(page);
  }
}
