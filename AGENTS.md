# Linguard - AI Development Guide

This document provides guidelines for AI assistants working on the Linguard repository. It covers project structure, coding patterns, best practices, and development workflows.

## 📋 Project Overview

**Linguard** is a modern web application for managing WireGuard VPN servers. Built with FastAPI (backend) and React/TypeScript (frontend), it provides a comprehensive interface for creating, configuring, and monitoring WireGuard interfaces and peers.

### Technology Stack

**Backend:**
- Python 3.8+
- FastAPI
- SQLAlchemy ORM
- Pydantic v2 for validation
- PostgreSQL/SQLite/MySQL databases

**Frontend:**
- React 18+
- TypeScript
- Vite
- Radix UI for primitives
- Tailwind CSS
- Zustand for state management
- TanStack Query for server state

### Key Features
- WireGuard server management (create, edit, delete)
- Peer management with automatic configuration generation
- Real-time traffic monitoring and metrics
- OIDC SSO support for enterprise authentication
- Encrypted credentials storage
- Firewall integration (iptables/nftables/firewalld)
- Background services (health checks, backups, metrics)
- Webhook integrations via Traffic Triggers

---

## 🏗️ Frontend Architecture

### Directory Structure

```
frontend/src/
├── assets/              # Static assets (images, fonts)
├── components/          # Reusable UI components
│   ├── Dialog/          # Modal dialogs
│   ├── Forms/           # Form components
│   ├── Layout/          # Layout components
│   └── primitives/      # Radix UI wrappers
├── contexts/            # React Context providers
├── hooks/               # Custom React hooks
├── pages/               # Page components (routes)
│   ├── Setup/           # Setup wizard pages
│   └── ...              # Feature pages
├── services/            # API service layer
├── store/               # Zustand state stores
├── types/               # TypeScript type definitions
├── utils/               # Utility functions
└── ...                 # Vite config, entry points
```

### Component Patterns

#### 1. Presentational Components
Components receive props and render UI without side effects:

```typescript
interface ServerFormProps {
  server: Server | null;      // Existing server or null for new
  servers: Server[];          // Available servers (for bounce)
  onSubmit: (data: any) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  fieldErrors?: FieldErrors;
}
```

**Rules:**
- Props must be explicitly typed with interfaces
- No external dependencies except from `services/`, `utils/`, or other components
- Pure render logic - no side effects
- Use `useCallback` for event handlers passed to children

#### 2. Container/Smart Components
Components that manage state and fetch data:

```typescript
export default function ServersPage() {
  const servers = useQuery({
    queryKey: ['servers'],
    queryFn: serversAPI.list,
  });

  const { data: fieldErrors } = useMutation({
    mutationFn: (data) => serversAPI.create(data),
    onError: (error, variables) => {
      // Map API errors to field errors
      const errors = parseApiError(error, variables);
      setFieldErrors(errors);
    },
  });
}
```

**Rules:**
- Use TanStack Query for all server-state data
- Extract business logic to custom hooks when possible
- Handle loading, error, and success states explicitly

---

## 🧠 TypeScript Patterns

### 1. Type vs Interface

**Use `interface` for:**
- Object shapes that may extend
- Props interfaces
- Classes

```typescript
interface ServerFormProps {
  server: Server | null;
  onSubmit: (data: ServerCreate) => void;
}
```

**Use `type` for:**
- Union types
- Tuple types
- Generic constraints
- Type aliases

```typescript
type TrafficScope = 'peer' | 'server' | 'global';
type MetricsData = { metrics: TrafficMetric[]; summary: Summary };
type ServerCreate = { name: string; listen_port: number; ... };
```

### 2. API Response Types

Generate types from API client responses:

```typescript
// In types/index.ts
export type Server = {
  id: number;
  name: string;
  description?: string;
  listen_port: number;
  // ... all fields from backend response
};

export type ServerCreate = {
  name: string;
  listen_port: number;
  endpoint: string;
  // Only writable fields, no id, no read-only fields
};

export type ServerUpdate = Partial<Omit<ServerCreate, 'name' | 'listen_port'>>;
```

### 3. Optional Chaining & Null Safety

```typescript
// Safe access
const serverName = server?.name;
const peerCount = server?.peer_count ?? 0;

// Conditional rendering
if (server) {
  // Edit mode
} else if (defaults) {
  // Create mode with defaults
}
```

### 4. API Client Usage

```typescript
// From services/apiClient.ts
import { serversAPI, peersAPI, utilsAPI } from '../services/apiClient';

// Create server
const server = await serversAPI.create({
  name: 'Production Server',
  listen_port: 51820,
  endpoint: 'vpn.example.com',
  public_key: keyPair.public_key,
  private_key: keyPair.private_key,
  autostart: true,
});

// Update with partial data
await serversAPI.update(server.id, {
  name: 'Updated Server',
  description: 'Production WireGuard Server',
});

// Delete
await serversAPI.delete(server.id);
```

