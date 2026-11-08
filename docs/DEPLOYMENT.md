# Deployment Guide

> **Deployment warning:** Run exactly one Linguard backend worker in one instance during setup and whenever WebSocket functionality is required. The setup lifecycle lock is process-local, so multiple workers or instances can race setup mutations and completion. WebSocket tickets, connections, and broadcasts are also process-local: a ticket issued by one process cannot be used by another, and broadcasts do not reach clients connected elsewhere. Multiple workers or replicas are not supported for these purposes; sticky sessions or a shared database do not make them safe. Restrict management access during setup.

## Overview

This guide covers various deployment options for Linguard, from development to production environments.

## Development Deployment

### Prerequisites

- Python 3.8+
- Node.js 18+
- Git
- PostgreSQL (optional, SQLite works for development)

### Setup

```bash
# Clone repository
git clone https://github.com/joseantmazonsb/linguard.git
cd linguard

# Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt

# Configure the database and application settings through the setup wizard

# Frontend
cd ../frontend
pnpm install
```

### Running Development Servers

```bash
# Terminal 1 - Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
pnpm run dev
```

Access:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

### Development Tips

1. **Firewall Bypass:** For development, you can bypass firewall requirements:
   ```bash
   export DEBUG_BYPASS_FIREWALL=true
   ```

2. **Database:** Select SQLite in the setup wizard for quick development.

3. **Hot Reload:** Both frontend and backend support hot reloading during development.

## Production Deployment

### Systemd Service (Linux)

#### Installation Script

```bash
# Download and run installation script
wget https://github.com/joseantmazonsb/linguard/releases/latest/download/install.sh
chmod +x install.sh
sudo ./install.sh
```

#### Manual Installation

```bash
# Create system user
sudo useradd -m -s /bin/bash linguard

# Create directories
sudo mkdir -p /opt/linguard/{backend,frontend,data,logs}
sudo chown linguard:linguard /opt/linguard

# Install dependencies
sudo apt update
sudo apt install -y python3.12 python3-pip nodejs npm wireguard iptables

# Setup backend
cd /opt/linguard/backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt

# Configure the database and application settings through the setup wizard

# Setup frontend
cd /opt/linguard/frontend
npm install -g pnpm
pnpm install

# Create systemd service
sudo tee /etc/systemd/system/linguard.service > /dev/null <<EOF
[Unit]
Description=Linguard WireGuard Management
After=network.target

[Service]
Type=notify
User=linguard
Group=linguard
WorkingDirectory=/opt/linguard/backend
Environment="PATH=/opt/linguard/backend/.venv/bin:$PATH"
ExecStart=/opt/linguard/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/opt/linguard/logs/backend.log
StandardError=append:/opt/linguard/logs/backend.log

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable linguard
sudo systemctl start linguard
sudo systemctl status linguard
```

#### Firewall Configuration

```bash
# Configure passwordless sudo
echo "linguard ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables, /usr/bin/wg-quick, /usr/bin/wg" | \
sudo tee /etc/sudoers.d/linguard > /dev/null
sudo chmod 440 /etc/sudoers.d/linguard
```

### Docker Deployment

