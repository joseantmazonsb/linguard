# Deployment Guide

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
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your settings

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

2. **Database:** Use SQLite for quick development:
   ```bash
   DATABASE_URL=sqlite:///./linguard.db
   ```

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
.venv/bin/pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with production settings

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

#### Basic Docker Compose

```yaml
version: '3.8'

services:
  linguard:
    image: ghcr.io/joseantmazonsb/linguard:latest
    container_name: linguard
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://linguard:secret@linguard-db:5432/linguard
      SECRET_KEY: your-super-secret-key-here
      DEBUG: "false"
      WIREGUARD_PORT: "51820"
    depends_on:
      linguard-db:
        condition: service_healthy
    volumes:
      - linguard-data:/app/data
      - linguard-logs:/app/logs
    restart: unless-stopped
    networks:
      - linguard-network

  linguard-db:
    image: postgres:15
    container_name: linguard-db
    environment:
      POSTGRES_DB: linguard
      POSTGRES_USER: linguard
      POSTGRES_PASSWORD: secret
    volumes:
      - linguard-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U linguard"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - linguard-network

volumes:
  linguard-data:
  linguard-logs:
  linguard-db-data:

networks:
  linguard-network:
    driver: bridge
```

#### Docker with Nginx and SSL

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./linguard/data:/app/data
      - ./linguard/logs:/app/logs
    depends_on:
      - linguard
    networks:
      - linguard-network

  linguard:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://linguard:secret@linguard-db:5432/linguard
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: "false"
    depends_on:
      linguard-db:
        condition: service_healthy
    volumes:
      - linguard-data:/app/data
      - linguard-logs:/app/logs
    networks:
      - linguard-network

  linguard-db:
    image: postgres:15
    environment:
      POSTGRES_DB: linguard
      POSTGRES_USER: linguard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - linguard-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U linguard"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - linguard-network

volumes:
  linguard-data:
  linguard-logs:
  linguard-db-data:

networks:
  linguard-network:
    driver: bridge
```

Nginx configuration:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream linguard_backend {
        server linguard:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://linguard_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /docs {
            proxy_pass http://linguard_backend/docs;
            proxy_set_header Host $host;
        }

        location /redoc {
            proxy_pass http://linguard_backend/redoc;
            proxy_set_header Host $host;
        }
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://linguard_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### Kubernetes Deployment

See `kubernetes/deployment.yaml` for a complete Kubernetes manifest.

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
pip install -r requirements.txt

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

### Environment Variables

```bash
# NEVER commit these to Git
SECRET_KEY=your-super-secret-random-key
DATABASE_URL=postgresql://user:password@host/db
API_KEY=your-api-key-here
```

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

# Or use different port
export WIREGUARD_PORT=51821
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
   pip install -r requirements.txt
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
3. Consult [System Architecture](SYSTEM_ARCHITECTURE.md)
4. Enable DEBUG mode for detailed logs

## License

MIT License - see [LICENSE.md](../LICENSE.md) for details.
