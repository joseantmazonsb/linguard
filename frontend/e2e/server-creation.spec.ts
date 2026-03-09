import { test, expect } from '@playwright/test';

/**
 * Server Creation Tests
 * 
 * Tests to verify server creation works correctly with proper field names
 */

const API_BASE = 'http://localhost:8000/api/v1';

test.describe('Server Creation Tests', () => {
  
  test('should get server defaults for autofill', async ({ request }) => {
    const response = await request.get(`${API_BASE}/servers/defaults/autofill`);
    
    expect(response.status()).toBe(200);
    
    const defaults = await response.json();
    console.log('Server defaults:', defaults);
    
    // Should have interface, keys, addresses, etc.
    expect(defaults.interface).toBeDefined();
    expect(defaults.public_key).toBeDefined();
    expect(defaults.private_key).toBeDefined();
  });

  test('should create server with correct field names', async ({ request }) => {
    // Get defaults first
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    console.log('Defaults received:', defaults);
    
    // Create server with correct schema
    const serverData = {
      name: 'Test Server',
      interface: defaults.interface || 'wg-test0',
      listen_port: 51820,
      endpoint: 'vpn.example.com:51820',
      public_key: defaults.public_key || 'MeL4UDkm6KtzB0rgbSkxtwIY9wytEk9zGdp8MyTttjo=',
      private_key: defaults.private_key || 'OMAQt4LJHrHjdnp3vpLQ9w0PFZUC6at6TF+8cB+ikn4=',
      ipv4_address: '10.0.1.1/24',
      ipv6_address: 'fd00::1/64',
      dns_primary: '1.1.1.1',
      dns_secondary: '8.8.8.8',
      description: 'Test server created via API',
    };
    
    console.log('Creating server with data:', serverData);
    
    const response = await request.post(`${API_BASE}/servers/`, {
      data: serverData
    });
    
    console.log('Server creation response status:', response.status());
    
    if (response.status() !== 201) {
      const errorText = await response.text();
      console.log('Error response:', errorText);
    }
    
    expect(response.status()).toBe(201);
    
    const server = await response.json();
    console.log('Created server:', server);
    
    expect(server.id).toBeDefined();
    expect(server.name).toBe('Test Server');
    expect(server.interface).toBe(serverData.interface);
    expect(server.listen_port).toBe(51820);
    expect(server.ipv4_address).toBe('10.0.1.1/24');
    expect(server.ipv6_address).toBe('fd00::1/64');
    expect(server.dns_primary).toBe('1.1.1.1');
    expect(server.dns_secondary).toBe('8.8.8.8');
  });

  test('should reject server with old field names (interface_name)', async ({ request }) => {
    // Get defaults first
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    // Try to create server with OLD incorrect field name
    const serverData = {
      name: 'Test Server',
      interface_name: 'wg-test0', // WRONG - should be 'interface'
      listen_port: 51820,
      public_key: defaults.public_key,
      private_key: defaults.private_key,
    };
    
    console.log('Creating server with OLD field names:', serverData);
    
    const response = await request.post(`${API_BASE}/servers/`, {
      data: serverData
    });
    
    console.log('Response status:', response.status());
    
    // Should get 422 validation error because 'interface' is required
    expect(response.status()).toBe(422);
    
    const error = await response.json();
    console.log('Validation error:', error);
    
    // Should complain about missing 'interface' field
    expect(JSON.stringify(error)).toContain('interface');
  });

  test('should reject server with missing required fields', async ({ request }) => {
    const serverData = {
      name: 'Test Server',
      // Missing interface, listen_port, public_key, private_key
    };
    
    const response = await request.post(`${API_BASE}/servers/`, {
      data: serverData
    });
    
    expect(response.status()).toBe(422);
    
    const error = await response.json();
    console.log('Validation errors for missing fields:', error);
    
    // Should have multiple validation errors
    expect(error.detail).toBeDefined();
    expect(Array.isArray(error.detail)).toBe(true);
    expect(error.detail.length).toBeGreaterThan(0);
  });

  test('should list servers', async ({ request }) => {
    const response = await request.get(`${API_BASE}/servers/`);
    
    expect(response.status()).toBe(200);
    
    const servers = await response.json();
    expect(Array.isArray(servers)).toBe(true);
    
    console.log(`Found ${servers.length} servers`);
    
    // If we have servers, check structure
    if (servers.length > 0) {
      const server = servers[0];
      expect(server.id).toBeDefined();
      expect(server.name).toBeDefined();
      expect(server.interface).toBeDefined();
      expect(server.listen_port).toBeDefined();
      expect(server.public_key).toBeDefined();
    }
  });

  test('should get server by ID', async ({ request }) => {
    // First create a server
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    const createResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Get Test Server',
        interface: defaults.interface || 'wg-get-test',
        listen_port: 51821,
        public_key: defaults.public_key,
        private_key: defaults.private_key,
        ipv4_address: '10.0.2.1/24',
      }
    });
    
    expect(createResponse.status()).toBe(201);
    const created = await createResponse.json();
    
    // Now get it by ID
    const getResponse = await request.get(`${API_BASE}/servers/${created.id}`);
    
    expect(getResponse.status()).toBe(200);
    
    const server = await getResponse.json();
    expect(server.id).toBe(created.id);
    expect(server.name).toBe('Get Test Server');
    expect(server.ipv4_address).toBe('10.0.2.1/24');
  });

  test('should update server', async ({ request }) => {
    // Create a server
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    const createResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Update Test Server',
        interface: defaults.interface || 'wg-update-test',
        listen_port: 51822,
        public_key: defaults.public_key,
        private_key: defaults.private_key,
      }
    });
    
    const created = await createResponse.json();
    
    // Update it
    const updateResponse = await request.put(`${API_BASE}/servers/${created.id}`, {
      data: {
        name: 'Updated Server Name',
        description: 'Updated description',
        endpoint: 'updated.example.com:51822',
      }
    });
    
    expect(updateResponse.status()).toBe(200);
    
    const updated = await updateResponse.json();
    expect(updated.name).toBe('Updated Server Name');
    expect(updated.description).toBe('Updated description');
    expect(updated.endpoint).toBe('updated.example.com:51822');
    // Interface should remain unchanged
    expect(updated.interface).toBe(created.interface);
  });

  test('should delete server', async ({ request }) => {
    // Create a server
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    const createResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Delete Test Server',
        interface: defaults.interface || 'wg-delete-test',
        listen_port: 51823,
        public_key: defaults.public_key,
        private_key: defaults.private_key,
      }
    });
    
    const created = await createResponse.json();
    
    // Delete it
    const deleteResponse = await request.delete(`${API_BASE}/servers/${created.id}`);
    
    expect(deleteResponse.status()).toBe(204);
    
    // Verify it's gone
    const getResponse = await request.get(`${API_BASE}/servers/${created.id}`);
    expect(getResponse.status()).toBe(404);
  });

  test('should create server with bounce routing', async ({ request }) => {
    // Get defaults
    const defaultsResponse = await request.get(`${API_BASE}/servers/defaults/autofill`);
    const defaults = await defaultsResponse.json();
    
    // First create a bounce server
    const bounceResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Bounce Server',
        interface: 'wg-bounce',
        listen_port: 51900,
        public_key: defaults.public_key,
        private_key: defaults.private_key,
        is_bounce_server: true,
      }
    });
    
    expect(bounceResponse.status()).toBe(201);
    const bounceServer = await bounceResponse.json();
    
    // Create a server that routes through the bounce server
    const serverResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Server via Bounce',
        interface: 'wg-via-bounce',
        listen_port: 51901,
        public_key: defaults.public_key.replace(/A/g, 'B'), // Different key
        private_key: defaults.private_key.replace(/A/g, 'B'),
        bounce_via_server_id: bounceServer.id,
      }
    });
    
    expect(serverResponse.status()).toBe(201);
    const server = await serverResponse.json();
    
    expect(server.bounce_via_server_id).toBe(bounceServer.id);
    console.log(`✓ Server ${server.id} routes through bounce server ${bounceServer.id}`);
  });
});