See the [Docker deployment guide](../docker-readme.md) and supplied [Compose file](../docker-compose.yml) for the current image, persistence paths, bridge-network limitations, port mappings, and host privilege requirements. Before upgrading an existing container or switching between Make and Compose, follow its [volume migration instructions](../docker-readme.md#upgrading-an-existing-container); otherwise config, database, backups, or plugins may be lost or the wrong volume used.

Configure the database and signing key through setup, not `DATABASE_URL` or `SECRET_KEY` environment variables. If using a reverse proxy, terminate HTTPS and configure WebSocket upgrades for `/ws` to the same single backend instance.

### Kubernetes Deployment

No Kubernetes manifest is supplied. Any custom deployment must respect the single-worker, single-instance warning above, including during rollout: do not overlap old and new pods during setup or when WebSockets are required.

Key considerations:

1. **Resource Limits:**
   ```yaml
   resources:
     requests:
       memory: "256Mi"
       cpu: "250m"
     limits:
       memory: "512Mi"
       cpu: "500m"
   ```

2. **Persistent Volumes:** Use PersistentVolumeClaim for data persistence

3. **Security Context:**
   ```yaml
   securityContext:
     runAsNonRoot: true
     runAsUser: 1000
     seccompProfile:
       type: RuntimeDefault
   ```

## WSL Deployment

### Prerequisites

- Windows Subsystem for Linux 2 (WSL2)
- Ubuntu 22.04 or later

### Setup

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3.12 python3-pip nodejs npm wireguard iptables

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt

# Configure firewall (important for WSL)
# WSL uses a different network configuration
```

### Network Configuration

WSL deployment requires special network configuration:

1. **Host Access:**
   - Backend: http://localhost:8000 (from WSL)
   - Frontend: http://localhost:5173 (from WSL)

2. **Host Network:**
   - Access from Windows: Use port forwarding or configure WSL network settings

3. **Firewall Rules:**
   ```bash
   # Configure WSL firewall
   sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 5173 -j ACCEPT
   ```

## Security Best Practices

### Configuration Secrets

Keep database credentials, signing keys, and API keys out of Git and restrict access to configuration files and exports. The setup wizard generates the signing key; `SECRET_KEY` and `DATABASE_URL` environment variables do not configure the current server. For an installation using the known legacy setup key, follow [legacy signing key recovery](SETUP_RECOVERY.md) before resuming service.

### SSL/TLS

1. **Use HTTPS in Production:**
   - Obtain SSL certificate (Let's Encrypt recommended)
   - Configure reverse proxy (nginx, Apache)
   - Enable HSTS headers

2. **Secure Headers:**
   ```nginx
   add_header Strict-Transport-Security "max-age=31536000";
   add_header X-Frame-Options "DENY";
   add_header X-Content-Type-Options "nosniff";
   ```

### Database Security

1. **Use Strong Passwords:**
   ```bash
   POSTGRES_PASSWORD=$(openssl rand -base64 32)
   ```

2. **Database Users:**
   - Create dedicated database user
   - Limit permissions to minimum required
   - Use SSL connections

3. **Backup Strategy:**
   ```bash
   # Automated daily backups
   0 2 * * * pg_dump linguard > /backups/linguard_$(date +\%Y\%m\%d).sql
   ```

   Linguard rejects backup creation requests with `encrypt=true` (HTTP 400); it does not encrypt new backups. Backups created by the previous implementation were also unencrypted, even if encryption was requested. They may contain WireGuard private and preshared keys and integration configuration. Restrict access and use external encryption for stored and transferred backups, including database dumps and exports. The legacy restore path for records marked encrypted only base64-decodes them; base64 is not encryption.

### Firewall Configuration

```bash
# Production firewall rules
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp -m tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp -m tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

### Monitoring and Logging

1. **Centralized Logging:**
   ```bash
   # Configure rsyslog for centralized logging
   sudo apt install -y rsyslog
   ```

2. **Log Rotation:**
   ```bash
   sudo ln -sf /dev/null /var/log/linguard.log
   ```

3. **Health Checks:**
   ```bash
   # Create health check script
   cat > /usr/local/bin/linguard-health.sh << 'EOF'
   #!/bin/bash
   curl -f http://localhost:8000/health || exit 1
   exit 0
   EOF
   chmod +x /usr/local/bin/linguard-health.sh
   ```

## Troubleshooting Deployment

### Common Issues

#### Database Connection Failed

```bash
# Check database is running
sudo systemctl status postgresql

# Check connection
psql postgres -c "SELECT 1"
```

#### Port Already in Use

```bash
# Find and kill process using port
sudo lsof -ti:8000 | xargs kill -9

# For Docker, update the UDP port mappings to match each server's listen port;
# see docker-readme.md. WIREGUARD_PORT does not configure the server.
```

#### Permission Denied

```bash
# Fix file permissions
sudo chown -R linguard:linguard /opt/linguard
sudo chmod -R 755 /opt/linguard

# Fix sudoers file
sudo chmod 440 /etc/sudoers.d/linguard
```

#### Firewall Not Working

```bash
# Verify iptables rules
sudo iptables -L -n -v

# Test iptables command
sudo iptables -L

# Check sudoers configuration
sudo -l | grep linguard
```

### Monitoring

```bash
# Check service status
sudo systemctl status linguard

# View logs
sudo journalctl -u linguard -f

# Check resource usage
top -p $(pgrep -f uvicorn)
```

## Migration Guide

### Upgrading Versions

For Docker installations, use the [container and volume migration procedure](../docker-readme.md#upgrading-an-existing-container) instead of the service upgrade steps below. If authentication reports an insecure legacy signing key, follow [legacy signing key recovery](SETUP_RECOVERY.md).

1. **Backup Data:**
   ```bash
   pg_dump linguard > backup.sql
   ```

2. **Update Code:**
   ```bash
   git pull origin main
   ```

3. **Update Dependencies:**
   ```bash
   pip install -r requirements.lock.txt
   ```

4. **Run Migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Restart Service:**
   ```bash
   sudo systemctl restart linguard
   ```

## Support

For deployment issues:

1. Check [GitHub Issues](https://github.com/joseantmazonsb/linguard/issues)
2. Review [Documentation](https://linguard.readthedocs.io)
3. Review [Development Guide](DEVELOPMENT.md) for project internals
4. Enable DEBUG mode for detailed logs

## License

MIT License - see [LICENSE.md](../LICENSE.md) for details.
