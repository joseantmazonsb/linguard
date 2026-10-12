# Linguard CLI Autocomplete Examples

## 🎯 Introduction

The Linguard CLI autocomplete system helps you set up your WireGuard network quickly, without having to remember IP addresses, subnet ranges, DNS servers and more.

## 📦 Installation

```bash
cd backend/src/linguard_cli
pip install -e .
```

## 🚀 Autocomplete Commands

### 1. IP Address Suggestions

```bash
# Show general IP suggestions
linguard completers ip

# Show 20 suggestions
linguard completers ip -c 20

# Suggestions with a specific prefix
linguard completers ip 192.168.1

# Private IP suggestions
linguard completers ip 10.0.0

# Test public IP suggestions
linguard completers ip 203.0.113
```

**Example output:**
```
Suggested IP addresses:
  1. 192.168.1.1
  2. 192.168.1.2
  3. 192.168.1.3
  4. 10.0.0.1
  5. 10.0.0.2
  6. 172.16.0.1
  7. 203.0.113.1
  8. 8.8.8.8
  9. 1.1.1.1
```

### 2. Subnet Suggestions

```bash
# Show common subnet ranges
linguard completers subnet

# Subnet suggestions from a specific network
linguard completers subnet 192.168.1.0

# Suggestions with a specific class
linguard completers subnet --class A
linguard completers subnet --class B
linguard completers subnet --class C
```

**Example output:**
```
Common subnet ranges:
  192.168.1.0/24 - Class C - 254 hosts
  192.168.0.0/16 - Class C - 65534 hosts
  10.0.0.0/8 - Class A - 16M hosts
  172.16.0.0/12 - Class B - 1M hosts
```

### 3. DNS Suggestions

```bash
# Show all DNS servers
linguard completers dns

# Cloudflare DNS
linguard completers dns --provider cloudflare

# Google DNS
linguard completers dns --provider google

# Quad9 DNS
linguard completers dns --provider cloud
```

**Example output:**
```
Suggested DNS (cloudflare):
  1.1.1.1
  1.0.0.1
  2606:4700:4700::1111
  2606:4700:4700::1001
```

### 4. Port Suggestions

```bash
# Show common WireGuard ports
linguard completers port

# Port range suggestions
linguard completers port -r 51820-65535

# Specific ports
linguard completers port -r 443-8443
```

**Example output:**
```
Common WireGuard ports:
  51820
  51821
  51822
  443
  8443
  8080
```

### 5. Peer Name Suggestions

```bash
# Show common peer names
linguard completers peer

# With a specific server port
linguard completers peer --server-port 51820
```

**Example output:**
```
Suggested peer names:
  1. Office Network
  2. Home Device
  3. Mobile Hotspot
  4. Backup Server
  5. Development Machine
  6. Production Server
  7. IoT Device
  8. Remote Worker
```

## 🔧 Usage in Main Commands

### Create a Server with Autocomplete

```bash
# Suggest IPs, DNS and ports
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Production Server" --endpoint vpn.example.com

# Use specific values
linguard servers create \
  --name "Prod Server" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart
```

### Create a Peer with Autocomplete

```bash
# Suggest an IP range
linguard peers create 1 --suggest-range \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# Create a peer with specific parameters
linguard peers create 1 \
  --name "Home Device" \
  --endpoint 203.0.113.50 \
  --allowed-ips 192.168.1.0/24 \
  --ipv6 fd00::100/128 \
  --preshared-key "your-key-here"
```

### Practical Examples

#### Scenario 1: Set Up a Production Server

```bash
# 1. Review available suggestions
linguard completers ip
linguard completers dns --provider cloudflare
linguard completers port

# 2. Create a server using suggestions
linguard servers create \
  --name "Production VPN" \
  --suggest-ip \
  --suggest-dns \
  --suggest-port \
  --endpoint vpn.company.com

# 3. Specify the final configuration
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint vpn.company.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart \
  --description "Main production WireGuard server"
```

#### Scenario 2: Adding Peers to the Network

```bash
# 1. Review available subnet ranges
linguard completers subnet

# 2. Create an office peer
linguard peers create 1 \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# 3. Create a home peer
linguard peers create 1 \
  --name "Home Device" \
  --endpoint 203.0.113.50 \
  --allowed-ips 192.168.2.0/24 \
  --ipv6 fd00::200/128

# 4. Create a backup peer
linguard peers create 1 \
  --name "Backup Server" \
  --endpoint 10.0.0.50 \
  --allowed-ips 192.168.3.0/24
```

#### Scenario 3: Setting Up a Complete Network

