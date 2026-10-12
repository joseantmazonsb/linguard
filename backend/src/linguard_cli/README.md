# Linguard CLI

Command Line Interface to manage WireGuard servers with Linguard.

## 🚀 Features

- ✅ Full WireGuard server management
- ✅ Peer management with IP autocomplete
- ✅ Traffic triggers for monitoring
- ✅ Integrations and webhooks
- ✅ Backups and restore
- ✅ Metrics and monitoring
- ✅ Notification system
- ✅ **Smart IP autocomplete** (private ranges, subnets)
- ✅ **DNS suggestions** (Cloudflare, Google, Quad9)
- ✅ **Port suggestions** (WireGuard defaults, HTTPS)
- ✅ **Peer name suggestions**
- ✅ **Subnet and IP range suggestions**
- ✅ Formatted table output
- ✅ Colors and formatting for better UX
- ✅ JSON output for automation
- ✅ Secure JWT authentication

## 📦 Installation

### Method 1: Install with pip directly

```bash
cd backend/src/linguard_cli
pip install -e .
```

### Method 2: Install from linguard

```bash
cd backend
pip install -r requirements.txt
pip install -e src/linguard_cli
```

## Configuration

### Environment Variables

```bash
export LINGUARD_API_URL="http://localhost:8000"
export LINGUARD_API_TOKEN="your-jwt-token-here"
```

Or create a `.env` file:

```bash
LINGUARD_API_URL=http://localhost:8000
LINGUARD_API_TOKEN=your-jwt-token-here
```

## 📖 Documentation

For a complete guide with detailed examples, see [GUIDE.md](GUIDE.md)

## 🎯 Quick Commands

```bash
# Log in
linguard auth login

# List servers
linguard servers list

# Create a server
linguard servers create --name my-server --port 51820 --endpoint vpn.example.com

# List peers
linguard peers list

# Create a peer
linguard peers create 1 --name my-peer --endpoint 203.0.113.1

# Create a backup
linguard backups create

# Show system status
linguard status system
```

## Available Commands

### Authentication

- `linguard auth login` - Log in and get a token
- `linguard auth status` - Check authentication status
- `linguard auth logout` - Clear the token

### Servers

- `linguard servers list` - List all servers
- `linguard servers create` - Create a new server
- `linguard servers delete` - Delete a server
- `linguard servers start` - Start a server
- `linguard servers stop` - Stop a server
- `linguard servers reload` - Reload configuration

### Peers

- `linguard peers list` - List all peers
- `linguard peers create` - Create a new peer
- `linguard peers delete` - Delete a peer

### Backups

- `linguard backups list` - List backups
- `linguard backups create` - Create a backup

### Status

- `linguard status system` - System information
- `linguard status health` - Health check

## 🛠️ Smart Autocomplete

The CLI includes an autocomplete system to make network configuration easier.

### Autocomplete Commands

```bash
# IP address suggestions
linguard completers ip
linguard completers ip -c 20          # Show 20 suggestions
linguard completers ip 192.168.1      # Suggestions with a prefix

# Subnet suggestions
linguard completers subnet
linguard completers subnet 192.168.1.0

# DNS suggestions
linguard completers dns
linguard completers dns --provider cloudflare
linguard completers dns --provider google
linguard completers dns --provider cloud

# Port suggestions
linguard completers port
linguard completers port -r 51820-65535  # Port range

# Peer name suggestions
linguard completers peer
linguard completers peer --server-port 51820
```

### Using --suggest

```bash
# Suggest IPs automatically
linguard servers create --suggest-ip --name "Server" --endpoint example.com

# Suggest IP ranges
linguard peers create 1 --suggest-range --name "Peer"

# Combine suggestions
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Prod Server" --endpoint vpn.example.com
```

### Practical Examples

```bash
# See common IP suggestions
linguard completers ip

# See private subnet suggestions
linguard completers subnet

# See Cloudflare DNS suggestions
linguard completers dns --provider cloudflare

# See WireGuard port suggestions
linguard completers port

# See peer name suggestions
linguard completers peer
```

## 🎯 Quick Commands

```bash
# Log in
linguard auth login

# List servers as a table
linguard servers list

# Create a server
linguard servers create --name "MyServer" --port 51820 --endpoint vpn.example.com

# Manage servers
linguard servers start 1
linguard servers stop 1
linguard servers reload 1

# Manage peers
linguard peers create 1 --name "Office" --endpoint 192.168.1.100
linguard peers list

# Traffic triggers
linguard traffic-triggers list
linguard traffic-triggers create --name "Alert" --scope peer --peer-id 1 --direction combined --threshold-bytes 1000000 --window last_hour

# Integrations
linguard integrations list
linguard integrations create --name "Slack" --type webhook --url "https://hooks.slack.com/xxx"

# Notifications
linguard notifications list
linguard notifications mark-all-read

# Metrics
linguard metrics traffic --scope global

# System status
linguard status system
linguard status health
```

## 📁 Full Server Creation

### Create a complete server

```bash
linguard servers create \
  --name "Production Server" \
  --port 51820 \
  --endpoint "vpn.example.com" \
  --ipv4 "10.0.0.1/24" \
  --ipv6 "fd00::1/64" \
  --dns-primary "1.1.1.1" \
  --dns-secondary "8.8.8.8" \
  --autostart \
  --description "Production WireGuard Server"
```

### Manage servers

```bash
# List servers
linguard servers list

# Start a server
linguard servers start 1

# Stop a server
linguard servers stop 1

# Reload configuration
linguard servers reload 1
```

### Create a peer

```bash
linguard peers create \
  1 \
  --name "Office Network" \
  --endpoint "192.168.1.100" \
  --allowed-ips "192.168.1.0/24" \
  --preshared-key "your-pre-shared-key"
```

## 📁 Project Structure

```
backend/src/linguard_cli/
├── __init__.py           # Package initialization
├── __main__.py           # Entry point
├── main.py               # CLI implementation (1000+ lines)
├── requirements.txt      # Dependencies
├── setup.py             # Installation script
├── test_cli.py          # Basic syntax test
├── README.md            # This file
└── GUIDE.md             # Complete documentation
```

## 🎨 UX Improvements

To get JSON output, use the `--json` option:

```bash
linguard servers list --json
```

## Requirements

- Python 3.8+
- Running Linguard FastAPI backend
- Valid authentication token

## Contributing

1. Clone the repository
2. Create a feature branch
3. Implement your changes
4. Test your code
5. Submit a Pull Request

## License

MIT License - see LICENSE file
