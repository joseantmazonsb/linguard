# Linguard - AI Agent Guide

Essential instructions for AI agents working on this repository.

## Project Overview

**Linguard** is a web app for managing WireGuard VPN servers. Backend: FastAPI + SQLAlchemy + Pydantic v2 (Python 3.8+, PostgreSQL/SQLite/MySQL). Frontend: React 18 + TypeScript + Vite, with Radix UI, Tailwind CSS, Zustand, and TanStack Query.

## Project Layout

```
backend/app/
├── api/        # FastAPI routers (auth, servers, peers, traffic_triggers, ...)
├── core/       # config, DI containers, database, security, events
├── models/     # SQLAlchemy models
├── schemas/    # Pydantic schemas
├── services/   # Business logic (wireguard, firewall, backup_service, ...)
└── utils/

frontend/src/
├── components/ # Dialog/, Forms/, Layout/, primitives/ (Radix wrappers)
├── hooks/      # Custom hooks
├── pages/      # Routes
├── services/   # API client layer
├── store/      # Zustand stores
├── types/      # TypeScript types
└── utils/
```

## Environment & Commands

- Backend venv lives at `backend/.venv` — always activate it: `cd backend && source .venv/bin/activate`
- Run backend: `uvicorn app.main:app --reload --port 8000` (docs at /docs and /redoc)
- Backend tests: `pytest` (coverage: `pytest --cov=app --cov-report=html`)
- Frontend: `pnpm install`, `pnpm dev` (port 5173), `pnpm test`, `pnpm lint`
- Migrations: `alembic revision --autogenerate -m "..."` then `alembic upgrade head`
- Format: backend `ruff format .`, frontend `pnpm format`

## Coding Rules

**Backend:**
- Endpoints delegate to services; never call WireGuard/firewall operations directly in routers.
- DI via `dependency_injector`: define no-dependency services first, then inject them into dependent services. Order matters.
- Use `providers.Singleton` for stateful services.
- Validation errors return 400 with `{"type": ..., "field": ..., "message": ...}` detail.
- Admin-only routers require `Depends(get_current_admin)`.

**Frontend:**
- Presentational components: typed props, pure render, no side effects.
- Container components: fetch with TanStack Query, handle loading/error/success explicitly.
- `interface` for object shapes/props; `type` for unions/tuples/aliases.
- Use optional chaining and `??` for safe access.
- Always include Tailwind `dark:` variants; mobile-first responsive classes.

**Testing (TDD):**
- Write failing test first, implement minimum code, then refactor.
- Coverage targets: backend ≥ 80%, frontend ≥ 70%, critical paths 100%.
- Test naming: `it('should [action] when [condition]')`.

**Git:**
- Branches: `features/...`, `fixes/...`, `docs/...`, `chore/...`
- Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:` prefixes.

## References

- Full developer documentation: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- FastAPI: https://fastapi.tiangolo.com/
- TanStack Query: https://tanstack.com/query/latest
- Zustand: https://github.com/pmndrs/zustand
