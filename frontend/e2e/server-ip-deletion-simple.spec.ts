import { test, expect } from '@playwright/test';

test.describe('Server IP Deletion API Test', () => {
  test('should delete IPv6 from server via API', async ({ request }) => {
    test.setTimeout(60000);
    
    console.log('=== Step 1: Initialize setup (if needed) ===');
    const initRes = await request.post('http://localhost:8000/api/v1/setup/initialize', {
      data: {
        username: 'admin',
        email: 'admin@test.com',
        password: 'admin123'
      }
    });
    if (initRes.ok()) {
      console.log('✓ Setup initialized');
    } else {
      const initError = await initRes.json();
      console.log('Setup already done or failed:', initError.detail);
    }
    
    console.log('\n=== Step 2: Login to get token ===');
    const loginRes = await request.post('http://localhost:8000/api/v1/auth/token', {
      form: {
        username: 'admin',
        password: 'admin123'
      }
    });
    expect(loginRes.ok()).toBeTruthy();
    const loginData = await loginRes.json();
    const token = loginData.access_token;
    console.log('✓ Logged in, got token');
    
    console.log('\n=== Step 3: Generate keypair ===');
    const keyRes = await request.get('http://localhost:8000/api/v1/utils/generate-keypair', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const keys = await keyRes.json();
    console.log('✓ Generated keys');
    
    console.log('\n=== Step 4: Create server with both IPv4 and IPv6 ===');
    const createRes = await request.post('http://localhost:8000/api/v1/servers/', {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: 'Test Server',
        endpoint: '192.168.1.100',
        listen_port: 51820,
        ipv4_address: '10.8.0.1/24',
        ipv6_address: 'fd00::1/64',
        public_key: keys.public_key,
        private_key: keys.private_key
      }
    });
    
    if (!createRes.ok()) {
      const errorData = await createRes.json();
      console.log('Server creation failed:', JSON.stringify(errorData, null, 2));
    }
    expect(createRes.ok()).toBeTruthy();
    const server = await createRes.json();
    console.log(`✓ Server created: ID=${server.id}`);
    console.log(`  IPv4: ${server.ipv4_address}`);
    console.log(`  IPv6: ${server.ipv6_address}`);
    
    expect(server.ipv4_address).toBe('10.8.0.1/24');
    expect(server.ipv6_address).toBe('fd00::1/64');
    
    console.log('\n=== Step 5: Update server - delete IPv6 (send empty string) ===');
    const updateRes = await request.put(`http://localhost:8000/api/v1/servers/${server.id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: server.name,
        endpoint: server.endpoint,
        listen_port: server.listen_port,
        ipv4_address: '10.8.0.1/24',
        ipv6_address: '',  // Empty string should delete it
        public_key: server.public_key,
        private_key: server.private_key
      }
    });
    
    console.log(`Update response status: ${updateRes.status()}`);
    const updateData = await updateRes.json();
    console.log('Update response:', JSON.stringify(updateData, null, 2));
    
    expect(updateRes.ok()).toBeTruthy();
    
    console.log(`\n=== Step 6: Verify IPv6 was deleted ===`);
    console.log(`  IPv4: ${updateData.ipv4_address}`);
    console.log(`  IPv6: ${updateData.ipv6_address}`);
    
    expect(updateData.ipv4_address).toBe('10.8.0.1/24');
    
    if (updateData.ipv6_address === null || updateData.ipv6_address === '') {
      console.log('✓✓✓ SUCCESS: IPv6 was deleted!');
    } else {
      console.log(`✗✗✗ FAILED: IPv6 still exists: ${updateData.ipv6_address}`);
      throw new Error(`IPv6 should be null/empty but is: ${updateData.ipv6_address}`);
    }
    
    console.log('\n=== Step 7: Try to delete both IPs (should fail) ===');
    const failRes = await request.put(`http://localhost:8000/api/v1/servers/${server.id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: server.name,
        endpoint: server.endpoint,
        listen_port: server.listen_port,
        ipv4_address: '',  // Try to delete both
        ipv6_address: '',
        public_key: server.public_key,
        private_key: server.private_key
      }
    });
    
    console.log(`Delete both IPs response status: ${failRes.status()}`);
    const failData = await failRes.json();
    console.log('Response:', JSON.stringify(failData, null, 2));
    
    expect(failRes.status()).toBe(422);
    console.log('✓ Got expected 422 error when trying to delete both IPs');
    
    console.log('\n=== ALL TESTS PASSED ===');
  });
});
