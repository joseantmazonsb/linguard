# Linguard

[![GitHub](https://img.shields.io/github/license/joseantmazonsb/linguard)](LICENSE.md) ![Python version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=yellow) [![Stable workflow status](https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml) [![Latest workflow status](https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml) [![Stable Documentation Status](https://readthedocs.org/projects/linguard/badge/?version=stable)](https://linguard.readthedocs.io/en/stable/?badge=stable) [![codecov](https://codecov.io/github/joseantmazonsb/linguard/graph/badge.svg)](https://codecov.io/github/joseantmazonsb/linguard)

[![GitHub release (latest SemVer including pre-releases)](https://img.shields.io/github/v/release/joseantmazonsb/linguard?color=green&include_prereleases&logo=github)](https://github.com/joseantmazonsb/linguard/releases) [![GitHub all releases](https://img.shields.io/github/downloads/joseantmazonsb/linguard/total?logo=github)](https://github.com/joseantmazonsb/linguard/releases)

![Linguard Logo](docs/assets/logo.png)

## Overview

Linguard is a modern web application for managing WireGuard VPN servers. Built with FastAPI and React, it provides a comprehensive interface for creating, configuring, and monitoring WireGuard interfaces and peers.

## Key Features

- ✅ **Interface Management:** Create, edit, delete, and configure WireGuard interfaces via web UI
- ✅ **Peer Management:** Add, remove, and configure peers with automatic configuration generation
- ✅ **Real-time Monitoring:** View traffic statistics and connection status in real-time
- ✅ **System Information:** Monitor system resources, network interfaces, and firewall status
- ✅ **Encrypted Credentials:** AES encryption for sensitive user data
- ✅ **OIDC SSO Support:** Enterprise-grade authentication with OpenID Connect
- ✅ **Firewall Integration:** Automatic iptables/firewall configuration
- ✅ **Background Services:** Health monitoring, automatic backups, and metrics collection
- ✅ **Docker Support:** Easy deployment with Docker and Docker Compose
- ✅ **Systemd Integration:** Run as a system service for production use

## Screenshots

![Dashboard Screenshot](docs/assets/screenshot-dashboard.png)
![Interface Management](docs/assets/screenshot-interface.png)
![Peer Management](docs/assets/screenshot-peer.png)

## Documentation

- [Full Documentation](https://linguard.readthedocs.io)
- [System Architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Firewall Configuration](docs/FIREWALL.md)
- [Background Services](docs/SERVICES.md)
- [Development Guide](DEVELOPMENT.md)

## Quick Start

### Development Setup

```bash
# Clone the repository
git clone https://github.com/joseantmazonsb/linguard.git
cd linguard

# Backend setup
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure database
cp .env.example .env
# Edit .env with your settings

# Start backend
uvicorn app.main:app --reload --port 8000

# Frontend setup
cd ../frontend
pnpm install
pnpm run dev

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
```

### Firewall Configuration

For production use, configure passwordless sudo for iptables:

```bash
echo "yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables, /usr/bin/wg-quick, /usr/bin/wg" | \
sudo tee /etc/sudoers.d/linguard > /dev/null
sudo chmod 440 /etc/sudoers.d/linguard
```

## Installation

### As a `systemd` service

1. Download the latest release from [GitHub Releases](https://github.com/joseantmazonsb/linguard/releases)
2. Extract and run the installation script:
   ```bash
   chmod +x install.sh
   sudo ./install.sh
   ```
3. Start Linguard:
   ```bash
   sudo systemctl start linguard.service
   sudo systemctl enable linguard.service
   ```

### Docker

1. Clone the repository
2. Configure environment variables in `.env`
3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Docker Compose

```yaml
version: '3.8'
services:
  linguard:
    image: joseantmazonsb/linguard:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/linguard
      - SECRET_KEY=your-secret-key-here
    depends_on:
      - db
    volumes:
      - ./data:/app/data

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=linguard
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Technology Stack

- **Backend:** FastAPI, Python 3.8+, SQLAlchemy, Pydantic v2
- **Frontend:** React, TypeScript, Vite, Radix UI
- **Database:** PostgreSQL, SQLite, MySQL
- **Authentication:** JWT, bcrypt, OIDC SSO
- **WireGuard:** iptables, wg-quick
- **Monitoring:** Health checks, metrics collection, background services

## API Documentation

Once running, access the API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./linguard.db
# OR for PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/linguard

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15

# WireGuard
WIREGUARD_PORT=51820

# Application
DEBUG=True
LOG_LEVEL=DEBUG
DEBUG_BYPASS_FIREWALL=False  # Set to True only for development

# Firewall
FIREWALL_DRIVER=iptables  # or nftables, firewalld
```

## Development

See [Development Guide](DEVELOPMENT.md) for detailed development instructions.

### Running Tests

```bash
# Backend tests
cd backend
source .venv/bin/activate
pytest

# Frontend tests
cd frontend
pnpm test
```

### Code Quality

```bash
# Backend
cd backend
source .venv/bin/activate
ruff check .
ruff format .

# Frontend
cd frontend
pnpm lint
pnpm format
```

## System Requirements

### Minimum Requirements

- Python 3.8+ (recommended: 3.10+)
- Node.js 18+
- PostgreSQL 12+ (for production)
- WireGuard installed
- iptables or nftables

### Recommended Requirements

- Python 3.11+
- PostgreSQL 15+
- SSD storage
- 2GB+ RAM
- Modern web browser (Chrome, Firefox, Safari)

## Security Considerations

- Use strong `SECRET_KEY` in production
- Enable HTTPS in production
- Use PostgreSQL with proper permissions
- Configure firewall rules appropriately
- Regular security updates
- Enable rate limiting
- Sanitize all user inputs

## Contributing

See [Contributing Guide](CONTRIBUTING.md) for contribution instructions.

## License

This project is licensed under the MIT License - see [LICENSE.md](LICENSE.md) for details.

## Support

- [GitHub Issues](https://github.com/joseantmazonsb/linguard/issues)
- [Documentation](https://linguard.readthedocs.io)
- [Discussions](https://github.com/joseantmazonsb/linguard/discussions)

## Roadmap

### In Progress

- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom integrations
- [ ] CLI tool for command-line management

### Planned

- [ ] Multi-tenant support
- [ ] Kubernetes deployment support
- [ ] Terraform provider
- [ ] GraphQL API
- [ ] WebSocket for real-time updates
- [ ] Advanced traffic analysis

## Credits

- **WireGuard:** [WireGuard Project](https://www.wireguard.com/)
- **FastAPI:** [FastAPI Project](https://fastapi.tiangolo.com/)
- **React:** [React Team](https://react.dev/)
- **Vite:** [Vite Team](https://vitejs.dev/)

## Acknowledgments

- Built with ❤️ by the Linguard community
- Inspired by the simplicity and elegance of WireGuard
- Thanks to all contributors and users
