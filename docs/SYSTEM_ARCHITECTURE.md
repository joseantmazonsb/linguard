# System Architecture

## Overview

Linguard is a modern web application built with FastAPI for the backend and React with Vite for the frontend. It provides a comprehensive management interface for WireGuard VPN servers.

## Technology Stack

### Backend

- **Framework:** FastAPI (async, Python 3.8+)
- **Database:** SQLAlchemy ORM with async support
- **Database Engines:** PostgreSQL, SQLite, MySQL
- **Validation:** Pydantic v2
- **Authentication:** JWT tokens, bcrypt password hashing, OIDC SSO
- **Task Queue:** Python asyncio for background tasks
- **API Documentation:** Auto-generated Swagger UI and ReDoc

### Frontend

- **Framework:** React 18+
- **Build Tool:** Vite
- **Language:** TypeScript
- **UI Components:** Radix UI, shadcn/ui
- **State Management:** React hooks
- **HTTP Client:** Fetch API with Axios fallback

### Infrastructure

- **Process Manager:** uvicorn (ASGI server)
- **Dependency Injection:** Dependency Injector
- **Logging:** Python logging module
- **Testing:** pytest, pytest-asyncio

## Application Structure

### Backend (`backend/app/`)

```
app/
├── api/                 # API endpoint handlers
│   ├── auth.py         # Authentication (JWT, OIDC)
│   ├── interface.py    # WireGuard interface management
│   ├── peer.py         # Peer management
│   ├── system.py       # System monitoring
│   └── plugins.py      # Plugin system
├── core/               # Core application configuration
│   ├── config.py       # Settings and configuration
│   ├── security.py     # Security utilities (password hashing, etc.)
│   └── dependencies.py # Dependency definitions
├── db/                 # Database layer
│   ├── session.py      # Database session management
│   ├── base.py         # Base model definition
│   └── models.py       # SQLAlchemy models
├── services/           # Background services
│   ├── firewall/       # Firewall management (iptables)
│   ├── health_monitor_service.py
│   ├── interface_monitor_service.py
│   ├── backup_cleanup_service.py
│   ├── periodic_backup_service.py
│   ├── metrics_monitor_service.py
│   └── update_checker.py
├── utils/              # Utility functions
│   ├── validation.py   # Input validation
│   └── helpers.py      # Helper functions
└── main.py             # Application entry point
```

### Frontend (`frontend/src/`)

```
src/
├── components/         # Reusable React components
│   ├── ui/            # Base UI components
│   ├── wireguard/     # WireGuard-specific components
│   └── layout/        # Layout components
├── pages/             # Page components
│   ├── auth/          # Authentication pages
│   ├── dashboard/     # Dashboard pages
│   ├── interfaces/    # Interface management
│   ├── peers/         # Peer management
│   └── settings/      # Settings pages
├── services/          # API service layer
│   ├── auth.service.ts
│   ├── interface.service.ts
│   ├── peer.service.ts
│   └── system.service.ts
├── hooks/             # Custom React hooks
├── types/             # TypeScript type definitions
├── utils/             # Utility functions
└── App.tsx            # Root application component
```

## Data Flow

### API Requests

1. Client sends HTTP request to API endpoint
2. FastAPI validates request and authentication
3. Dependency injection provides required dependencies
4. Business logic processes the request
5. Response is serialized to JSON
6. Response is sent back to the client

### Background Services

1. Services are initialized during application startup
2. Services run as async background tasks
3. Services use dependency injection for database access
4. Services log their activities for monitoring
5. Services can be stopped gracefully on shutdown

### Database Operations

1. Database session is created via dependency injection
2. SQLAlchemy models are used for data access
3. Async operations are supported for better performance
4. Transactions are managed automatically
5. Sessions are properly closed on completion

## Authentication Flow

### JWT Authentication

1. User provides credentials
2. Server validates credentials
3. JWT token is generated with user claims
4. Token is returned to client
5. Client includes token in Authorization header
6. Server validates token on protected routes

### OIDC SSO (OpenID Connect)

