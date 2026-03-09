import { test, expect } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

test.describe('Interface Monitoring - Auto-Detection', () => {
  test('should auto-detect when server is stopped manually outside webapp', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes

    // Track console logs
    const consoleLogs: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'log') {
        consoleLogs.push(msg.text());
      }
    });

    // === LOGIN ===
    console.log('Step 1: Login to application');
    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    console.log('✓ Logged in successfully');

    // === NAVIGATE TO SERVERS PAGE ===
    console.log('\nStep 2: Navigate to Servers page');
    await page.click('a[href="/servers"]');
    await page.waitForLoadState('networkidle');
    console.log('✓ On servers page');

    // === START A SERVER ===
    console.log('\nStep 3: Start the first server');
    
    // Find the first server row and its start button
    const firstServerRow = page.locator('tbody tr').first();
    await expect(firstServerRow).toBeVisible({ timeout: 5000 });
    
    // Get the server name for logging
    const serverName = await firstServerRow.locator('td').first().textContent();
    console.log(`  Server name: ${serverName}`);
    
    // Check if server is already running
    const serverStatus = await firstServerRow.locator('td').nth(2).textContent(); // Status column
    console.log(`  Current status: ${serverStatus}`);
    
    let serverId: string;
    
    if (serverStatus?.includes('running') || serverStatus?.includes('Active')) {
      console.log('  Server is already running, will use it for test');
      // Extract server ID from the row (assuming it's in a data attribute or link)
      const serverLink = firstServerRow.locator('a').first();
      const href = await serverLink.getAttribute('href');
      serverId = href?.split('/').pop() || '1';
    } else {
      console.log('  Server is stopped, starting it now...');
      // Find and click the start button in this row
      const startButton = firstServerRow.locator('button:has-text("Start")');
      await startButton.click();
      
      // Wait for success toast
      const successToast = page.locator('.Toastify__toast--success');
      await expect(successToast).toBeVisible({ timeout: 10000 });
      console.log('✓ Server started via webapp');
      
      // Wait a moment for the status to update
      await page.waitForTimeout(2000);
      
      // Extract server ID
      const serverLink = firstServerRow.locator('a').first();
      const href = await serverLink.getAttribute('href');
      serverId = href?.split('/').pop() || '1';
    }
    
    console.log(`  Server ID: ${serverId}`);

    // === VERIFY INTERFACE IS RUNNING VIA WG SHOW ===
    console.log('\nStep 4: Verify interface is running via "sudo wg show all"');
    
    const { stdout: wgShowBefore } = await execAsync('sudo wg show all');
    console.log('WireGuard interfaces before stopping:');
    console.log(wgShowBefore);
    
    // Expect to see at least one interface
    expect(wgShowBefore).toContain('interface:');
    console.log('✓ Interface confirmed running in WireGuard');

    // === GET THE PUBLIC KEY TO FIND THE RIGHT INTERFACE ===
    console.log('\nStep 5: Get server public key from API');
    
    // Make API call to get server details
    const apiResponse = await page.request.get(`http://localhost:8000/api/v1/servers/${serverId}`, {
      headers: {
        'Authorization': `Bearer ${await page.evaluate(() => localStorage.getItem('token'))}`,
      },
    });
    const serverData = await apiResponse.json();
    const publicKey = serverData.public_key;
    console.log(`  Public Key: ${publicKey}`);

    // Find which interface has this public key
    const interfaceMatch = wgShowBefore.match(new RegExp(`interface: (utun\\d+)[^]+public key: ${publicKey.replace(/\+/g, '\\+').replace(/\//g, '\\/')}`, 'm'));
    const interfaceName = interfaceMatch ? interfaceMatch[1] : null;
    
    if (!interfaceName) {
      console.error('Could not find interface name for public key:', publicKey);
      console.log('Available interfaces:', wgShowBefore);
      throw new Error('Could not find running interface');
    }
    
    console.log(`  Interface name: ${interfaceName}`);

    // === FIND AND KILL THE WIREGUARD-GO PROCESS ===
    console.log('\nStep 6: Kill wireguard-go process manually (simulating external stop)');
    
    // Find the wireguard-go process for this interface
    const { stdout: psOutput } = await execAsync(`ps aux | grep "wireguard-go ${interfaceName}" | grep -v grep`);
    console.log('Process info:', psOutput);
    
    const pidMatch = psOutput.match(/^\S+\s+(\d+)/);
    if (!pidMatch) {
      throw new Error(`Could not find wireguard-go process for ${interfaceName}`);
    }
    
    const pid = pidMatch[1];
    console.log(`  Found wireguard-go process: PID ${pid}`);
    
    // Kill the process
    await execAsync(`sudo kill ${pid}`);
    console.log(`✓ Killed wireguard-go process (PID ${pid})`);
    
    // Verify it's gone
    await page.waitForTimeout(1000);
    const { stdout: wgShowAfter } = await execAsync('sudo wg show all');
    console.log('\nWireGuard interfaces after killing process:');
    console.log(wgShowAfter || '(no interfaces)');
    
    // Verify the interface is no longer present
    expect(wgShowAfter).not.toContain(interfaceName);
    console.log(`✓ Interface ${interfaceName} confirmed stopped`);

    // === WAIT FOR AUTO-DETECTION (10 SECONDS) ===
    console.log('\nStep 7: Wait for interface monitor to detect the stopped server...');
    console.log('  (Monitor checks every 10 seconds)');
    
    // Go back to dashboard to see the status change
    await page.click('a[href="/dashboard"]');
    await page.waitForLoadState('networkidle');
    
    // Wait up to 15 seconds (giving it extra time beyond the 10s interval)
    console.log('  Waiting up to 15 seconds for auto-detection...');
    
    // Look for the toast notification (optional, might appear)
    const infoToast = page.locator('.Toastify__toast--info');
    try {
      await infoToast.waitFor({ state: 'visible', timeout: 15000 });
      const toastText = await infoToast.textContent();
      console.log(`✓ Toast notification appeared: "${toastText}"`);
    } catch (e) {
      console.log('  (No toast notification appeared, checking status directly)');
    }
    
    // === VERIFY DASHBOARD SHOWS SERVER AS INACTIVE ===
    console.log('\nStep 8: Verify Dashboard shows server as inactive');
    
    // Wait a bit more to ensure the UI has updated
    await page.waitForTimeout(3000);
    
    // Find the "Recent Servers" card
    const recentServersCard = page.locator('text=Recent Servers').locator('..');
    
    // Look for the server in the recent servers list
    const serverInDashboard = recentServersCard.locator(`text=${serverName}`).locator('../..');
    
    // Check if it shows as inactive (gray badge)
    const inactiveBadge = serverInDashboard.locator('span:has-text("Inactive")');
    await expect(inactiveBadge).toBeVisible({ timeout: 5000 });
    console.log('✓ Dashboard shows server as "Inactive"');

    // === VERIFY SERVERS PAGE SHOWS SERVER AS STOPPED ===
    console.log('\nStep 9: Verify Servers page shows server as stopped');
    
    await page.click('a[href="/servers"]');
    await page.waitForLoadState('networkidle');
    
    // Find the server row again
    const serverRow = page.locator(`text=${serverName}`).locator('../..');
    
    // Check the status column shows stopped/inactive
    const statusCell = serverRow.locator('td').nth(2); // Status column
    const statusText = await statusCell.textContent();
    
    console.log(`  Server status in table: ${statusText}`);
    expect(statusText?.toLowerCase()).toMatch(/stopped|inactive|not running/);
    console.log('✓ Servers page shows server as stopped');

    // === SUCCESS ===
    console.log('\n═══════════════════════════════════════════════════════');
    console.log('✓✓✓ TEST PASSED: Interface monitoring auto-detection works!');
    console.log('═══════════════════════════════════════════════════════');
    
    // Log WebSocket messages if any
    const wsLogs = consoleLogs.filter(log => log.includes('Server status change') || log.includes('WebSocket'));
    if (wsLogs.length > 0) {
      console.log('\nWebSocket messages received:');
      wsLogs.forEach(log => console.log(`  ${log}`));
    }
  });
});