---

## 🎯 SOLID Principles

### 1. Single Responsibility Principle (SRP)

Each class/component should have one reason to change.

**❌ Bad:** Component that fetches data, handles form, displays errors, and sends notifications

```typescript
// Anti-pattern - too many responsibilities
export function ServerPage() {
  // Fetch data
  // Handle form
  // Display errors
  // Send notifications
  // ...
}
```

**✅ Good:** Split into focused components

```typescript
// ServerPage.tsx - Only orchestrates
export function ServerPage() {
  const { data: servers } = useQuery(['servers'], serversAPI.list);
  const mutation = useMutation({ mutationFn: serversAPI.create });
  
  return (
    <ServerList servers={servers}>
      <ServerForm 
        onSubmit={mutation.mutate} 
        onCancel={handleCancel}
      />
    </ServerList>
  );
}

// ServerList.tsx - Only displays list
export function ServerList({ servers, children }) {
  return (
    <div className="grid gap-4">
      {servers.map(s => <ServerCard key={s.id} server={s} />)}
      {children}
    </div>
  );
}

// ServerForm.tsx - Only handles form
export function ServerForm({ onSubmit, onCancel }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };
  // ... form logic only
}
```

### 2. Open/Closed Principle (OCP)

Open for extension, closed for modification.

**Pattern: Strategy for different authentication modes**

```typescript
// ❌ Anti-pattern - modify logic for each auth mode
export async function login(username, password) {
  if (useOIDC) {
    // OIDC logic
  } else {
    // Basic auth logic
  }
}

// ✅ Good - extend via strategy pattern
export interface AuthStrategy {
  login(username: string, password: string): Promise<AuthToken>;
  validate(): Promise<boolean>;
}

export class BasicAuthStrategy implements AuthStrategy {
  login(username, password) { /* ... */ }
}

export class OIDCAuthStrategy implements AuthStrategy {
  login(username, password) { /* ... */ }
}

// Usage - no modification needed for new auth types
const strategy = authConfig.mode === 'oidc' 
  ? new OIDCAuthStrategy(config) 
  : new BasicAuthStrategy();
const token = await strategy.login(username, password);
```

**Pattern: Traffic Trigger Scopes**

```typescript
// Extendable scope types
export type TrafficScope = 'peer' | 'server' | 'global';

// New scope can be added without modifying existing code
export async function evaluateTrigger(trigger: TrafficTrigger, metrics: Metrics) {
  switch (trigger.scope) {
    case 'peer':
      return evaluatePeerTrigger(trigger, metrics);
    case 'server':
      return evaluateServerTrigger(trigger, metrics);
    case 'global':
      return evaluateGlobalTrigger(trigger, metrics);
    default:
      console.warn(`Unknown scope: ${trigger.scope}`);
      return false;
  }
}
```

### 3. Liskov Substitution Principle (LSP)

Subtypes must be substitutable for base types.

**Example: Different metric types**

```typescript
// ✅ Good - consistent interface
export interface TrafficMetric {
  recorded_at: string;
  rx_bytes: number;
  tx_bytes: number;
  is_connected: boolean;
}

export type MetricsData = {
  servers: {
    total_rx_bytes: number;
    total_tx_bytes: number;
    top_servers: Array<{ id: number; name: string; rx_bytes: number; tx_bytes: number }>;
  };
  peers: {
    total_rx_bytes: number;
    total_tx_bytes: number;
    top_peers: Array<{ id: number; name: string; rx_bytes: number; tx_bytes: number }>;
  };
  timestamp: string;
};

// Both implement consistent structure
const handleMetricsUpdate = (data: MetricsData) => {
  // Can handle both servers and peers uniformly
  const totalTraffic = data.servers.total_rx_bytes + data.servers.total_tx_bytes;
  // ...
};
```

### 4. Interface Segregation Principle (ISP)

Clients should not be forced to depend on interfaces they don't use.

**❌ Bad - Fat interface**

```typescript
// Anti-pattern - WebSocket handles everything
export interface WebSocketHandler {
  onMetricsUpdate?(data: MetricsData);
  onNotification?(data: NotificationData);
  onServerStatusChange?(data: ServerStatusChangeData);
  onHealthUpdate?(data: HealthData);
  onPeerConnection?(data: PeerConnectionData);
  onIntegrationEvent?(data: IntegrationEventData);
  // Too many optional methods
}
```

**✅ Good - Separate focused interfaces**

