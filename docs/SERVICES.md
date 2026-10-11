# System Services

## Overview

Linguard includes several background services for monitoring, maintenance, and operational tasks. These services run independently of the main API server.

## Available Services

### 1. Interface Monitor Service

**Purpose:** Monitors WireGuard interface status and health.

**Configuration:**
- Check interval: 10 seconds (configurable)
- Monitors: Interface state, peer connections, traffic

**Location:** `app/services/interface_monitor.py`

### 2. Health Monitor Service

**Purpose:** Tracks overall system health and application status.

**Features:**
- Checks application readiness
- Monitors database connectivity
- Tracks service availability

**Configuration:**
- Check interval: 30 seconds
- Logs health status changes

**Location:** `app/services/health_monitor_service.py`

### 3. Firewall Service

**Purpose:** Manages firewall operations and enforces network policies.

**Features:**
- Driver detection (iptables, nftables, etc.)
- Command execution with timeout protection
- Password prompt prevention

**Requirements:**
- iptables or nftables installed
- Passwordless sudo configured

**Location:** `app/services/firewall/service.py`

### 4. Interface Monitor

**Purpose:** Monitors network interfaces for WireGuard configuration.

**Check Interval:** 10 seconds

**Location:** `app/services/interface_monitor.py`

### 5. Backup Cleanup Service

**Purpose:** Automatically removes old backup files to prevent disk space issues.

**Configuration:**
- Run interval: 24 hours
- Cleanup policy: Configurable retention period

**Location:** `app/services/backup_cleanup_service.py`

### 6. Periodic Backup Service

**Purpose:** Creates regular backups of WireGuard configurations.

**Features:**
- Scheduled backups
- Automatic retention management
- Backup location: Configurable

**Location:** `app/services/periodic_backup_service.py`

### 7. Metrics Monitor Service

**Purpose:** Collects and stores system metrics for visualization.

**Features:**
- Traffic monitoring
- Interface statistics
- System resource usage

**Location:** `app/services/metrics_monitor_service.py`

### 8. Update Checker Service

**Purpose:** Checks for new versions and security updates.

**Configuration:**
- Check interval: 6 hours
- Non-blocking operation

**Location:** `app/services/update_checker.py`

## Service Architecture

### Dependency Injection

All services use dependency injection for configuration and database access:

```python
from app.container import get_container

def get_health_monitor():
    container = get_container()
    return container.health_monitor_service()
```

### Background Execution

Services run as background tasks using Python's asyncio:

```python
async def start_background_monitors():
    """Start all background monitoring services."""
    _interface_monitor = app.container.interface_monitor_service()
    _health_monitor = app.container.health_monitor_service()
    # ... other services
```

## Configuration

### Environment Variables

Most services can be configured via environment variables:

```bash
# Health monitor check interval (seconds)
HEALTH_MONITOR_INTERVAL=30

# Interface monitor check interval (seconds)
INTERFACE_MONITOR_INTERVAL=10

# Backup retention days
BACKUP_RETENTION_DAYS=30

# Metrics collection interval (seconds)
METRICS_INTERVAL=60
```

### Database Integration

All services use the same database session as the main application:

```python
from app.db.session import get_db

async def backup_configurations(db: Session = Depends(get_db)):
    # Access database through dependency injection
    pass
```

## Service Lifecycle

### Startup Order

Services start in the following order during application initialization:

1. Firewall service (detects driver)
2. Interface monitor
3. Health monitor
4. Backup cleanup service
5. Periodic backup service
6. Metrics monitor service
7. Update checker

### Graceful Shutdown

All services are properly cleaned up on application shutdown:

```python
async def lifespan_shutdown(app):
    """Stop all background services on shutdown."""
    await stop_all_monitors()
```

## Monitoring and Logging

### Log Levels

Services use standard Python logging with configurable levels:

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Debug information")
logger.info("Informational message")
logger.warning("Warning condition")
logger.error("Error occurred")
logger.critical("Critical failure")
```

### Log Output

Logs are written to:
- Console (stdout)
- Application log files (if configured)

### Health Status

Services report their status via the `/health` endpoint:

```json
{
  "status": "healthy",
  "services": {
    "interface_monitor": "healthy",
    "health_monitor": "healthy",
    "firewall": "healthy"
  }
}
```

## Testing Services

### Unit Testing

```python
import pytest
from app.services.health_monitor_service import HealthMonitorService

def test_health_monitor_startup():
    """Test that health monitor initializes correctly."""
    service = HealthMonitorService()
    assert service is not None
```

### Integration Testing

```python
def test_interface_monitor_with_real_interface():
    """Test interface monitoring with actual WireGuard interface."""
    with TestClient(app) as client:
        response = client.get("/api/v1/interfaces")
        assert response.status_code == 200
```

## Performance Considerations

### Resource Usage

- **Memory:** Services use minimal memory (< 50MB total)
- **CPU:** Background checks are non-blocking
- **Database:** Connection pooling prevents excessive queries

### Optimization Tips

1. Increase check intervals for less critical services
2. Disable metrics collection if not needed
3. Configure appropriate backup retention periods
4. Use efficient database queries

## Troubleshooting

### Service Not Starting

**Problem:** Service fails to initialize during startup.

**Solutions:**
1. Check logs for specific error messages
2. Verify database connectivity
3. Ensure required dependencies are installed
4. Check file permissions for backup directories

### High CPU Usage

**Problem:** Services consume excessive CPU.

**Solutions:**
1. Increase check intervals
2. Disable unnecessary services
3. Check for infinite loops in code
4. Monitor database query performance

### Service Timing Out

**Problem:** Service operations timeout.

**Solutions:**
1. Increase timeout values
2. Check network connectivity
3. Verify firewall rules aren't blocking operations
4. Monitor system resources

## Security Considerations

1. **Authentication:** All services run with application user context
2. **Authorization:** Services respect user permissions
3. **Data Protection:** Sensitive data is encrypted before storage
4. **Audit Logging:** All actions are logged for security auditing

## Future Enhancements

Planned improvements for services:

- [ ] Configurable service intervals via UI
- [ ] Service health dashboard
- [ ] Automated service restart on failure
- [ ] Advanced metrics collection
- [ ] Plugin system for custom services
- [ ] Service dependency management
