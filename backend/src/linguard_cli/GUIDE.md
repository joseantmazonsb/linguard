# Linguard CLI - Complete User Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Commands Reference](#commands-reference)
5. [Examples](#examples)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

---

## Quick Start

```bash
# Install
cd backend/src/linguard_cli
pip install -e .

# Login
linguard auth login

# List servers
linguard servers list

# Create server
linguard servers create --name "MyServer" --port 51820 --endpoint vpn.example.com

# Check system status
linguard status system
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Linguard FastAPI backend running on default port 8000

### Method 1: Install from source

```bash
cd backend/src/linguard_cli
pip install -e .
```

### Method 2: Install via pip (recommended)

```bash
pip install linguard-cli
```

### Verify installation

```bash
linguard --version
linguard --help
```

## Configuration

### Environment Variables

Create a `.env` file in your project directory:

```bash
# API Configuration
LINGUARD_API_URL=http://localhost:8000
LINGUARD_API_TOKEN=your-jwt-token-here

# Optional: Custom API endpoint
LINGUARD_API_URL=https://api.your-linguard-instance.com
```

### Getting Your JWT Token

```bash
linguard auth login

# The command will output your token and suggest saving it
```

### Manual Token Setup

```bash
export LINGUARD_API_TOKEN="your-token-here"
# Or add to .env file
echo "LINGUARD_API_TOKEN=your-token-here" >> .env
```

## Commands Reference

### Authentication

#### `linguard auth login`

Authenticate with the Linguard API and get a JWT token.

**Options:**
- Automatically prompts for username and password
- Outputs JWT token to console
- Offers to save to `.env` file

**Example:**
```bash
linguard auth login
# Enter username: admin
# Enter password: yourpassword
# Your token will be displayed
```

#### `linguard auth status`

Check current authentication status.

**Output:**
```
✓ Authentication successful!
  User: admin
  Email: admin@example.com
  Role: admin
```

#### `linguard auth logout`

Clear stored authentication token.

---

### Servers

#### `linguard servers list`

List all WireGuard servers.

**Options:**
- `--json` - Output in JSON format

**Example output:**
```
Found 2 server(s):

Name             | Interface | Port     | Status
-----------------|-----------|----------|----------
Production Server| wg0       | 51820    | running
Staging Server   | wg1       | 51821    | stopped
```

#### `linguard servers create`

Create a new WireGuard server.

**Options:**
- `--name` (required) - Server name
- `--port` (required) - Listen port (1-65535)
- `--endpoint` (required) - Server hostname/IP
- `--ipv4` - IPv4 address (e.g., 10.0.0.1/24)
- `--ipv6` - IPv6 address (e.g., fd00::1/64)
- `--dns-primary` - Primary DNS server
- `--dns-secondary` - Secondary DNS server
- `--autostart` - Enable autostart on boot
- `--description` - Server description

**Example:**
```bash
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint "vpn.company.com" \
  --ipv4 "10.0.0.1/24" \
  --ipv6 "fd00::1/64" \
  --dns-primary "1.1.1.1" \
  --dns-secondary "8.8.8.8" \
  --autostart \
  --description "Main production VPN server"
```

#### `linguard servers delete <server_id>`

Delete a WireGuard server.

**Confirmation:** Requires confirmation prompt.

**Example:**
```bash
linguard servers delete 1
# Are you sure you want to delete server 1? [y/N]: y
✓ Server 1 deleted successfully!
```

#### `linguard servers start <server_id>`

Start a WireGuard server.

**Example:**
```bash
linguard servers start 1
✓ Server 1 started successfully!
```

#### `linguard servers stop <server_id>`

Stop a WireGuard server.

**Example:**
```bash
linguard servers stop 1
✓ Server 1 stopped successfully!
```

#### `linguard servers reload <server_id>`

Reload server configuration without stopping.

**Example:**
```bash
linguard servers reload 1
✓ Server 1 reloaded successfully!
```

---

### Peers

#### `linguard peers list`

List all peers across all servers.

**Options:**
- `--json` - Output in JSON format

**Example output:**
```
Found 5 peer(s):

Name           | Server    | Endpoint    | Enabled | Status
---------------|-----------|-------------|---------|--------
Office Network | Server 1  | 192.168.1.1| ✓       | connected
Home Device    | Server 1  | 203.0.113.1| ✓       | connected
Backup Server  | Server 2  | 10.0.0.50  | ✓       | connected
```

#### `linguard peers create <server_id>`

Create a new peer for a specific server.

**Options:**
- `--name` (required) - Peer name
- `--endpoint` (required) - Peer public IP/hostname
- `--allowed-ips` - Allowed IPs (e.g., 192.168.1.0/24)
- `--ipv6` - IPv6 address
- `--port` (default: 51820) - Peer port
- `--dns-primary` - Primary DNS
- `--dns-secondary` - Secondary DNS
- `--preshared-key` - Pre-shared key (optional)
- `--persistent-keepalive` (default: 60) - Keepalive interval

**Example:**
```bash
linguard peers create 1 \
  --name "Office Network" \
  --endpoint "192.168.1.100" \
  --allowed-ips "192.168.1.0/24" \
  --preshared-key "your-pre-shared-key"
```

#### `linguard peers delete <peer_id>`

Delete a peer.

**Example:**
```bash
linguard peers delete 5
# Are you sure you want to delete peer 5? [y/N]: y
✓ Peer 5 deleted successfully!
```

---

### Traffic Triggers

#### `linguard traffic-triggers list`

List all traffic triggers.

**Example output:**
```
Found 3 trigger(s):

✓ High Traffic Alert
     Scope: peer | Status: enabled
✓ Low Traffic Warning
     Scope: server | Status: enabled
✓ Global Alert
     Scope: global | Status: disabled
```

#### `linguard traffic-triggers create`

Create a new traffic trigger.

**Options:**
- `--name` (required) - Trigger name
- `--scope` (required) - peer/server/global
- `--peer-id` - Peer ID (for peer scope)
- `--server-id` - Server ID (for server scope)
- `--direction` (required) - rx/tx/combined
- `--threshold-bytes` (required) - Threshold in bytes
- `--window` (required) - Time window (last_hour, last_24_hours, etc.)
- `--cooldown-minutes` (default: 5) - Cooldown period
- `--integration-ids` - Comma-separated integration IDs

**Example:**
```bash
linguard traffic-triggers create \
  --name "High Traffic Alert" \
  --scope peer \
  --peer-id 1 \
  --direction combined \
  --threshold-bytes 1000000 \
  --window last_hour \
  --cooldown-minutes 5
```

#### `linguard traffic-triggers delete <trigger_id>`

Delete a traffic trigger.

#### `linguard traffic-triggers test <trigger_id>`

Test a traffic trigger to see if it would trigger.

**Example:**
```bash
linguard traffic-triggers test 1
✓ Trigger test completed!
  Result: passed
  Triggered: false
```

---

### Integrations

#### `linguard integrations list`

List all integrations (webhooks, notifications, etc.).

**Example output:**
```
Found 4 integration(s):

✓ Slack Notifications
     Type: notification | Events: 5
✓ Webhook Endpoint
     Type: webhook | Events: 3
✓ Email Alerts
     Type: email | Events: 2
```

#### `linguard integrations create`

Create a new integration.

**Options:**
- `--name` (required) - Integration name
- `--type` (required) - webhook/notification/email
- `--url` - Webhook URL
- `--events` - Comma-separated event types

**Example:**
```bash
linguard integrations create \
  --name "Slack Notifications" \
  --type webhook \
  --url "https://hooks.slack.com/services/xxx" \
  --events "server_started,peer_connected,peer_disconnected"
```

#### `linguard integrations delete <integration_id>`

Delete an integration.

---

### Notifications

#### `linguard notifications list`

List all notifications.

**Example output:**
```
Found 10 notification(s) (3 unread)

✓ [2024-01-15 10:30:00] Server restarted successfully
✗ [2024-01-15 09:15:00] Peer connection failed
✗ [2024-01-15 08:00:00] Configuration saved
```

#### `linguard notifications mark-all-read`

Mark all notifications as read.

#### `linguard notifications clear-all`

Clear all notifications (requires confirmation).

---

### Metrics

#### `linguard metrics traffic`

Get traffic metrics.

**Options:**
- `--scope` (required) - peer/server/global
- `--server-id` - Server ID (for server scope)
- `--peer-id` - Peer ID (for peer scope)
- `--json` - Output in JSON format

**Examples:**

Get global traffic:
```bash
linguard metrics traffic --scope global
```

Get server-specific traffic:
```bash
linguard metrics traffic --scope server --server-id 1
```

Get peer-specific traffic:
```bash
linguard metrics traffic --scope peer --peer-id 5
```

---

### Status

#### `linguard status system`

Show system information and status.

**Example output:**
```
Component      | Status
---------------|---------
WireGuard      | Installed
IP Forwarding  | Enabled
Firewall       | Configured
Default Interface | eth0
```

#### `linguard status health`

Run comprehensive health check.

**Example output:**
```
✓ System Health Check
  Overall Status: healthy

Component Status:
Component          | Status
-------------------|---------
Database           | Healthy
WireGuard          | Healthy
IP Forwarding      | Healthy
Firewall           | Healthy
Default Interface  | Healthy
```

---

## Examples

### Complete Server Setup

```bash
# Login
linguard auth login

# Check current servers
linguard servers list

# Create new production server
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint "vpn.company.com" \
  --ipv4 "10.0.0.1/24" \
  --ipv6 "fd00::1/64" \
  --dns-primary "1.1.1.1" \
  --dns-secondary "8.8.8.8" \
  --autostart \
  --description "Main production WireGuard server"

# Start the server
linguard servers start 1

# Create peers
linguard peers create 1 \
  --name "Office Network" \
  --endpoint "192.168.1.100" \
  --allowed-ips "192.168.1.0/24"

linguard peers create 1 \
  --name "Home Device" \
  --endpoint "203.0.113.50" \
  --ipv6 "fd00::100/128"

# Create traffic trigger
linguard traffic-triggers create \
  --name "High Traffic Alert" \
  --scope peer \
  --peer-id 1 \
  --direction combined \
  --threshold-bytes 1000000 \
  --window last_hour \
  --cooldown-minutes 5

# Check system health
linguard status health
```

### Backup and Restore

```bash
# Create backup
linguard backups create --name "pre-update-backup"

# List backups
linguard backups list

# Keep only last 3 backups (manual cleanup)
linguard backups list --json | jq '.items[-3:]'
```

### Monitoring

```bash
# Check system health
linguard status health

# Monitor traffic
linguard metrics traffic --scope global

# Watch notifications
linguard notifications list
```

## Troubleshooting

### Common Issues

#### 1. "No module named 'linguard_cli'"

**Solution:**
```bash
cd backend/src/linguard_cli
pip install -e .
```

#### 2. "Authentication failed"

**Possible causes:**
- Token expired
- Wrong credentials
- API server down

**Solutions:**
```bash
# Check API is running
curl http://localhost:8000/health

# Clear token and login again
linguard auth logout
linguard auth login
```

#### 3. "Cannot connect to API"

**Check:**
```bash
# Test connection
curl http://localhost:8000/api/v1/health

# Check if server is running
ps aux | grep uvicorn

# Check logs
tail -f backend/logs/app.log
```

#### 4. "Invalid token"

**Solution:**
```bash
# Clear token
linguard auth logout

# Re-authenticate
linguard auth login
```

#### 5. "Permission denied"

**Solution:**
- Ensure you're using an admin account
- Check user role in Linguard settings
- Verify token has admin privileges

### Debug Mode

Enable debug output:

```bash
# Export debug flag
export DEBUG=1

# Or run directly
LINGUARD_DEBUG=1 linguard servers list
```

### Checking API Logs

```bash
# View backend logs
tail -f backend/logs/app.log

# Search for errors
grep "ERROR" backend/logs/app.log
```

## FAQ

### Q: How do I reset my password?

A: Use the Linguard web interface to reset your password, then login again with the CLI.

### Q: Can I use the CLI without the web interface?

A: Yes, the CLI is fully independent. You only need the FastAPI backend running.

### Q: Where are backups stored?

A: By default, backups are stored in the `data/backups/` directory (configurable in settings).

### Q: Can I backup multiple servers at once?

A: Yes, use `linguard backups create` to create a backup that includes all servers.

### Q: How do I export server configuration?

A: The CLI will automatically generate the configuration when you create a server. You can also use the web interface.

### Q: Can I use the CLI on different operating systems?

A: Yes, the CLI is cross-platform and works on Linux, macOS, and Windows (with WSL or Git Bash).

### Q: What happens if the API server is restarted?

A: You may need to re-authenticate. The CLI stores the token, but it can expire.

### Q: How do I update Linguard?

A: Use the update checker or follow the official update procedure. The CLI doesn't handle updates directly.

### Q: Can I automate tasks with the CLI?

A: Yes! You can use it in scripts:

```bash
#!/bin/bash
linguard auth login > /dev/null
linguard servers list --json > servers.json
linguard status health
```

### Q: What's the difference between `stop` and `reload`?

A: 
- `stop`: Completely stops the WireGuard interface
- `reload`: Restarts the interface without fully stopping (faster)

### Q: Can I manage peers across multiple servers?

A: Yes, `linguard peers list` shows all peers from all servers. When creating a peer, specify the server ID.

---

## Additional Resources

- [Linguard Documentation](https://linguard.readthedocs.io)
- [GitHub Repository](https://github.com/joseantmazonsb/linguard)
- [API Documentation](http://localhost:8000/docs)
- [Issue Tracker](https://github.com/joseantmazonsb/linguard/issues)

## License

MIT License - see LICENSE file

---

**Version:** 0.1.0
**Last Updated:** 2024-10-11
