import { test, expect } from '@playwright/test';

test.describe('Peer IP Deletion API Test', () => {
  test('should delete IPv6 from peer via API', async ({ request }) => {
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
    
    console.log('\n=== Step 3: Generate keypair for server ===');
    const serverKeyRes = await request.get('http://localhost:8000/api/v1/utils/generate-keypair', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const serverKeys = await serverKeyRes.json();
    console.log('✓ Generated server keys');
    
    console.log('\n=== Step 4: Create server ===');
    const createServerRes = await request.post('http://localhost:8000/api/v1/servers/', {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: 'Test Server',
        endpoint: '192.168.1.100',
        listen_port: 51820,
        ipv4_address: '10.8.0.1/24',
        ipv6_address: 'fd00::1/64',
        public_key: serverKeys.public_key,
        private_key: serverKeys.private_key
      }
    });
    expect(createServerRes.ok()).toBeTruthy();
    const server = await createServerRes.json();
    console.log(`✓ Server created: ID=${server.id}`);
    
    console.log('\n=== Step 5: Generate keypair for peer ===');
    const peerKeyRes = await request.get('http://localhost:8000/api/v1/utils/generate-keypair', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const peerKeys = await peerKeyRes.json();
    console.log('✓ Generated peer keys');
    
    console.log('\n=== Step 6: Create peer with both IPv4 and IPv6 ===');
    const createPeerRes = await request.post('http://localhost:8000/api/v1/peers/', {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: 'Test Peer',
        server_id: server.id,
        ipv4_address: '10.8.0.2/32',
        ipv6_address: 'fd00::2/128',
        public_key: peerKeys.public_key,
        private_key: peerKeys.private_key
      }
    });
    
    if (!createPeerRes.ok()) {
      const errorData = await createPeerRes.json();
      console.log('Peer creation failed:', JSON.stringify(errorData, null, 2));
    }
    expect(createPeerRes.ok()).toBeTruthy();
    const peer = await createPeerRes.json();
    console.log(`✓ Peer created: ID=${peer.id}`);
    console.log(`  IPv4: ${peer.ipv4_address}`);
    console.log(`  IPv6: ${peer.ipv6_address}`);
    
    expect(peer.ipv4_address).toBe('10.8.0.2/32');
    expect(peer.ipv6_address).toBe('fd00::2/128');
    
    console.log('\n=== Step 7: Update peer - delete IPv6 (send empty string) ===');
    const updateRes = await request.put(`http://localhost:8000/api/v1/peers/${peer.id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: peer.name,
        server_id: peer.server_id,
        ipv4_address: '10.8.0.2/32',
        ipv6_address: '',  // Empty string should delete it
        public_key: peer.public_key,
        private_key: peer.private_key
      }
    });
    
    console.log(`Update response status: ${updateRes.status()}`);
    const updateData = await updateRes.json();
    console.log('Update response:', JSON.stringify(updateData, null, 2));
    
    expect(updateRes.ok()).toBeTruthy();
    
    console.log(`\n=== Step 8: Verify IPv6 was deleted ===`);
    console.log(`  IPv4: ${updateData.ipv4_address}`);
    console.log(`  IPv6: ${updateData.ipv6_address}`);
    
    expect(updateData.ipv4_address).toBe('10.8.0.2/32');
    
    if (updateData.ipv6_address === null || updateData.ipv6_address === '') {
      console.log('✓✓✓ SUCCESS: IPv6 was deleted!');
    } else {
      console.log(`✗✗✗ FAILED: IPv6 still exists: ${updateData.ipv6_address}`);
      throw new Error(`IPv6 should be null/empty but is: ${updateData.ipv6_address}`);
    }
    
    console.log('\n=== Step 9: Try to delete both IPs (should fail) ===');
    const failRes = await request.put(`http://localhost:8000/api/v1/peers/${peer.id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: peer.name,
        server_id: peer.server_id,
        ipv4_address: '',  // Try to delete both
        ipv6_address: '',
        public_key: peer.public_key,
        private_key: peer.private_key
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