```typescript
// Separate interfaces for different concerns
export interface MetricsWebSocketHandler {
  onMetricsUpdate(data: MetricsData): void;
}

export interface NotificationWebSocketHandler {
  onNotification(data: NotificationData): void;
}

export interface ServerStatusWebSocketHandler {
  onServerStatusChange(data: ServerStatusChangeData): void;
}

// Component subscribes only to what it needs
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { onMetricsUpdate, onNotification, onServerStatusChange, ... } = options;
  
  // Handle only subscribed events
}
```

### 5. Dependency Inversion Principle (DIP)

High-level modules should not depend on low-level modules.

**Pattern: Abstract away API details**

```typescript
// ❌ Bad - Direct API coupling
export function createServer(formData: ServerCreate) {
  return serversAPI.create(formData);
}

// ✅ Good - Abstract interface
export interface ServerService {
  create(data: ServerCreate): Promise<Server>;
  update(id: number, data: ServerUpdate): Promise<Server>;
  delete(id: number): Promise<void>;
  start(id: number): Promise<void>;
  stop(id: number): Promise<void>;
  reload(id: number): Promise<void>;
}

// Implementation
export class DefaultServerService implements ServerService {
  private api = serversAPI;
  
  async create(data: ServerCreate): Promise<Server> {
    return this.api.create(data);
  }
  
  // ... other methods
}

// Usage - can swap implementation
const serverService = new DefaultServerService();
const server = await serverService.create(formData);
```

**Pattern: Mock services for testing**

```typescript
// In tests
describe('ServerForm', () => {
  let mockServerService: MockServerService;
  
  beforeEach(() => {
    mockServerService = {
      create: jest.fn().mockResolvedValue({ id: 1, name: 'Test Server' }),
      // ... other mocked methods
    };
    
    // Mock implementation
    jest.mock('../services/ServerService', () => ({
      DefaultServerService: class Mock implements ServerService {
        async create(data) { return mockServerService.create(data); }
        // ...
      }
    }));
  });
});
```

---

## 🧪 Test Driven Development (TDD)

### TDD Workflow: Red-Green-Refactor

For every feature, follow these steps:

#### 1. RED Phase - Write Failing Test

**Example: Adding traffic trigger validation**

```typescript
// traffic_trigger_validation.test.ts

import { describe, it, expect } from 'vitest';
import { validateTrafficTrigger } from '../src/utils/trafficTriggerValidation';

describe('validateTrafficTrigger', () => {
  it('should reject trigger with invalid threshold (negative value)', () => {
    // 🟥 RED: Test should fail before implementation
    const trigger = {
      name: 'High Traffic Alert',
      scope: 'peer',
      peer_id: 1,
      direction: 'combined',
      threshold_bytes: -1000,  // Invalid
      window: 'last_hour',
      cooldown_minutes: 5,
      enabled: false,
      integration_ids: [],
    };
    
    expect(() => validateTrafficTrigger(trigger)).toThrow(
      'threshold_bytes must be a positive number'
    );
  });
});
```

Run tests: **FAILS** ❌

#### 2. GREEN Phase - Implement Minimum Code

```typescript
// src/utils/trafficTriggerValidation.ts

export function validateTrafficTrigger(trigger: TrafficTrigger): void {
  // 🟢 GREEN: Implement just enough to pass the test
  if (trigger.threshold_bytes < 0) {
    throw new Error('threshold_bytes must be a positive number');
  }
  
  if (trigger.window !== 'last_hour' && 
      trigger.window !== 'last_24_hours' && 
      trigger.window !== 'last_7_days' && 
      trigger.window !== 'last_30_days') {
    throw new Error('Invalid window value');
  }
  
  if (trigger.cooldown_minutes < 1) {
    throw new Error('cooldown_minutes must be at least 1');
  }
}
```

Run tests: **PASSES** ✅

#### 3. REFACTOR Phase - Improve Without Breaking

```typescript
// Now we can refactor with confidence

export function validateTrafficTrigger(trigger: TrafficTrigger): void {
  const validWindows = ['last_hour', 'last_24_hours', 'last_7_days', 'last_30_days'];
  
  // Extract validation concerns
  if (trigger.threshold_bytes < 0) {
    throw createValidationError('threshold_bytes must be a positive number');
  }
  
  if (!validWindows.includes(trigger.window)) {
    throw createValidationError('Invalid window value');
  }
  
  if (trigger.cooldown_minutes < MIN_COOLDOWN_MINUTES) {
    throw createValidationError(`cooldown_minutes must be at least ${MIN_COOLDOWN_MINUTES}`);
  }
}

// utils/errors.ts
export function createValidationError(message: string): Error {
  return new Error(`Traffic trigger validation error: ${message}`);
}

const MIN_COOLDOWN_MINUTES = 1;
```

Run tests: **STILL PASSES** ✅

