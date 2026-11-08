# Linguard Development Guide

Developer documentation for Linguard, a web application for managing WireGuard VPN servers.

## Overview

**Linguard** lets you create, configure, and monitor WireGuard interfaces and peers through a web interface. Key features include real-time traffic metrics, OIDC SSO, firewall integration, background services (health checks, backups, metrics), and webhook integrations via Traffic Triggers.

**Stack:**
- Backend: Python 3.12 (used by Docker and CI), FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL/SQLite/MySQL
- Frontend: React 18+, TypeScript, Vite, Radix UI, Tailwind CSS, Zustand, TanStack Query

---

## Getting Started

### Prerequisites

- Python 3.12 and pip
- Node.js 22 and pnpm
- PostgreSQL, SQLite, or MySQL
- Git

### Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
pip install -r requirements-test.lock.txt  # for tests
```

The requirements files specify direct dependencies; the generated lock files pin
their transitive dependencies for Python 3.12 across platforms. After changing
either requirements file, update both locks with `uv==0.12.5` from `backend/`:

```bash
uv pip compile --python-version 3.12 --universal requirements.txt -o requirements.lock.txt
uv pip compile --python-version 3.12 --universal -c requirements.lock.txt requirements-test.txt -o requirements-test.lock.txt
```

If installation fails, resolve the underlying platform or build issue and retry the lockfile installation rather than installing unpinned packages.

### Running the Backend

```bash
# Development (hot reload)
uvicorn app.main:app --reload --port 8000

# Production (no reload)
uvicorn app.main:app --port 8000
```

Once running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Running the Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The frontend is available at http://localhost:5173 and expects the backend on port 8000.

### Configuration

Use the setup wizard to configure the database and application settings. SQLite is the default; PostgreSQL and MySQL require a reachable database. The database connection is stored in `backend/linguard.config.json` by default; `LINGUARD_CONFIG_PATH` can select another file. Global settings, including the signing key, are stored in the database. `DATABASE_URL` and `SECRET_KEY` environment variables do not configure the server. Configuration files, databases, and backups can contain credentials and other secrets; restrict access and use external encryption where needed. See [Docker Deployment](../docker-readme.md) for persistence and security considerations.

---

## Architecture

```
linguard/
├── backend/
│   ├── app/
│   │   ├── api/        # FastAPI routers
│   │   ├── core/       # config, DI container, database, security, events
│   │   ├── models/     # SQLAlchemy models
│   │   ├── schemas/    # Pydantic schemas
│   │   ├── services/   # Business logic
│   │   ├── plugins/    # Plugin system
│   │   └── main.py     # Entry point
│   ├── src/linguard_cli/   # CLI (depends on the backend)
│   ├── requirements.txt
│   └── requirements.lock.txt
├── frontend/src/       # React application (see structure below)
└── docs/
```

Frontend details:

```
frontend/src/
├── components/   # Reusable UI (Dialog/, Forms/, Layout/, primitives/)
├── hooks/        # Custom React hooks
├── pages/        # Route pages (including Setup wizard)
├── services/     # API client layer
├── store/        # Zustand stores
├── types/        # TypeScript type definitions
└── utils/
```

### Backend Patterns

**Dependency Injection.** The app uses `dependency_injector`. Services without dependencies are defined first; services with dependencies are defined after, injecting the earlier singletons. Order matters.

**Service layer.** Endpoints never call WireGuard or firewall operations directly — they delegate to services (`WireGuardService`, `FirewallService`, ...). Services receive the database session and other collaborators through DI.

**Repository pattern.** Generic `Repository[T]` classes wrap common database operations (get, create, delete) over SQLAlchemy models.

**Event bus.** Services communicate through an in-process `EventBus` (`subscribe`/`publish`) for events like `SERVER_STARTED` or `PEER_CONNECTED`.

**Authentication.** JWT bearer tokens (`OAuth2PasswordBearer`). Protected routes use `get_current_user`; admin-only routes use `get_current_admin`.

**Background services.** Long-running monitors (health checks, interface monitoring, backup cleanup) run as asyncio loops started on app startup, with manual start/stop available for the setup wizard.

**Error handling.** Custom exceptions like `ValidationError` and `MultiFieldValidationError` return HTTP 400 with structured detail (`type`, `field`, `message`) handled by FastAPI exception handlers.

### Frontend Patterns

**Presentational components** receive typed props and render UI without side effects. **Container components** own state and data fetching with TanStack Query, handling loading, error, and success states explicitly. Business logic should live in custom hooks.

**Data fetching.** All server state goes through TanStack Query (`useQuery`/`useMutation`), with optimistic updates where appropriate and cache invalidation on settle.

**Global state.** Client-side state (UI preferences, session) uses Zustand stores.

---

## Database Schema

Setup initializes tables using SQLAlchemy's `create_all`. The repository does not currently include an Alembic configuration or migration scripts; `create_all` does not migrate existing tables when models change.

---

## Testing

### Backend

```bash
cd backend
source .venv/bin/activate

pytest                          # all tests
pytest tests/services/ -v       # specific suite
pytest --cov=app --cov-report=html   # coverage
```

- Unit tests live in `backend/tests/` and mock external collaborators.
- Integration tests use `TestClient` against the real app with a test database.
- Coverage is reported by pytest; the configured failure threshold is currently 0%.

### Frontend

```bash
cd frontend

pnpm exec playwright install chromium
pnpm test:e2e          # end-to-end (Playwright)
```

Playwright expects the frontend and backend servers to be running and some tests require setup data. There is no frontend unit-test or coverage script currently.

The mocked setup, dashboard and integration regression specs run in CI with a Vite server and mocked API responses. The setup-storage regression also runs directly with Node 22 (`node --experimental-strip-types --test e2e/setup-storage.test.mjs`).

Development follows TDD: write a failing test, implement the minimum code to pass it, then refactor while keeping tests green.

---

## Code Quality

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check .
ruff format .

# Frontend
cd frontend
pnpm lint
pnpm build
```

Before submitting a PR:
- All tests pass
- Review coverage for affected paths
- No `console.log` statements in production code
- Types are properly defined
- Formatting applied

---

## CLI

The `linguard` CLI lives in `backend/src/linguard_cli/` and depends on the backend:

```bash
cd backend/src/linguard_cli
source ../../.venv/bin/activate
pip install -e .

linguard --help
linguard completers ip
linguard servers list
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: psutil` | Activate `backend/.venv` and reinstall `requirements.lock.txt` |
| Database connection error | Check `backend/linguard.config.json` (or `LINGUARD_CONFIG_PATH`); verify the DB server is running |
| Port 8000 already in use | `uvicorn app.main:app --reload --port 8001` or `lsof -ti:8000 \| xargs kill -9` |
| Frontend module resolution errors | `rm -rf node_modules/.vite && pnpm build` |
| TypeScript "Property X does not exist" | Verify the type exists in `frontend/src/types/` and matches the backend response |

---

## Resources

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [React](https://react.dev/)
- [TypeScript](https://www.typescriptlang.org/docs/)
- [TanStack Query](https://tanstack.com/query/latest)
- [Zustand](https://github.com/pmndrs/zustand)
- [Tailwind CSS](https://tailwindcss.com/docs)

## License

MIT License — see [LICENSE.md](../LICENSE.md).
