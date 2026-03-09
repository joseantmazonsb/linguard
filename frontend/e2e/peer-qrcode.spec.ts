import { test, expect } from '@playwright/test';

test.describe('Peer QR Code API Test', () => {
  test('should generate QR code for peer configuration', async ({ request }) => {
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
        name: 'QR Test Server',
        endpoint: 'vpn.example.com',
        listen_port: 51820,
        ipv4_address: '10.8.0.1/24',
        ipv6_address: 'fd00::1/64',
        dns_primary: '1.1.1.1',
        dns_secondary: '8.8.8.8',
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
        name: 'QR Test Peer',
        server_id: server.id,
        ipv4_address: '10.8.0.100/32',
        ipv6_address: 'fd00::100/128',
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
    
    console.log('\n=== Step 7: Request QR code ===');
    const qrCodeRes = await request.get(`http://localhost:8000/api/v1/peers/${peer.id}/qrcode`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    console.log(`QR code response status: ${qrCodeRes.status()}`);
    console.log(`QR code content-type: ${qrCodeRes.headers()['content-type']}`);
    
    // Check response status
    if (!qrCodeRes.ok()) {
      const errorText = await qrCodeRes.text();
      console.log('QR code generation failed:', errorText);
    }
    expect(qrCodeRes.ok()).toBeTruthy();
    
    // Check content type
    const contentType = qrCodeRes.headers()['content-type'];
    expect(contentType).toBe('image/png');
    console.log('✓ Content-Type is image/png');
    
    // Check that we got image data
    const qrCodeBuffer = await qrCodeRes.body();
    expect(qrCodeBuffer.length).toBeGreaterThan(0);
    console.log(`✓ QR code image size: ${qrCodeBuffer.length} bytes`);
    
    // Verify PNG signature (first 8 bytes)
    const pngSignature = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
    const receivedSignature = qrCodeBuffer.slice(0, 8);
    expect(receivedSignature.equals(pngSignature)).toBeTruthy();
    console.log('✓ QR code is a valid PNG image');
    
    console.log('\n=== Step 8: Get peer config for manual verification ===');
    const configRes = await request.get(`http://localhost:8000/api/v1/peers/${peer.id}/config`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(configRes.ok()).toBeTruthy();
    const configText = await configRes.text();
    console.log('✓ Peer config:');
    console.log(configText);
    
    // Verify config contains expected fields
    expect(configText).toContain('[Interface]');
    expect(configText).toContain('PrivateKey');
    expect(configText).toContain('Address');
    expect(configText).toContain('10.8.0.100/32');
    expect(configText).toContain('fd00::100/128');
    expect(configText).toContain('DNS');
    expect(configText).toContain('[Peer]');
    expect(configText).toContain('PublicKey');
    expect(configText).toContain('Endpoint');
    expect(configText).toContain('vpn.example.com:51820');
    expect(configText).toContain('AllowedIPs');
    expect(configText).toContain('PersistentKeepalive');
    console.log('✓ Config contains all expected fields');
    
    console.log('\n=== Step 9: Test QR code with peer that has only IPv4 ===');
    const peerKeyRes2 = await request.get('http://localhost:8000/api/v1/utils/generate-keypair', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const peerKeys2 = await peerKeyRes2.json();
    
    const createPeerRes2 = await request.post('http://localhost:8000/api/v1/peers/', {
      headers: { 'Authorization': `Bearer ${token}` },
      data: {
        name: 'QR Test Peer IPv4 Only',
        server_id: server.id,
        ipv4_address: '10.8.0.101/32',
        public_key: peerKeys2.public_key,
        private_key: peerKeys2.private_key
      }
    });
    expect(createPeerRes2.ok()).toBeTruthy();
    const peer2 = await createPeerRes2.json();
    console.log(`✓ Peer 2 created: ID=${peer2.id} (IPv4 only)`);
    
    const qrCodeRes2 = await request.get(`http://localhost:8000/api/v1/peers/${peer2.id}/qrcode`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(qrCodeRes2.ok()).toBeTruthy();
    expect(qrCodeRes2.headers()['content-type']).toBe('image/png');
    const qrCodeBuffer2 = await qrCodeRes2.body();
    expect(qrCodeBuffer2.length).toBeGreaterThan(0);
    console.log('✓ QR code generated successfully for IPv4-only peer');
    
    console.log('\n=== ALL TESTS PASSED ===');
  });
});
