# Linguard Docker Deployment

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Root access or sudo privileges (for NET_ADMIN capability)

### Build and Run

**Option 1: Using Make (Recommended)**

```bash
# Build the image
make build

# Run the container
make run

# View logs
make logs

# Access the UI
# http://localhost:8000
```

**Option 2: Manual Commands**

```bash
# Build
docker build -t linguard .

# Run
docker run -d \
  --name linguard \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /etc/wireguard:/etc/wireguard:rw \
  -v linguard_data:/app/data \
  -v linguard_backups:/app/backups \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/linguard.db \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  --cap-add NET_ADMIN \
  --device /dev/net/tun:/dev/net/tun \
  --security-opt seccomp:unconfined \
  --privileged \
  linguard
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:////app/data/linguard.db` | Database connection string |
| `SECRET_KEY` | Random on first run | Secret key for JWT tokens |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiry time |
| `USE_OIDC` | `false` | Enable OIDC authentication |
| `OIDC_ISSUER_URL` | - | OIDC provider URL |

### Database Options

#### SQLite (Default - No External DB)
```bash
-e DATABASE_URL=sqlite+aiosqlite:////app/data/linguard.db
```
- **Pros**: Simple, no external dependencies, persists in volume
- **Cons**: Single database, no replication, limited concurrency

#### PostgreSQL
```bash
-e DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/linguard
```
- **Pros**: Production-grade, replication, concurrent access
- **Cons**: Requires external PostgreSQL instance

#### MySQL/MariaDB
```bash
-e DATABASE_URL=mysql+pymysql://user:password@mysql:3306/linguard
```
- **Pros**: Production-grade, widely used
- **Cons**: Requires external MySQL/MariaDB instance

## Permissions & Capabilities

The container requires the following Linux capabilities and permissions:

```bash
--cap-add NET_ADMIN        # For iptables/nftables
--device /dev/net/tun      # For WireGuard TUN device
--security-opt seccomp:unconfined  # For WireGuard kernel modules
--privileged               # For all required capabilities
```

### Alternative: Minimal Permissions (if supported)

If your kernel supports it, you can use a less privileged approach:

```bash
--cap-add NET_ADMIN
--cap-add SYS_MODULE
--device /dev/net/tun
```

## Data Persistence

### Volumes

| Volume | Mount Point | Description |
|--------|-------------|-------------|
| `linguard_data` | `/app/data` | Database, configs, logs |
| `linguard_backups` | `/app/backups` | Backup files |
| `/etc/wireguard` | `/etc/wireguard` | WireGuard configs (host path) |

### Backup Your Data

```bash
# Backup database
docker exec linguard cp /app/data/linguard.db ./linguard_backup.db

# Backup backups volume
docker run --rm --volumes-from linguard -v $(pwd):/backup alpine \
  tar czf /backup/linguard_backups.tar.gz -C /app/backups .
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs linguard

# Check if container is running
docker ps
```

### Database errors

```bash
# Check if database exists
docker exec linguard ls -la /app/data/

# Reinitialize database (WARNING: deletes all data)
docker exec linguard rm /app/data/linguard.db
```

### Can't access WireGuard configs

Ensure your host has `/etc/wireguard` writable:
```bash
sudo mkdir -p /etc/wireguard
sudo chmod 777 /etc/wireguard
```

### Network issues

```bash
# Check if container has network access
docker exec linguard ping -c 1 8.8.8.8

# Test WireGuard interface
docker exec linguard ip addr show wg0
```

## Development Mode

For local development with hot-reload, use the development docker-compose:

```bash
docker-compose -f docker-compose.dev.yml up
```

## Production Recommendations

1. **Use a reverse proxy** (nginx, caddy, traefik) for:
   - HTTPS termination
   - Rate limiting
   - SSL certificates
   - Domain routing

2. **Set strong SECRET_KEY** in production
   ```bash
   docker run -e SECRET_KEY=$(openssl rand -hex 64) ...
   ```

3. **Use PostgreSQL** for production workloads

4. **Enable monitoring** (Prometheus, Grafana)

5. **Configure backup automation**

6. **Use systemd or docker-compose** for auto-restart

## Examples

### Production with PostgreSQL

```bash
docker run -d \
  --name linguard \
  -p 8000:8000 \
  -v /etc/wireguard:/etc/wireguard:rw \
  -e DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/linguard \
  -e SECRET_KEY=$(openssl rand -hex 64) \
  --cap-add NET_ADMIN \
  --device /dev/net/tun \
  --security-opt seccomp:unconfined \
  --privileged \
  linguard
```

### With Custom Port

```bash
docker run -d \
  --name linguard \
  -p 9000:8000 \
  linguard
```

Then access: `http://localhost:9000`

---

For more information, see [Linguard Documentation](https://linguard.readthedocs.io).
