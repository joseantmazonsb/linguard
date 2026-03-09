import { test, expect } from '@playwright/test';
import { setupAndLogin } from './helpers';

/**
 * Peer IP Autofill Tests
 * 
 * Tests to verify:
 * 1. Peer creation auto-fills first free IP (not server IP)
 * 2. Peer migration suggests first free IP on target server
 * 3. Peers cannot be created with server IP
 * 4. Peers with only IPv4 or only IPv6 can be created (NULL handling)
 */

const API_BASE = 'http://localhost:8000/api/v1';

test.describe('Peer IP Autofill E2E Tests', () => {
  let authToken: string;
  let serverId: number;
  let server2Id: number;
  
  test.beforeAll(async ({ request }) => {
    // Login to get auth token
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      data: {
        username: 'admin',
        password: 'admin1'
      }
    });
    
    expect(loginResponse.ok()).toBeTruthy();
    const loginData = await loginResponse.json();
    authToken = loginData.access_token;
    
    // Create test server
    const serverResponse = await request.post(`${API_BASE}/servers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Test Server 1',
        interface: 'wg-test1',
        listen_port: 51821,
        endpoint: 'test1.example.com:51821',
        public_key: 'test_pub_key_1_32_chars_base64==',
        private_key: 'test_priv_key_1_32_chars_base64=',
        ipv4_address: '10.8.0.1/24',
        ipv6_address: 'fd00::1/64'
      }
    });
    
    expect(serverResponse.ok()).toBeTruthy();
    const server = await serverResponse.json();
    serverId = server.id;
    
    // Create second test server for migration tests
    const server2Response = await request.post(`${API_BASE}/servers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Test Server 2',
        interface: 'wg-test2',
        listen_port: 51822,
        endpoint: 'test2.example.com:51822',
        public_key: 'test_pub_key_2_32_chars_base64==',
        private_key: 'test_priv_key_2_32_chars_base64=',
        ipv4_address: '10.9.0.1/24',
        ipv6_address: 'fd01::1/64'
      }
    });
    
    expect(server2Response.ok()).toBeTruthy();
    const server2 = await server2Response.json();
    server2Id = server2.id;
  });

  test('API: get peer defaults returns first free IP (not server IP)', async ({ request }) => {
    const response = await request.get(`${API_BASE}/peers/defaults/${serverId}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const defaults = await response.json();
    console.log('Peer defaults:', defaults);
    
    // Should have IP addresses
    expect(defaults.ipv4_address).toBeDefined();
    expect(defaults.ipv6_address).toBeDefined();
    
    // Extract IPs without CIDR
    const suggestedIPv4 = defaults.ipv4_address.split('/')[0];
    const suggestedIPv6 = defaults.ipv6_address.split('/')[0];
    
    // Verify suggested IPs are NOT the server IPs
    expect(suggestedIPv4).not.toBe('10.8.0.1');
    expect(suggestedIPv6).not.toBe('fd00::1');
    
    // Should suggest first free IP after server
    expect(suggestedIPv4).toBe('10.8.0.2');
    expect(suggestedIPv6).toBe('fd00::2');
  });

  test('API: create peer with only IPv4 (NULL matching bug fix)', async ({ request }) => {
    const response = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Peer IPv4 Only',
        server_id: serverId,
        ipv4_address: '10.8.0.10/32',
        // No IPv6 - this should work after NULL bug fix
        public_key: 'peer_ipv4_only_public_key_base64=',
        allowed_ips: '0.0.0.0/0'
      }
    });
    
    if (!response.ok()) {
      const errorText = await response.text();
      console.log('Error creating peer with only IPv4:', errorText);
    }
    
    expect(response.ok()).toBeTruthy();
    
    const peer = await response.json();
    expect(peer.ipv4_address).toBe('10.8.0.10/32');
    expect(peer.ipv6_address).toBeNull();
  });

  test('API: create peer with only IPv6', async ({ request }) => {
    const response = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Peer IPv6 Only',
        server_id: serverId,
        // No IPv4
        ipv6_address: 'fd00::10/128',
        public_key: 'peer_ipv6_only_public_key_base64=',
        allowed_ips: '::/0'
      }
    });
    
    if (!response.ok()) {
      const errorText = await response.text();
      console.log('Error creating peer with only IPv6:', errorText);
    }
    
    expect(response.ok()).toBeTruthy();
    
    const peer = await response.json();
    expect(peer.ipv4_address).toBeNull();
    expect(peer.ipv6_address).toBe('fd00::10/128');
  });

  test('API: reject peer with same IP as server', async ({ request }) => {
    const response = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Bad Peer',
        server_id: serverId,
        ipv4_address: '10.8.0.1/32', // Same as server!
        public_key: 'bad_peer_public_key_base64====',
        allowed_ips: '0.0.0.0/0'
      }
    });
    
    expect(response.status()).toBe(422);
    
    const error = await response.json();
    console.log('Validation error:', error);
    
    // Should contain error about server IP conflict
    const errorStr = JSON.stringify(error);
    expect(errorStr).toContain('cannot be the same as the server IP');
  });

  test('API: reject duplicate peer IP', async ({ request }) => {
    // First, create a peer
    const peer1Response = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Peer 1',
        server_id: serverId,
        ipv4_address: '10.8.0.20/32',
        public_key: 'peer1_public_key_base64======',
        allowed_ips: '0.0.0.0/0'
      }
    });
    
    expect(peer1Response.ok()).toBeTruthy();
    
    // Try to create another peer with same IP
    const peer2Response = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Peer 2',
        server_id: serverId,
        ipv4_address: '10.8.0.20/32', // Duplicate!
        public_key: 'peer2_public_key_base64======',
        allowed_ips: '0.0.0.0/0'
      }
    });
    
    expect(peer2Response.status()).toBe(422);
    
    const error = await peer2Response.json();
    const errorStr = JSON.stringify(error);
    expect(errorStr).toContain('already in use');
  });

  test('API: migration preview returns first free IP on target server', async ({ request }) => {
    // Create a peer on server 1
    const peerResponse = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Migration Test Peer',
        server_id: serverId,
        ipv4_address: '10.8.0.30/32',
        ipv6_address: 'fd00::30/128',
        public_key: 'migration_peer_public_key_base64=',
        allowed_ips: '0.0.0.0/0, ::/0'
      }
    });
    
    expect(peerResponse.ok()).toBeTruthy();
    const peer = await peerResponse.json();
    
    // Get migration preview for server 2
    const previewResponse = await request.get(
      `${API_BASE}/peers/${peer.id}/migration-preview?target_server_id=${server2Id}`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      }
    );
    
    expect(previewResponse.ok()).toBeTruthy();
    
    const preview = await previewResponse.json();
    console.log('Migration preview:', preview);
    
    // Should suggest IPs on target server's subnet
    expect(preview.suggested_ipv4_address).toBeDefined();
    expect(preview.suggested_ipv6_address).toBeDefined();
    
    // Extract IPs
    const suggestedIPv4 = preview.suggested_ipv4_address.split('/')[0];
    const suggestedIPv6 = preview.suggested_ipv6_address.split('/')[0];
    
    // Should NOT suggest target server's IPs
    expect(suggestedIPv4).not.toBe('10.9.0.1');
    expect(suggestedIPv6).not.toBe('fd01::1');
    
    // Should suggest first free IP on target server
    expect(suggestedIPv4).toBe('10.9.0.2');
    expect(suggestedIPv6).toBe('fd01::2');
  });

  test('API: reject migration to target server IP', async ({ request }) => {
    // Create a peer
    const peerResponse = await request.post(`${API_BASE}/peers/`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        name: 'Migration Bad IP Peer',
        server_id: serverId,
        ipv4_address: '10.8.0.40/32',
        public_key: 'migration_bad_peer_key_base64===',
        allowed_ips: '0.0.0.0/0'
      }
    });
    
    expect(peerResponse.ok()).toBeTruthy();
    const peer = await peerResponse.json();
    
    // Try to migrate with target server's IP
    const migrateResponse = await request.post(
      `${API_BASE}/peers/${peer.id}/migrate`,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        data: {
          target_server_id: server2Id,
          ipv4_address: '10.9.0.1/32' // Target server's IP!
        }
      }
    );
    
    expect(migrateResponse.status()).toBe(422);
    
    const error = await migrateResponse.json();
    const errorStr = JSON.stringify(error);
    expect(errorStr).toContain('cannot be the same as the server IP');
  });

  test('UI: peer form auto-fills first free IP when server selected', async ({ page }) => {
    await page.goto('/');
    await setupAndLogin(page);
    
    // Navigate to peers page
    await page.click('a[href="/peers"]');
    await page.waitForURL('**/peers');
    
    // Click add peer button
    await page.click('button:has-text("Add Peer")');
    
    // Wait for peer form to appear
    await page.waitForSelector('input[name="name"]');
    
    // Select server from dropdown
    await page.click('[role="combobox"]'); // Or specific server selector
    await page.waitForTimeout(500);
    await page.click(`text=Test Server 1`);
    
    // Wait for autofill to happen
    await page.waitForTimeout(1000);
    
    // Check that IPv4 address is auto-filled and NOT the server IP
    const ipv4Input = await page.locator('input[name="ipv4_address"]');
    const ipv4Value = await ipv4Input.inputValue();
    
    expect(ipv4Value).toBeTruthy();
    expect(ipv4Value).not.toContain('10.8.0.1'); // Should not be server IP
    
    console.log('Auto-filled IPv4:', ipv4Value);
  });
});
