# Linguard CLI - Quick Reference

## 🚀 Quick Start

```bash
# 1. Setup
cd backend
bash scripts/setup.sh

# 2. Activate
source backend/.venv/bin/activate

# 3. Use CLI
linguard --help
```

## 📋 Command Reference

### Authentication

```bash
# Login
linguard auth login

# Check status
linguard auth status

# Logout
linguard auth logout
```

### Servers

```bash
# List all servers
linguard servers list

# Create new server
linguard servers create \
  --name "MyServer" \
  --port 51820 \
  --endpoint vpn.example.com

# Use autocompletion
linguard servers create \
  --suggest-ip \
  --suggest-dns \
  --suggest-port

# Server operations
linguard servers start <id>
linguard servers stop <id>
linguard servers reload <id>
linguard servers delete <id>
```

### Peers

```bash
# List all peers
linguard peers list

# Create new peer
linguard peers create <server_id> \
  --name "Office Network" \
  --endpoint 192.168.1.100

# Use autocompletion for IP ranges
linguard peers create 1 \
  --suggest-range \
  --name "Home Device"

# Peer operations
linguard peers delete <id>
```

### Traffic Triggers

```bash
# List triggers
linguard traffic-triggers list

# Create trigger
linguard traffic-triggers create \
  --name "High Traffic Alert" \
  --scope peer \
  --peer-id 1 \
  --direction combined \
  --threshold-bytes 1000000 \
  --window last_hour

# Test trigger
linguard traffic-triggers test <id>

# Delete trigger
linguard traffic-triggers delete <id>
```

### Integrations

```bash
# List integrations
linguard integrations list

# Create integration
linguard integrations create \
  --name "Slack Notifications" \
  --type webhook \
  --url "https://hooks.slack.com/xxx" \
  --events "server_started,peer_connected"

# Delete integration
linguard integrations delete <id>
```

### Backups

```bash
# List backups
linguard backups list

# Create backup
linguard backups create --name "pre-update-backup"

# Restore from backup
linguard backups restore <backup_id>

# Delete backup
linguard backups delete <id>
```

### Notifications

```bash
# List notifications
linguard notifications list

# Mark all as read
linguard notifications mark-all-read

# Clear all notifications
linguard notifications clear-all
```

### Metrics

```bash
# Get traffic metrics
linguard metrics traffic \
  --scope global \
  --json

# Get server-specific metrics
linguard metrics traffic \
  --scope server \
  --server-id 1

# Get peer-specific metrics
linguard metrics traffic \
  --scope peer \
  --peer-id 5
```

### Status

```bash
# Check system status
linguard status system

# Run health check
linguard status health
```

## 🛠️ Autocompletion

### IP Addresses

```bash
# Show IP suggestions
linguard completers ip

# Show 20 suggestions
linguard completers ip -c 20

# Suggestions with prefix
linguard completers ip 192.168.1
```

### Subnets

```bash
# Show subnet suggestions
linguard completers subnet

# Class-specific subnets
linguard completers subnet --class A
linguard completers subnet --class B
linguard completers subnet --class C
```

### DNS Servers

```bash
# Show all DNS servers
linguard completers dns

# Specific provider
linguard completers dns --provider cloudflare
linguard completers dns --provider google
linguard completers dns --provider quad9
```

### Ports

```bash
# Show common WireGuard ports
linguard completers port

# Port range suggestions
linguard completers port -r 51820-65535
```

### Peer Names

```bash
# Show peer name suggestions
linguard completers peer

# With specific server port
linguard completers peer --server-port 51820
```

## 💡 Usage Examples

### Complete Server Setup

```bash
# Login
linguard auth login

# Create production server with suggestions
linguard servers create \
  --name "Production VPN" \
  --suggest-ip \
  --suggest-dns \
  --suggest-port \
  --endpoint vpn.company.com

# Start the server
linguard servers start 1

# Create peer for office
linguard peers create 1 \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# Create traffic trigger
linguard traffic-triggers create \
  --name "High Traffic Alert" \
  --scope peer \
  --peer-id 1 \
  --direction combined \
  --threshold-bytes 1000000 \
  --window last_hour

# Check system health
linguard status health
```

### Backup and Restore Workflow

```bash
# Create backup before updates
linguard backups create --name "pre-update-backup"

# List backups
linguard backups list

# Perform updates...

# Restore if needed
linguard backups restore <backup_id>
```

### Monitoring

```bash
# Check system health
linguard status health

# Monitor global traffic
linguard metrics traffic --scope global

# Watch notifications
linguard notifications list

# Clear old notifications
linguard notifications mark-all-read
```

## 🎨 Output Formats

### Text (default)

```bash
linguard servers list
```

Output:
```
Name           | Interface | Port     | Status
---------------|-----------|----------|----------
Production VPN | wg0       | 51820    | running
Staging Server | wg1       | 51821    | stopped
```

### JSON (for automation)

```bash
linguard servers list --json
```

Output:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Production VPN",
      "interface": "wg0",
      "listen_port": 51820,
      "status": "running"
    }
  ],
  "total": 1
}
```

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
export LINGUARD_API_URL="http://localhost:8000"
export LINGUARD_API_TOKEN="your-jwt-token-here"

# Or use .env file
```

### .env File

```bash
LINGUARD_API_URL=http://localhost:8000
LINGUARD_API_TOKEN=your-jwt-token-here
LINGUARD_DEBUG=true
```

## 🐛 Troubleshooting

### CLI Not Found

```bash
# Ensure venv is activated
source backend/.venv/bin/activate

# Verify CLI is installed
which linguard

# Reinstall CLI
cd backend/src/linguard_cli
pip install -e .
```

### Authentication Failed

```bash
# Clear token and login again
linguard auth logout
linguard auth login
```

### Cannot Connect to API

```bash
# Check backend is running
curl http://localhost:8000/health

# Verify API URL
echo $LINGUARD_API_URL

# Test connection
curl http://localhost:8000/api/v1/health
```

### Permission Denied

```bash
# Ensure you're using an admin account
linguard auth status

# Check user role
```

## 📚 Additional Resources

- [Complete Guide](GUIDE.md)
- [Examples](EXAMPLE_AUTOCOMPLETE.md)
- [API Documentation](http://localhost:8000/docs)
- [GitHub Repository](https://github.com/joseantmazonsb/linguard)

## 📊 Command Summary

| Command | Description |
|---------|-------------|
| `linguard auth login` | Login and get JWT token |
| `linguard servers list` | List all WireGuard servers |
| `linguard servers create` | Create new server |
| `linguard servers delete <id>` | Delete server |
| `linguard servers start <id>` | Start server |
| `linguard servers stop <id>` | Stop server |
| `linguard peers list` | List all peers |
| `linguard peers create <server_id>` | Create new peer |
| `linguard traffic-triggers list` | List traffic triggers |
| `linguard traffic-triggers create` | Create new trigger |
| `linguard integrations list` | List integrations |
| `linguard integrations create` | Create new integration |
| `linguard backups list` | List backups |
| `linguard backups create` | Create backup |
| `linguard backups restore <id>` | Restore from backup |
| `linguard notifications list` | List notifications |
| `linguard status system` | Show system info |
| `linguard status health` | Run health check |
| `linguard completers ip` | IP suggestions |
| `linguard completers subnet` | Subnet suggestions |
| `linguard completers dns` | DNS server suggestions |
| `linguard completers port` | Port suggestions |
| `linguard completers peer` | Peer name suggestions |

---

**Version:** 0.1.0  
**Last Updated:** 2024-10-11
