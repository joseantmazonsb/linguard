import { test, expect } from '@playwright/test';

/**
 * Webhook Integration Tests
 * 
 * Tests to verify webhook integration type works correctly
 */

const API_BASE = 'http://localhost:8000/api/v1';

test.describe('Webhook Integration Tests', () => {
  
  test('should create webhook integration', async ({ request }) => {
    const response = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Test Webhook Integration',
        type: 'webhook',
        description: 'Testing webhook functionality',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST',
          headers: {
            'X-Test-Header': 'test-value'
          }
        },
        events_subscribed: ['server.created', 'server.deleted'],
        enabled: true
      }
    });
    
    expect(response.status()).toBe(201);
    
    const integration = await response.json();
    console.log('Created webhook integration:', integration);
    
    expect(integration.id).toBeDefined();
    expect(integration.type).toBe('webhook');
    expect(integration.config.url).toBe('https://httpbin.org/post');
    expect(integration.config.method).toBe('POST');
    expect(integration.total_triggered).toBe(0);
  });
  
  test('END-TO-END: webhook should be triggered when event occurs', async ({ request }) => {
    // Step 1: Create webhook integration
    const webhookResponse = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Event Trigger Webhook',
        type: 'webhook',
        description: 'Webhook to test event triggering',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST'
        },
        events_subscribed: ['server.created'],
        enabled: true
      }
    });
    
    expect(webhookResponse.status()).toBe(201);
    const webhook = await webhookResponse.json();
    const webhookId = webhook.id;
    
    console.log(`Created webhook integration ID: ${webhookId}`);
    
    // Verify initial state
    expect(webhook.total_triggered).toBe(0);
    expect(webhook.last_triggered_at).toBeNull();
    
    // Step 2: Create a server to trigger the webhook
    const serverResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Webhook Trigger Test Server',
        interface: 'wg-webhook-test',
        listen_port: 51850,
        public_key: 'webhook-test-pub-key',
        private_key: 'webhook-test-priv-key',
        ipv4_address: '10.0.30.1/24'
      }
    });
    
    expect(serverResponse.status()).toBe(201);
    const server = await serverResponse.json();
    console.log(`Created server ID: ${server.id}`);
    
    // Step 3: Wait a bit for async event processing
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Step 4: Verify webhook was triggered
    const checkResponse = await request.get(`${API_BASE}/integrations/${webhookId}`);
    expect(checkResponse.status()).toBe(200);
    
    const updatedWebhook = await checkResponse.json();
    console.log('Webhook after trigger:', {
      total_triggered: updatedWebhook.total_triggered,
      last_triggered_at: updatedWebhook.last_triggered_at
    });
    
    expect(updatedWebhook.total_triggered).toBe(1);
    expect(updatedWebhook.last_triggered_at).not.toBeNull();
    
    // Step 5: Clean up - delete server
    await request.delete(`${API_BASE}/servers/${server.id}`);
  });
  
  test('should support different HTTP methods', async ({ request }) => {
    // Test POST method
    const postWebhook = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'POST Webhook',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST'
        },
        events_subscribed: ['server.created'],
        enabled: true
      }
    });
    
    expect(postWebhook.status()).toBe(201);
    const post = await postWebhook.json();
    expect(post.config.method).toBe('POST');
    
    // Test PUT method
    const putWebhook = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'PUT Webhook',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/put',
          method: 'PUT'
        },
        events_subscribed: ['server.edited'],
        enabled: true
      }
    });
    
    expect(putWebhook.status()).toBe(201);
    const put = await putWebhook.json();
    expect(put.config.method).toBe('PUT');
    
    // Test GET method
    const getWebhook = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'GET Webhook',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/get',
          method: 'GET'
        },
        events_subscribed: ['server.deleted'],
        enabled: true
      }
    });
    
    expect(getWebhook.status()).toBe(201);
    const get = await getWebhook.json();
    expect(get.config.method).toBe('GET');
  });
  
  test('should include custom headers in webhook request', async ({ request }) => {
    const response = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Webhook with Custom Headers',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST',
          headers: {
            'X-Custom-Header': 'custom-value',
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
          }
        },
        events_subscribed: ['server.created'],
        enabled: true
      }
    });
    
    expect(response.status()).toBe(201);
    const webhook = await response.json();
    
    expect(webhook.config.headers['X-Custom-Header']).toBe('custom-value');
    expect(webhook.config.headers['Authorization']).toBe('Bearer test-token');
  });
  
  test('should not trigger webhook when disabled', async ({ request }) => {
    // Create disabled webhook
    const webhookResponse = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Disabled Webhook',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST'
        },
        events_subscribed: ['server.created'],
        enabled: false  // Disabled
      }
    });
    
    expect(webhookResponse.status()).toBe(201);
    const webhook = await webhookResponse.json();
    const webhookId = webhook.id;
    
    // Create server (should not trigger disabled webhook)
    const serverResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Test Server for Disabled Webhook',
        interface: 'wg-disabled-test',
        listen_port: 51860,
        public_key: 'disabled-test-pub',
        private_key: 'disabled-test-priv',
        ipv4_address: '10.0.40.1/24'
      }
    });
    
    expect(serverResponse.status()).toBe(201);
    const server = await serverResponse.json();
    
    // Wait for potential event processing
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Verify webhook was NOT triggered
    const checkResponse = await request.get(`${API_BASE}/integrations/${webhookId}`);
    const updatedWebhook = await checkResponse.json();
    
    expect(updatedWebhook.total_triggered).toBe(0);
    expect(updatedWebhook.last_triggered_at).toBeNull();
    
    // Clean up
    await request.delete(`${API_BASE}/servers/${server.id}`);
  });
  
  test('should handle webhook URL validation', async ({ request }) => {
    // Test with missing URL
    const response = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Invalid Webhook',
        type: 'webhook',
        config: {
          method: 'POST'
          // Missing url
        },
        events_subscribed: ['server.created'],
        enabled: true
      }
    });
    
    // Should still create (validation happens at runtime)
    expect(response.status()).toBe(201);
    const webhook = await response.json();
    expect(webhook.config.url).toBeUndefined();
  });
  
  test('should trigger webhook for multiple event types', async ({ request }) => {
    // Create webhook subscribed to multiple events
    const webhookResponse = await request.post(`${API_BASE}/integrations/`, {
      data: {
        name: 'Multi-Event Webhook',
        type: 'webhook',
        config: {
          url: 'https://httpbin.org/post',
          method: 'POST'
        },
        events_subscribed: ['server.created', 'server.edited', 'server.deleted'],
        enabled: true
      }
    });
    
    expect(webhookResponse.status()).toBe(201);
    const webhook = await webhookResponse.json();
    const webhookId = webhook.id;
    
    // Create server (triggers server.created)
    const serverResponse = await request.post(`${API_BASE}/servers/`, {
      data: {
        name: 'Multi-Event Test Server',
        interface: 'wg-multi-test',
        listen_port: 51870,
        public_key: 'multi-test-pub',
        private_key: 'multi-test-priv',
        ipv4_address: '10.0.50.1/24'
      }
    });
    
    expect(serverResponse.status()).toBe(201);
    const server = await serverResponse.json();
    
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Update server (triggers server.edited)
    await request.put(`${API_BASE}/servers/${server.id}`, {
      data: {
        description: 'Updated description'
      }
    });
    
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Delete server (triggers server.deleted)
    await request.delete(`${API_BASE}/servers/${server.id}`);
    
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Check webhook was triggered 3 times
    const checkResponse = await request.get(`${API_BASE}/integrations/${webhookId}`);
    const updatedWebhook = await checkResponse.json();
    
    console.log(`Webhook triggered ${updatedWebhook.total_triggered} times`);
    expect(updatedWebhook.total_triggered).toBe(3);
  });
});