### Test Organization

#### 1. Unit Tests (vitest)

Located in `backend/tests/` and `frontend/tests/`

```typescript
// backend/tests/services/server_service_test.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.server_service import ServerService

class TestServerService:
    @pytest.fixture
    def mock_wg_service(self):
        return MagicMock()
    
    @pytest.fixture
    def service(self, mock_wg_service):
        with patch('app.services.server_service.WireGuardService') as mock:
            mock.return_value = mock_wg_service
            return ServerService()
    
    def test_create_server(self, service, mock_wg_service):
        # Given
        server_data = {
            'name': 'Test Server',
            'listen_port': 51820,
            'endpoint': 'vpn.example.com',
            'public_key': 'test_pubkey',
            'private_key': 'test_privkey',
        }
        
        # When
        result = service.create(server_data)
        
        # Then
        assert result['name'] == 'Test Server'
        assert result['listen_port'] == 51820
        mock_wg_service.create_interface.assert_called_once()
```

#### 2. Integration Tests

Located in `backend/tests/integration/` and `frontend/e2e/`

```typescript
// frontend/e2e/traffic-trigger-validation.spec.ts
import { test, expect } from '@playwright/test';
import { gotoDashboard } from './helpers';

test.describe('Traffic Trigger Validation', () => {
  test.beforeEach(async ({ page }) => {
    await gotoDashboard(page);
  });

  test('should show validation error for negative threshold', async ({ page }) => {
    // Navigate to traffic triggers page
    await page.goto('/traffic-triggers');
    
    // Click "Create Trigger"
    await page.click('button:has-text("Create Trigger")');
    
    // Fill form with invalid data
    await page.fill('[name="threshold_bytes"]', '-1000');
    
    // Click Save
    await page.click('button:has-text("Save")');
    
    // Should show error
    await expect(page.locator('.error-message')).toContainText(
      'threshold_bytes must be a positive number'
    );
  });

  test('should accept valid trigger configuration', async ({ page }) => {
    await page.goto('/traffic-triggers');
    await page.click('button:has-text("Create Trigger")');
    
    // Fill valid form
    await page.fill('[name="name"]', 'High Traffic Alert');
    await page.fill('[name="threshold_bytes"]', '1000000');
    await page.fill('[name="cooldown_minutes"]', '5');
    
    await page.click('button:has-text("Save")');
    
    // Should succeed
    await expect(page.locator('.success-message')).toBeVisible();
  });
});
```

### Testing Guidelines

**1. Test Coverage Requirements**

- Backend: ≥ 80% coverage (enforced by CI)
- Frontend: ≥ 70% coverage
- Critical paths: 100% coverage

**2. Test Naming Convention**

```typescript
describe('ComponentName', () => {
  it('should [action] when [condition]', () => {
    // Good: it('should show error when threshold is negative')
  });
  
  it('should [action] and [expected result]', () => {
    // Good: it('should navigate to login when token expires')
  });
  
  it('[condition] should [action]', () => {
    // Good: it('when server is deleted should show confirmation')
  });
});
```

**3. Mocking Strategy**

```typescript
// ✅ Good - Mock external dependencies
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ServerForm from '../ServerForm';
import { serversAPI } from '../services/apiClient';

jest.mock('../services/apiClient', () => ({
  serversAPI: {
    create: jest.fn().mockResolvedValue({ id: 1, name: 'Test' }),
    getDefaults: jest.fn().mockResolvedValue({}),
  },
}));

describe('ServerForm', () => {
  it('should create server with valid data', async () => {
    const user = userEvent.setup();
    const { getByRole } = render(<ServerForm onSubmit={jest.fn} onCancel={jest.fn} />);
    
    await user.type(getByRole('textbox', { name: 'Server Name' }), 'Test Server');
    await user.click(getByRole('button', { name: 'Create Server' }));
    
    expect(serversAPI.create).toHaveBeenCalledWith({ name: 'Test Server' });
  });
});
```

**4. Integration Test Structure**

```typescript
// backend/tests/integration/server_integration_test.py
import pytest
from app.main import app
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

class TestServerEndpoints:
    def test_create_server_201(self, client):
        """Test creating a new server returns 201"""
        response = client.post('/servers', json={
            'name': 'Test Server',
            'listen_port': 51820,
            'endpoint': 'vpn.example.com',
            'public_key': 'pubkey',
            'private_key': 'privkey',
        })
        
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Server'
        assert 'id' in response.json()
    
    def test_create_server_400_invalid_port(self, client):
        """Test invalid port returns 400"""
        response = client.post('/servers', json={
            'name': 'Test',
            'listen_port': 99999,  # Invalid
            'endpoint': 'vpn.example.com',
            'public_key': 'pubkey',
            'private_key': 'privkey',
        })
        
        assert response.status_code == 400
```

