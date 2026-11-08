# Contributing to Linguard

Thank you for your interest in contributing to Linguard! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Submitting Pull Requests](#submitting-pull-requests)

## Code of Conduct

Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.12 and pip
- Node.js 22 and pnpm
- Git
- PostgreSQL, SQLite, or MySQL (for local development)

### Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt -r requirements-test.lock.txt
```

### Frontend Setup

```bash
cd frontend
pnpm install
```

## Development Setup

### Running in Development Mode

You'll need two terminal windows:

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
pnpm dev
```

### Database Setup

Choose SQLite, PostgreSQL, or MySQL in the setup wizard. PostgreSQL and MySQL require a reachable database. The connection is stored in `backend/linguard.config.json` by default, or at `LINGUARD_CONFIG_PATH` if set; `DATABASE_URL` and `SECRET_KEY` do not configure the server. Restrict access to the config file because it may contain database credentials. See the [Development Guide](docs/DEVELOPMENT.md#configuration) for details.

## Project Structure

### Backend (`backend/`)

```
backend/
├── app/
│   ├── api/              # API endpoints
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── utils/            # Utility functions
│   ├── core/             # Core configuration
│   └── main.py           # Application entry point
├── requirements.txt      # Direct Python dependencies
└── requirements.lock.txt # Locked Python dependencies
```

### Frontend (`frontend/`)

```
frontend/
├── src/                  # Source code
├── public/               # Static assets
└── package.json          # Node.js dependencies
```

## Making Changes

### Backend Changes

1. **Add new endpoints:**
   - Create the endpoint in `app/api/`
   - Define request/response schemas in `app/schemas/`
   - Add Pydantic validators for data validation

2. **Add new models:**
   - Create SQLAlchemy models in `app/models/`
   - Create Pydantic schemas in `app/schemas/`
   - Add database session handling

3. **Add utilities:**
   - Use `app/utils/` for reusable functions
   - Add type hints for all functions

### Frontend Changes

1. **Component structure:**
   - Follow the existing component pattern
   - Use TypeScript for type safety

2. **Styling:**
   - Use the existing CSS framework
   - Add comments to new styles

## Code Style

### Python

- Use [Black](https://black.readthedocs.io/) for formatting
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Follow [PEP 8](https://pep8.org/) style guide
- Add type hints to all functions
- Include docstrings for public functions

### JavaScript/TypeScript

- Use ESLint and Prettier
- Follow [TypeScript](https://typescript.org/) best practices
- Add JSDoc comments to public functions

## Testing

### Backend Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

### Frontend Tests

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:e2e
```

Playwright expects the frontend and backend servers to be running, and some tests require setup data. There is no frontend unit-test or coverage script; see the [Development Guide](docs/DEVELOPMENT.md#frontend) for additional regression tests.

## Submitting Pull Requests

### Before Submitting

1. **Update documentation:**
   - README.md
   - docs/DEVELOPMENT.md
   - docs/DEPLOYMENT.md
   - release-notes.md

2. **Update requirements:**
   - Update `backend/requirements.txt` or `backend/requirements-test.txt` and regenerate both locks as described in the [Development Guide](docs/DEVELOPMENT.md#backend-setup)
   - Update `frontend/package.json` and the appropriate lockfile for frontend dependencies

3. **Run all tests:**
   - Backend tests pass
   - Frontend tests pass
   - Linting passes

4. **Update changelog:**
   - Add your changes to release notes

### Pull Request Template

```
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Dependency update

## Testing

Describe how you tested your changes

## Screenshots (if applicable)

Add screenshots for UI changes

## Dependencies

- [ ] Added to requirements.txt
- [ ] Added to package.json
- [ ] Installed and tested

## Documentation

- [ ] Updated README.md
- [ ] Updated docs/DEVELOPMENT.md
- [ ] Added inline code comments
```

## Questions?

Feel free to open an issue or discuss in the project's issue tracker.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
