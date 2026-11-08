import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { loadSetupState, saveSetupState, updateCurrentStep, updateSetupStepData } from '../src/utils/setupStorage.ts';

const key = 'linguard_setup_state';
const values = new Map();
globalThis.localStorage = {
  getItem: (name) => values.get(name) ?? null,
  setItem: (name, value) => values.set(name, value),
  removeItem: (name) => values.delete(name),
};

const state = () => ({
  currentStep: 'peer',
  lastUpdated: new Date().toISOString(),
  data: {
    username: 'admin', password: 'admin-password',
    connection_string: 'postgres://user:db-password@localhost/db',
    secret_key: 'signing-key', dns_primary: '1.1.1.1',
    serverId: 42, serverName: 'VPN', peerName: 'Laptop',
    auth: { oidc_client_id: 'client', oidc_client_secret: 'oidc-secret', skipped: false },
    account: { username: 'admin', password: 'nested-password', confirmPassword: 'nested-password' },
  },
});

describe('setup storage', () => {
  beforeEach(() => values.clear());

  it('should save resume data without credentials or signing keys', () => {
    const original = state();
    saveSetupState(original);
    const stored = JSON.parse(values.get(key));
    assert.equal(stored.currentStep, 'peer');
    assert.equal(stored.data.serverId, 42);
    assert.equal(stored.data.dns_primary, '1.1.1.1');
    assert.equal(stored.data.auth.oidc_client_id, 'client');
    for (const secret of ['admin-password', 'db-password', 'signing-key', 'oidc-secret', 'nested-password']) {
      assert.ok(!values.get(key).includes(secret), secret);
    }
    assert.equal(original.data.password, 'admin-password');
  });

  it('should sanitize legacy state on load without extending its expiry', () => {
    const legacy = state();
    values.set(key, JSON.stringify(legacy));
    const loaded = loadSetupState();
    assert.equal(loaded.currentStep, 'peer');
    assert.equal(loaded.data.serverId, 42);
    assert.equal(loaded.lastUpdated, legacy.lastUpdated);
    assert.deepEqual(JSON.parse(values.get(key)), loaded);
    for (const secret of ['admin-password', 'db-password', 'signing-key', 'oidc-secret', 'nested-password']) {
      assert.ok(!values.get(key).includes(secret), secret);
      assert.ok(!JSON.stringify(loaded).includes(secret), secret);
    }
  });

  it('should sanitize data passed through step updates', () => {
    saveSetupState(state());
    updateSetupStepData('auth', { oidc_client_secret: 'new-secret', oidc_client_id: 'new-client' });
    updateCurrentStep('server');
    assert.equal(loadSetupState().data.auth.oidc_client_id, 'new-client');
    assert.ok(!values.get(key).includes('new-secret'));
  });

  it('should not persist credentials embedded in an OIDC discovery URL', () => {
    const original = state();
    original.data.auth.oidc_discovery_url = 'https://user:password@idp.example.com/.well-known/openid-configuration?token=secret';
    saveSetupState(original);
    assert.ok(!values.get(key).includes('password'));
    assert.ok(!values.get(key).includes('token=secret'));
    values.set(key, JSON.stringify(original));
    loadSetupState();
    assert.ok(!values.get(key).includes('token=secret'));
  });

  it('should remove expired and malformed legacy state', () => {
    values.set(key, JSON.stringify({ ...state(), lastUpdated: '2000-01-01T00:00:00Z' }));
    assert.equal(loadSetupState(), null);
    assert.equal(values.has(key), false);
    values.set(key, '{"password":"secret"');
    assert.equal(loadSetupState(), null);
    assert.equal(values.has(key), false);
  });
});