---

## 🎨 Code Style Guidelines

### TypeScript/JavaScript

**Imports**
```typescript
// Group by: 1) React, 2) Services, 3) Utils, 4) Components, 5) Types
import React, { useState, useEffect } from 'react';
import { serversAPI, peersAPI } from '../services/apiClient';
import { validateEmail } from '../utils/validation';
import ServerCard from './ServerCard';
import type { Server } from '../types';
```

**Function Declarations**
```typescript
// Use arrow functions for callbacks, named functions for exports
export function createServerForm(initialData: ServerCreate): ServerForm {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };
  
  return (/* JSX */);
}

export const useServerMutation = () => {
  const mutation = useMutation({
    mutationFn: serversAPI.create,
  });
};
```

**Variable Naming**
```typescript
// Descriptive, imperative names
const serverData = { /* ... */ };
const isSubmitting = true;
const fieldErrors = { name: 'Name is required' };

// Avoid vague names
const data = { /* Bad - what data? */ };
const result = { /* Bad - what result? */ };
```

### Tailwind CSS Classes

**Consistent ordering**
```typescript
// Order: display → positioning → sizing → spacing → colors → typography → effects
className="flex items-center justify-center w-full h-full p-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg shadow-md hover:shadow-lg border border-gray-300 dark:border-gray-600"
```

**Dark mode support**
```typescript
// Always include dark: variant
className="bg-white dark:bg-gray-700 text-gray-900 dark:text-white"

// Conditional dark mode
const darkMode = useDarkMode();
className = darkMode 
  ? 'bg-gray-800 text-white' 
  : 'bg-white text-gray-900';
```

**Responsive design**
```typescript
// Mobile first, then desktop
className="text-sm md:text-base px-4 py-2"
className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
```

---

## 🐍 Backend Setup & Development (FastAPI)

### Prerequisites

- Python 3.8+
- pip package manager
- Git
- PostgreSQL, SQLite, or MySQL
- iptables/nftables/firewalld (optional)

### Virtual Environment Setup

**IMPORTANT:** The backend must use its own virtual environment in `backend/.venv`.

```bash
# 1. Create virtual environment
cd backend
python3 -m venv .venv

# 2. Activate the environment
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python -c "import fastapi; import uvicorn; print('✅ Backend dependencies installed')"
```

### Running the Backend

```bash
# Activate virtual environment
cd backend
source .venv/bin/activate

# Start the FastAPI server (add --reload for hot-reload during development)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Access the API documentation
# http://localhost:8000/docs (Swagger)
# http://localhost:8000/redoc (ReDoc)
```

> Note for AI agents: you may start the backend in the background from your shell
> when you need to test against it (`... &` or a background tool), but make sure
> the process is properly stopped when done (`pkill -f "uvicorn app.main"`).

### Using the CLI

```bash
# The CLI lives in backend/src/linguard_cli/
# It depends on the backend (FastAPI)

# Install the CLI
cd backend/src/linguard_cli
source ../.venv/bin/activate
pip install -e .

# Use the CLI
linguard --help
linguard completers ip
linguard servers list
```

### Backend Configuration

Create a `.env` file in the `backend/` directory:

```bash
# Database configuration
DATABASE_URL=sqlite:///./linguard.db
# DATABASE_URL=postgresql://user:password@localhost/linguard
# DATABASE_URL=mysql://user:password@localhost/linguard

# Security configuration
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OIDC configuration (optional)
USE_OIDC=false
OIDC_ISSUER_URL=https://your-oidc-provider.com
```

### Database Migrations

```bash
# Activate environment
cd backend
source .venv/bin/activate

# Create a new migration
alembic revision --autogenerate -m "your migration message"

# Apply migrations
alembic upgrade head

# Revert migration
alembic downgrade -1
```

### Testing the Backend

```bash
# Activate environment
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run specific tests
pytest tests/services/ -v

# Check code coverage
pytest --cov=app --cov-report=html
```

---

## 🚀 Development Workflow

### 1. Feature Development

```bash
# 1. Create feature branch
git checkout -b features/traffic-trigger-validation

# 2. Write failing tests first
npm test -- traffic-trigger-validation.test.ts  # Should fail

# 3. Implement feature
npm run dev

# 4. Make tests pass
npm test -- traffic-trigger-validation.test.ts  # Should pass

# 5. Refactor if needed
npm test -- traffic-trigger-validation.test.ts  # Should still pass

# 6. Commit with clear message
git add .
git commit -m "feat: add traffic trigger validation

- Implement threshold_bytes validation
- Add validation for window and cooldown_minutes
- Create error messages for validation failures
- Add integration tests for API endpoints"
```

### 2. Code Review Checklist