1. User is redirected to OIDC provider
2. User authenticates with OIDC provider
3. OIDC provider redirects back with ID token
4. Server validates ID token
5. JWT token is generated from ID token claims
6. User is logged in

## Service Architecture

### Background Services

Services are implemented as singleton instances using dependency injection:

```python
class HealthMonitorService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self._running = False
    
    async def start(self):
        """Start the health monitor service."""
        self._running = True
        while self._running:
            await self.check_health()
            await asyncio.sleep(self.settings.HEALTH_MONITOR_INTERVAL)
    
    async def stop(self):
        """Stop the health monitor service."""
        self._running = False
```

### Dependency Injection

Services and endpoints use dependency injection for testability and flexibility:

```python
from dependency_injector import containers, providers

class DatabaseContainer(containers.DeclarativeContainer):
    database = providers.AsyncSession()
    
    @providers.Singleton()
    def get_db(self):
        engine = create_async_engine(get_settings().DATABASE_URL)
        return providers.AsyncSession(engine, expire_on_commit=False)
```

## Monitoring and Observability

### Logging

- All services use Python's logging module
- Log levels are configurable (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Logs include timestamps, loggers, and message levels
- Structured logging is supported

### Health Checks

- `/health` endpoint provides application health status
- Individual services report their status
- Database connectivity is monitored
- Service dependencies are checked

### Metrics

- System metrics are collected (CPU, memory, disk)
- Network traffic is monitored for WireGuard interfaces
- Metrics are stored in the database for visualization
- Metrics collection can be configured or disabled

## Security Considerations

### Authentication

- JWT tokens are signed with a secret key
- Tokens have expiration times
- Passwords are hashed with bcrypt
- OIDC integration for enterprise SSO

### Authorization

- Role-based access control (RBAC)
- Permission checks on API endpoints
- Resource-level authorization

### Data Protection

- WireGuard configurations are encrypted (AES)
- User credentials are encrypted at rest
- Sensitive data is never logged

## Performance Optimization

### Database

- Connection pooling for efficient connections
- Async operations for non-blocking I/O
- Query optimization and indexing
- Lazy loading for large datasets

### API

- Async endpoints for concurrent requests
- Response caching where applicable
- Efficient data serialization
- Minimal dependencies

### Frontend

- Code splitting for faster load times
- Lazy loading of components
- Optimized bundle sizes
- Efficient re-renders

## Scalability

### Horizontal Scaling

- Stateless API design allows multiple instances
- Database connection pooling supports multiple connections
- Frontend can be served via CDN

### Vertical Scaling

- Efficient resource usage
- Async I/O for better throughput
- Database query optimization

## Deployment Patterns

### Development

- Run uvicorn with `--reload` for hot reloading
- Use SQLite for quick testing
- Disable firewall for development
- Enable DEBUG mode

### Production

- Use PostgreSQL for production database
- Enable HTTPS with TLS certificates
- Configure proper firewall rules
- Disable DEBUG mode
- Use strong SECRET_KEY
- Enable rate limiting
- Set up monitoring and logging

### Docker

- Multi-stage Docker builds for small images
- Docker Compose for local development
- Production-ready Dockerfile with security best practices

## Testing Strategy

### Unit Tests

- Test individual functions and classes
- Mock external dependencies
- Fast and isolated tests

### Integration Tests

- Test API endpoints with test database
- Test service interactions
- Test authentication flows

### E2E Tests

- Test complete user workflows
- Test with real database
- Test with actual WireGuard interfaces

## Future Improvements

### Planned Features

- [ ] GraphQL API support
- [ ] WebSocket for real-time updates
- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom integrations
- [ ] Multi-tenant support
- [ ] CLI tool for command-line management
- [ ] Kubernetes deployment support
- [ ] Terraform provider for infrastructure as code

### Technical Debt

- [ ] Refactor service initialization
- [ ] Improve error messages
- [ ] Add more comprehensive documentation
- [ ] Upgrade dependencies
- [ ] Add more test coverage
- [ ] Optimize database queries