```bash
# Step 1: Create the main server
linguard servers create \
  --name "Main VPN" \
  --port 51820 \
  --endpoint vpn.local \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart

# Step 2: Set up the office peer
linguard peers create 1 \
  --name "Office" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# Step 3: Set up the development peer
linguard peers create 1 \
  --name "Dev Machine" \
  --endpoint 192.168.1.101 \
  --allowed-ips 192.168.1.0/24 \
  --preshared-key "dev-key-12345"

# Step 4: Review the configuration
linguard servers list
linguard peers list
```

## 💡 Tips and Best Practices

### 1. Combine Autocomplete with Specific Parameters

```bash
# Review suggestions first
linguard completers ip
linguard completers subnet

# Then use them in the command
linguard servers create \
  --name "MyServer" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 10.0.0.1/24 \
  --dns-primary 1.1.1.1
```

### 2. Use --suggest for Interactivity

```bash
# The CLI will show suggestions and ask for confirmation
linguard servers create --suggest-ip \
  --name "Server" \
  --endpoint example.com

# It will show options such as:
# 1. 10.0.0.1/24
# 2. 192.168.1.0/24
# 3. 172.16.0.0/12
# (Enter to skip)
```

### 3. Save Reusable Configurations

```bash
# Create a script for standard configurations
cat > create_server.sh << 'EOF'
#!/bin/bash
linguard servers create \
  --name "$SERVER_NAME" \
  --port "$SERVER_PORT" \
  --endpoint "$SERVER_ENDPOINT" \
  --ipv4 10.0.0.$((RANDOM % 255))/24 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart
EOF

chmod +x create_server.sh
```

### 4. Use Secure DNS

```bash
# Secure Cloudflare DNS
linguard servers create \
  --name "Secure Server" \
  --port 51820 \
  --endpoint vpn.example.com \
  --dns-primary 1.0.0.1 \
  --dns-secondary 1.1.1.1

# Google DNS
linguard servers create \
  --name "Google DNS" \
  --port 51820 \
  --endpoint vpn.example.com \
  --dns-primary 8.8.8.8 \
  --dns-secondary 8.8.4.4
```

## 🔍 Troubleshooting

### Problem: Suggestions do not appear

**Solution:**
```bash
# Verify the CLI is installed
linguard --version

# Check permissions
ls -la linguard

# Restart autocomplete
linguard completers ip
```

### Problem: Suggested IPs are not valid

**Solution:**
```bash
# Verify the suggestions manually
linguard completers ip --count 10

# Use well-known ranges
linguard completers subnet --class C
```

### Problem: DNS does not connect

**Solution:**
```bash
# Check available DNS servers
linguard completers dns

# Use a trusted public DNS
linguard servers create \
  --name "Test" \
  --port 51820 \
  --endpoint example.com \
  --dns-primary 1.1.1.1
```

## 📚 Additional Resources

- [Full documentation](README.md)
- [User guide](GUIDE.md)
- [API Reference](http://localhost:8000/docs)

## 🎓 Learning

### Basic Level

```bash
# See all options
linguard completers --help

# Use basic suggestions
linguard servers create --suggest-ip --name "Test" --endpoint test.com
```

### Intermediate Level

```bash
# Combine multiple suggestions
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Prod" --endpoint vpn.com

# Use specific subnets
linguard completers subnet 192.168.1.0
```

### Advanced Level

```bash
# Script with autocomplete
cat > deploy_vpn.sh << 'EOF'
#!/bin/bash
# Suggest IPs for the server
linguard completers ip > /tmp/ip_suggestions.txt

# Suggest DNS
linguard completers dns --provider cloudflare > /tmp/dns.txt

# Use the suggestions
SERVER_IP=$(head -1 /tmp/ip_suggestions.txt)
DNS_PRIMARY=$(head -1 /tmp/dns.txt)

linguard servers create \
  --name "Auto Deploy" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 $SERVER_IP \
  --dns-primary $DNS_PRIMARY
EOF

chmod +x deploy_vpn.sh
```

## 🏆 Optimal Configuration Example

```bash
#!/bin/bash

# Complete VPN server setup

# 1. Create the main server
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint vpn.company.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart \
  --description "Main production WireGuard server"

# 2. Set up the office peer
linguard peers create 1 \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# 3. Set up the development peer
linguard peers create 1 \
  --name "Dev Machine" \
  --endpoint 192.168.1.101 \
  --allowed-ips 192.168.1.0/24 \
  --preshared-key "dev-key-secure-12345"

# 4. Create a backup
linguard backups create --name "pre-config-backup"

# 5. Verify the configuration
linguard servers list
linguard peers list
linguard status health
```

---

**Version:** 0.1.0  
**Last updated:** 2024-10-11