Before submitting PR:

- [ ] All tests pass (`npm test`, `pytest`)
- [ ] Test coverage meets requirements
- [ ] Code follows SOLID principles
- [ ] No console.log statements in production code
- [ ] Types are properly defined
- [ ] Error handling is comprehensive
- [ ] Documentation is updated
- [ ] No breaking changes (if applicable)
- [ ] Code is formatted (`ruff format`, `pnpm format`)

### 3. Git Conventions

**Branch naming**
```
features/feature-name            # New features
fixes/bugfix                      # Bug fixes
docs/update                        # Documentation
chore/task                         # Miscellaneous tasks
```

**Commit messages**
```
feat: add peer import functionality
fix: resolve timeout issue in metrics collection
docs: update deployment guide
refactor: extract validation logic to utility
test: add coverage for auth flow
```

**Scope conventions**
- Use `.` for singular nouns (user, server, peer)
- Use plural for collections (users, servers, peers)
- Use `-` to separate related items (create-user, update-server)

---

## 🐍 Backend Architecture (FastAPI)

### Directory Structure

```
backend/app/
├── api/                    # API endpoints (routers)
│   ├── auth.py            # Authentication endpoints
│   ├── servers.py         # Server CRUD endpoints
│   ├── peers.py           # Peer management endpoints
│   ├── settings.py        # Global settings
│   ├── audit.py           # Audit logging
│   ├── backup.py          # Backup/restore
│   ├── integrations.py    # Webhook integrations
│   ├── traffic_triggers.py # Traffic-based triggers
│   ├── plugins.py         # Plugin management
│   └── ...
├── core/                  # Core infrastructure
│   ├── config.py          # Application settings
│   ├── containers.py      # DI Container
│   ├── database.py        # Database setup
│   ├── security.py        # Security utilities
│   └── events.py          # Event bus
├── models/                # SQLAlchemy models
│   ├── server.py          # Server model
│   ├── peer.py            # Peer model
│   ├── integration.py     # Integration model
│   └── ...
├── schemas/               # Pydantic schemas
│   ├── server.py          # Server schemas
│   ├── peer.py            # Peer schemas
│   └── ...
├── services/              # Business logic
│   ├── wireguard.py       # WireGuard operations
│   ├── firewall.py        # Firewall management
│   ├── backup_service.py  # Backup logic
│   └── ...
├── plugins/               # Plugin system
└── utils/                 # Utilities
```

### Dependency Injection Container

Linguard uses `dependency_injector` for DI:

```python
# app/core/containers.py
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    """Application DI Container."""
    
    # Core Services - No dependencies
    ip_management_service = providers.Singleton(IPManagementService)
    dns_hierarchy_service = providers.Singleton(DNSHierarchyService)
    audit_service = providers.Singleton(AuditService)
    
    # Services with dependencies (injection order matters!)
    wireguard_service = providers.Singleton(
        WireGuardService,
        dns_hierarchy_service=dns_hierarchy_service,
        firewall_service=firewall_service,
    )
    
    integration_service = providers.Singleton(
        IntegrationService,
        notification_service=notification_service,
        plugin_manager=plugin_manager,
    )
```

**Rules:**
- Define services with NO dependencies first (Singletons)
- Define services WITH dependencies later, injecting singletons
- Order matters: dependencies must be defined before dependents
- Use `providers.Singleton` for stateful services

### API Router Registration

```python
# app/main.py
from fastapi import Depends, FastAPI
from .core.security import get_current_admin

app = FastAPI(title="Linguard API", version="1.0.0")

# Admin-gated routers (require admin role)
admin_deps = [Depends(get_current_admin)]

app.include_router(
    servers.router,
    prefix=f"/api/v1/servers",
    tags=["servers"],
    dependencies=admin_deps,  # Require admin
)

app.include_router(
    auth.router,
    prefix=f"/api/v1/auth",
    tags=["auth"],  # No dependencies - public
)

app.include_router(
    ws.router,
    tags=["websocket"],  # WebSocket (no dependencies)
)
```

### Service Layer Pattern

**❌ Bad:** Endpoint directly calling WireGuard operations

```python
# Anti-pattern - too coupled
@app.post("/servers")
async def create_server(data: ServerCreate, current_user: User = Depends(get_current_admin)):
    # Directly calling wireguard operations in endpoint
    wg_interface = wg.create_interface(data.public_key, data.private_key)
    server = Server(name=data.name, interface=wg_interface, ...)
    db.add(server)
    db.commit()
```

**✅ Good:** Endpoint delegates to service

