import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

test.describe('Server Subnet Conflict Validation - API Tests', () => {
  let authToken: string;
  let server1Id: number;

  test.beforeAll(async ({ request }) => {
    // Complete setup wizard via API
    // Step 1: Create admin account
    const setupResponse = await request.post(`${API_BASE}/setup/complete`, {
      data: {
        username: 'admin',
        email: 'admin@example.com',
        password: 'admin123'
      }
    });
    expect(setupResponse.ok()).toBeTruthy();
    
    // Step 2: Login to get token
    const formData = new URLSearchParams();
    formData.append('username', 'admin');
    formData.append('password', 'admin123');
    
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      data: formData.toString(),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    
    const loginData = await loginResponse.json();
    authToken = loginData.access_token;
  });

  test('should create first server with subnet 10.0.0.1/24', async ({ request }) => {
    const response = await request.post(`${API_BASE}/servers`, {
      data: {
        name: 'Test Server 1',
        interface: 'wg-test0',
        listen_port: 51820,
        endpoint: '192.168.1.100:51820',
        public_key: 'MeL4UDkm6KtzB0rgbSkxtwIY9wytEk9zGdp8MyTttjo=',
        private_key: 'OMAQt4LJHrHjdnp3vpLQ9w0PFZUC6at6TF+8cB+ikn4=',
        ipv4_address: '10.0.0.1/24',
        dns_primary: '1.1.1.1'
      },
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });
    
    expect(response.ok()).toBeTruthy();
    const server = await response.json();
    server1Id = server.id;
    
    console.log('✓ Created server 1 with IP 10.0.0.1/24');
  });

  test('should reject server with IP in existing server subnet (10.0.0.50/32)', async ({ request }) => {
    const response = await request.post(`${API_BASE}/servers`, {
      data: {
        name: 'Conflicting Server',
        interface: 'wg-test1',
        listen_port: 51821,
        endpoint: '192.168.1.101:51821',
        public_key: 'AnotherPublicKeyHere1234567890123456789012=',
        private_key: 'AnotherPrivateKeyHere1234567890123456789=',
        ipv4_address: '10.0.0.50/32', // Falls within 10.0.0.1/24
        dns_primary: '1.1.1.1'
      },
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });
    
    expect(response.status()).toBe(400);
    const error = await response.json();
    
    console.log('Error response:', error);
    expect(error.detail).toMatch(/subnet|conflict/i);
    
    console.log('✓ Correctly rejected server with conflicting subnet');
  });

  test('should reject server with subnet that contains existing server IP', async ({ request }) => {
    const response = await request.post(`${API_BASE}/servers`, {
      data: {
        name: 'Broad Subnet Server',
        interface: 'wg-test2',
        listen_port: 51822,
        endpoint: '192.168.1.102:51822',
        public_key: 'YetAnotherPublicKey1234567890123456789012=',
        private_key: 'YetAnotherPrivateKey123456789012345678=',
        ipv4_address: '10.0.0.0/16', // Contains 10.0.0.1
        dns_primary: '1.1.1.1'
      },
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });
    
    expect(response.status()).toBe(400);
    const error = await response.json();
    
    console.log('Error response:', error);
    expect(error.detail).toMatch(/subnet|conflict|contain/i);
    
    console.log('✓ Correctly rejected server with subnet containing existing server');
  });

  test('should accept server with non-conflicting subnet (10.100.0.1/24)', async ({ request }) => {
    const response = await request.post(`${API_BASE}/servers`, {
      data: {
        name: 'Valid Server',
        interface: 'wg-test3',
        listen_port: 51823,
        endpoint: '192.168.1.103:51823',
        public_key: 'ValidPublicKeyHere123456789012345678901234=',
        private_key: 'ValidPrivateKeyHere12345678901234567890=',
        ipv4_address: '10.100.0.1/24', // No conflict
        dns_primary: '1.1.1.1'
      },
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });
    
    expect(response.ok()).toBeTruthy();
    const server = await response.json();
    expect(server.ipv4_address).toBe('10.100.0.1/24');
    
    console.log('✓ Successfully created server with non-conflicting subnet');
  });
});
