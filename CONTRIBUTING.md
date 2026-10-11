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

- Python 3.8+
- Node.js and pnpm
- Git
- PostgreSQL, SQLite, or MySQL (for local development)

### Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm approve-builds
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

For local development, you can use SQLite by default. To use PostgreSQL:

1. Update `.env` in the backend directory
2. Run migrations:
   ```bash
   cd backend
   source .venv/bin/activate
   alembic upgrade head
   ```

## Project Structure

### Backend (`backend/`)

```
backend/
├── app/
│   ├── api/              # API endpoints
│   ├── db/               # Database models and sessions
│   ├── schemas/          # Pydantic schemas
│   ├── utils/            # Utility functions
│   ├── core/             # Core configuration
│   └── main.py           # Application entry point
├── requirements.txt      # Python dependencies
└── alembic/              # Database migrations
```

### Frontend (`frontend/`)

```
frontend/
├── src/                  # Source code
├── public/               # Static assets
├── packages/             # Approved build packages
└── package.json          # Node.js dependencies
```

## Making Changes

### Backend Changes

1. **Add new endpoints:**
   - Create the endpoint in `app/api/`
   - Define request/response schemas in `app/schemas/`
   - Add Pydantic validators for data validation

2. **Add new models:**
   - Create SQLAlchemy models in `app/db/models.py`
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
pnpm test
```

## Submitting Pull Requests

### Before Submitting

1. **Update documentation:**
   - README.md
   - GETTING_STARTED.md
   - RELEASE_NOTES.md

2. **Update requirements:**
   - Add new dependencies to `requirements.txt`
   - Update `package.json` for frontend dependencies

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
- [ ] Updated GETTING_STARTED.md
- [ ] Added inline code comments
```

## Known Issues

### Missing Dependencies

**Issue:** `psutil` is used but may not be in requirements.txt

**Solution:** Add `psutil==5.9.0` to `backend/requirements.txt`

**Issue:** `email-validator` may be missing

**Solution:** Add `email-validator` to validation module or requirements

## Questions?

Feel free to open an issue or discuss in the project's issue tracker.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