```python
# ✅ Good - Service layer abstraction
class WireGuardService(Service):
    async def create_interface(
        self, 
        db: AsyncSession,
        public_key: str,
        private_key: str,
        listen_port: int,
        interface_name: str,
    ) -> Interface:
        """Create WireGuard interface with firewall rules."""
        # Business logic here
        ...

@app.post("/servers")
async def create_server(
    data: ServerCreate,
    current_user: User = Depends(get_current_admin),
    wireguard_service: WireGuardService = Annotated[
        WireGuardService,
        Depends(wireguard_service),
    ],
):
    # Delegate to service
    interface = await wireguard_service.create_interface(
        db,
        data.public_key,
        data.private_key,
        data.listen_port,
        f"wg{data.id}",
    )
    
    server = Server(name=data.name, interface=interface, ...)
    db.add(server)
    db.commit()
    return server
```

### Event Bus Pattern

```python
# app/core/events.py
from enum import Enum
from typing import Callable, Dict

class EventType(Enum):
    SERVER_STARTED = "server_started"
    SERVER_STOPPED = "server_stopped"
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"

class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, list] = {e: [] for e in EventType}
    
    async def subscribe(self, event_type: EventType, handler: Callable):
        self._handlers[event_type].append(handler)
    
    async def publish(self, event_type: EventType, payload: dict):
        for handler in self._handlers[event_type]:
            await handler({"event_type": event_type.value, "payload": payload})

# Usage in main.py
event_bus = EventBus()

# Subscribe to events
async def handle_server_start(event_data: dict):
    await broadcast_server_status_change(event_data)

event_bus.subscribe(EventType.SERVER_STARTED, handle_server_start)

# Publish when needed
await event_bus.publish(
    EventType.SERVER_STARTED,
    {"name": "Production Server", "status": "running"}
)
```

### Database Repository Pattern

```python
# app/services/repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Generic, TypeVar

T = TypeVar('T')

class Repository(Generic[T]):
    def __init__(self, model: type[T], db: AsyncSession):
        self.model = model
        self.db = db
    
    async def get(self, id: int) -> T | None:
        return await self.db.get(self.model, id)
    
    async def get_by_field(self, field: str, value: any) -> T | None:
        return await self.db.get(
            self.model,
            {field: value}
        )
    
    async def create(self, data: dict) -> T:
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
    
    async def delete(self, id: int) -> bool:
        obj = await self.get(id)
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
            return True
        return False

# Usage
class ServerRepository(Repository[Server]):
    pass

@app.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    repo: ServerRepository = Annotated[
        ServerRepository,
        Depends(lambda repo, db: ServerRepository(Server, db)),
    ],
):
    return await repo.delete(server_id)
```

### Pydantic Schemas

**Base schemas for validation:**

```python
# app/schemas/base.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional

class BaseSchema(BaseModel):
    class Config:
        from_attributes = True  # Eager mode for SQLAlchemy

class CreateSchema(BaseSchema):
    """Schema for creation (only writable fields)"""
    pass

class UpdateSchema(BaseSchema):
    """Schema for updates (partial)"""
    pass

class PaginatedResponse(BaseSchema):
    items: list
    total: int
    skip: int
    limit: int
```

**Server schemas:**

```python
# app/schemas/server.py
from .base import CreateSchema, UpdateSchema, PaginatedResponse
from .peer import PeerCreate, PeerUpdate

class ServerCreate(CreateSchema):
    name: str = Field(..., min_length=1, max_length=100)
    listen_port: int = Field(..., ge=1, le=65535)
    endpoint: str = Field(..., min_length=1)
    ipv4_address: Optional[str] = Field(None, pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/[0-2][0-9]{1,2}$')
    ipv6_address: Optional[str] = None
    autostart: bool = True
    description: Optional[str] = Field(None, max_length=500)

class ServerUpdate(UpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    listen_port: Optional[int] = Field(None, ge=1, le=65535)
    endpoint: Optional[str] = Field(None, min_length=1)
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    autostart: Optional[bool] = None
    description: Optional[str] = None
    # Note: public_key, private_key are read-only (not in update)

class ServerResponse(BaseSchema):
    id: int
    name: str
    listen_port: int
    endpoint: str
    public_key: str
    status: str
    # ... all fields
```

### Error Handling

```python
# app/core/exceptions.py
from fastapi import HTTPException

class ValidationError(HTTPException):
    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=400,
            detail={"type": "validation_error", "field": field, "message": message}
        )

class MultiFieldValidationError(HTTPException):
    def __init__(self, errors: dict):
        super().__init__(
            status_code=400,
            detail={"type": "multi_field_validation_error", "errors": errors}
        )

# Custom exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "detail": exc.detail,
            "message": exc.detail["message"]
        }
    )

@app.exception_handler(MultiFieldValidationError)
async def multi_field_validation_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "detail": exc.detail,
            "message": "Multiple validation errors occurred"
        }
    )
```

