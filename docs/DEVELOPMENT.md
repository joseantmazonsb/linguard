# Linguard Development Guide

Developer documentation for Linguard, a web application for managing WireGuard VPN servers.

## Overview

**Linguard** lets you create, configure, and monitor WireGuard interfaces and peers through a web interface. Key features include real-time traffic metrics, OIDC SSO, encrypted credentials, firewall integration, background services (health checks, backups, metrics), and webhook integrations via Traffic Triggers.

**Stack:**
- Backend: Python 3.8+, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL/SQLite/MySQL
- Frontend: React 18+, TypeScript, Vite, Radix UI, Tailwind CSS, Zustand, TanStack Query

---

## Getting Started

### Prerequisites

- Python 3.8+ and pip
- pnpm
- PostgreSQL, SQLite, or MySQL
- Git

### Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL and SECRET_KEY
```

If `pip install` fails on some packages, install them manually:

```bash
pip install email-validator psutil bcrypt cryptography
```

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

### Environment Variables (backend/.env)

```env
DATABASE_URL=sqlite:///./linguard.db
# DATABASE_URL=postgresql://user:password@localhost/linguard
SECRET_KEY=change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=True
LOG_LEVEL=DEBUG
```

For production: set `DEBUG=False`, use a strong `SECRET_KEY`, PostgreSQL with SSL, and HTTPS.

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
│   ├── alembic/        # Migrations
│   └── requirements.txt
├── frontend/src/       # React application (see structure below)
├── docs/
└── docker/
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

## Database Migrations

```bash
cd backend
source .venv/bin/activate

alembic revision --autogenerate -m "Add new field"   # create
alembic upgrade head                                  # apply
alembic downgrade -1                                  # revert
```

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
- Coverage target: ≥ 80% (enforced by CI).

### Frontend

```bash
cd frontend

pnpm test              # unit tests (vitest)
pnpm test -- --coverage
pnpm test:e2e          # end-to-end (Playwright)
```

Coverage target: ≥ 70%.

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
pnpm format
```

Before submitting a PR:
- All tests pass
- Coverage meets targets
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
| `ModuleNotFoundError: psutil` | `pip install psutil` |
| Database connection error | Check `DATABASE_URL` in `backend/.env`; verify the DB server is running |
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
