# Linguard

[![GitHub License](https://img.shields.io/github/license/joseantmazonsb/linguard)](LICENSE.md) ![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue) [![GitHub Release](https://img.shields.io/github/v/release/joseantmazonsb/linguard?color=green)](https://github.com/joseantmazonsb/linguard/releases) [![codecov](https://codecov.io/gh/joseantmazonsb/linguard/graph/badge.svg)](https://codecov.io/gh/joseantmazonsb/linguard)

## Overview

Linguard is a modern web application for managing WireGuard VPN servers. Built with FastAPI and React, it provides a comprehensive interface for creating, configuring, and monitoring WireGuard interfaces and peers.

## Key Features

- ✅ **Interface Management:** Create, edit, delete, and configure WireGuard interfaces
- ✅ **Peer Management:** Add, remove, and configure peers with automatic configuration generation
- ✅ **Real-time Monitoring:** View traffic statistics and connection status
- ✅ **OIDC SSO Support:** Enterprise-grade authentication with OpenID Connect
- ✅ **Firewall Integration:** Automatic iptables/firewall configuration
- ✅ **Background Services:** Health monitoring, automatic backups, and metrics collection
- ✅ **Docker Support:** Easy deployment with Docker and Docker Compose
- ✅ **Systemd Integration:** Run as a system service for production use

## Documentation

**Getting Started** - See [Contributing Guide](CONTRIBUTING.md) for setup and development instructions.

**Development** - See [Development Guide](docs/DEVELOPMENT.md) for detailed development patterns and architecture.

**Deployment** - See [Deployment Guide](docs/DEPLOYMENT.md) for production deployment instructions.

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

### Production Deployment

See [Deployment Guide](docs/DEPLOYMENT.md) for production deployment instructions.

## Testing

### Backend

```bash
cd backend
source .venv/bin/activate
pytest
pytest --cov=app --cov-report=html
```

### Frontend

```bash
cd frontend
pnpm test
pnpm test -- --coverage
```

## Contributing

See [Contributing Guide](CONTRIBUTING.md) for information on how to contribute to Linguard.

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)

## License

MIT License — see [LICENSE.md](LICENSE.md).