### Background Services

```python
# app/services/background_services.py
import asyncio
from typing import Callable

class BackgroundService:
    def __init__(self, name: str, interval: int):
        self.name = name
        self.interval = interval
        self._running = False
        self._task = None
    
    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
    
    async def _run_loop(self):
        while self._running:
            await self.execute()
            await asyncio.sleep(self.interval)
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

# Usage in main.py
_health_monitor = HealthMonitorService(check_interval_seconds=30)

@app.on_event("startup")
async def startup():
    await _health_monitor.start()

@app.on_event("shutdown")
async def shutdown():
    await _health_monitor.stop()

# Manual start/stop (for setup wizard)
async def start_background_monitors():
    await _health_monitor.start()
    await _interface_monitor.start()
    await _backup_cleanup.start()
```

### Authentication & Authorization

```python
# app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        raise credentials_exception

async def get_current_admin(current_user: str = Depends(get_current_user)):
    """Require admin role for this dependency"""
    user_data = await get_user_by_username(current_user)
    if user_data.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    return current_user
```

### Testing Backend

**Unit Tests:**

```python
# backend/tests/services/wireguard_service_test.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.wireguard import WireGuardService

class TestWireGuardService:
    @pytest.fixture
    def mock_dns_service(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_firewall_service(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_dns_service, mock_firewall_service):
        with patch('app.services.wireguard.DNSHierarchyService') as mock_dns, \
             patch('app.services.wireguard.FirewallService') as mock_fw:
            mock_dns.return_value = mock_dns_service
            mock_fw.return_value = mock_firewall_service
            return WireGuardService(
                dns_hierarchy_service=mock_dns_service,
                firewall_service=mock_firewall_service
            )
    
    async def test_create_interface(self, service, mock_dns_service, mock_firewall_service):
        # Given
        private_key = "test_private_key"
        public_key = "test_public_key"
        
        # When
        result = await service.create_interface(
            db=None,
            private_key=private_key,
            public_key=public_key,
            listen_port=51820,
            interface_name="wg0",
        )
        
        # Then
        assert result["public_key"] == public_key
        mock_dns_service.generate_unique_ip.assert_called_once()
        mock_firewall_service.setup_rules.assert_called_once()
```

**Integration Tests:**

```python
# backend/tests/integration/server_api_test.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

class TestServerEndpoints:
    def test_create_server_201(self, client, admin_token):
        """Test creating a new server returns 201"""
        response = client.post("/api/v1/servers", json={
            "name": "Test Server",
            "listen_port": 51820,
            "endpoint": "vpn.example.com",
            "public_key": "test_pubkey",
            "private_key": "test_privkey",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 201
        assert response.json()["name"] == "Test Server"
        assert "id" in response.json()
    
    def test_create_server_400_invalid_port(self, client, admin_token):
        """Test invalid port returns 400"""
        response = client.post("/api/v1/servers", json={
            "name": "Test",
            "listen_port": 99999,  # Invalid
            "endpoint": "vpn.example.com",
            "public_key": "pubkey",
            "private_key": "privkey",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 400
        assert "detail" in response.json()
```

---

## 📝 Quick Reference

### Common Patterns

**Form Submission**
```typescript
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  onSubmit(formData);
};
```

**Loading States**
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['servers'],
  queryFn: serversAPI.list,
});

if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorBoundary error={error} />;
```

**Optimistic Updates**
```typescript
const mutation = useMutation({
  mutationFn: serversAPI.update,
  onMutate: async (newServer) => {
    await queryClient.cancelQueries(['servers']);
    const previousServers = queryClient.getQueryData(['servers']);
    queryClient.setQueryData(['servers'], (old) => [...old, newServer]);
    return { previousServers };
  },
  onError: (err, newServer, context) => {
    queryClient.setQueryData(['servers'], context.previousServers);
  },
  onSettled: () => {
    queryClient.invalidateQueries(['servers']);
  },
});
```

**Error Handling**
```typescript
try {
  await serversAPI.create(serverData);
  toast.success('Server created successfully');
} catch (error) {
  const apiError = error as ApiError;
  if (apiError.code === 'VALIDATION_ERROR') {
    toast.error('Please correct the following errors');
    // Display field-specific errors
  } else {
    toast.error('Failed to create server. Please try again.');
  }
}
```

---

## 🔗 Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [React Patterns](https://react.dev/learn)
- [SOLID Principles](https://medium.com/@johncarlosbaez/solid-principles-in-plain-english-7f991d7f8b8c)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Zustand Documentation](https://github.com/pmndrs/zustand)
- [Linting & Formatting](https://linguard.readthedocs.io/en/stable/development.html)

---

*Last updated: October 11, 2026*
*Maintained by the Linguard community*
