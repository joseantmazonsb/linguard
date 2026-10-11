# Development Guide

This document provides detailed technical information for developers working on Linguard.

## Architecture Overview

### Tech Stack

- **Backend:** Python 3.8+, FastAPI, SQLAlchemy, Pydantic
- **Frontend:** JavaScript/TypeScript, React, Vite
- **Database:** PostgreSQL, SQLite, or MySQL
- **Authentication:** JWT tokens with bcrypt password hashing, OIDC SSO support

### Project Layout

```
linguard/
├── backend/              # Python backend
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── core/        # Core configuration
│   │   ├── db/          # Database layer
│   │   ├── schemas/     # Pydantic models
│   │   ├── services/    # Background services (monitoring, firewall, etc.)
│   │   ├── utils/       # Utility functions
│   │   └── main.py      # Application entry
│   ├── requirements.txt
│   └── alembic/         # Database migrations
├── frontend/            # Frontend application
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   └── services/    # API services
│   └── package.json
├── docs/                # Documentation
└── docker/              # Docker configurations
```

## Backend Development

### API Structure

All API endpoints follow RESTful conventions:

- **Base URL:** `/api/v1`
- **Authentication:** Bearer token in Authorization header
- **Response format:** JSON

Example endpoint structure:

```python
from fastapi import APIRouter, Depends, HTTPException
from app.db.session import get_db
from app.schemas.interface import InterfaceResponse

router = APIRouter()

@router.get("/interfaces", response_model=List[InterfaceResponse])
async def get_interfaces(db: Session = Depends(get_db)):
    interfaces = InterfaceModel.get_all(db)
    return interfaces
```

### Database Models

Database models are located in `app/db/models.py`:

```python
from sqlalchemy import Column, Integer, String, DateTime
from app.db.base import Base

class InterfaceModel(Base):
    __tablename__ = "interfaces"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Pydantic Schemas

Schemas define request/response validation:

```python
from pydantic import BaseModel, EmailStr, field_validator

class InterfaceCreate(BaseModel):
    name: str
    ip_range: str
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > 50:
            raise ValueError('Name must be 50 characters or less')
        return v
```

### Authentication System

JWT-based authentication with bcrypt password hashing:

1. User registers via POST `/api/v1/auth/register`
2. Server generates JWT token
3. Client includes token in Authorization header
4. Server validates token on protected routes

### System Monitoring

The `app/api/system.py` module provides system monitoring:

```python
import psutil

def get_system_info():
    mem = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)
    
    return {
        'memory': {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent
        },
        'cpu': cpu_percent
    }
```

**Note:** `psutil` must be installed:
```bash
pip install psutil==5.9.0
```

## Frontend Development

### Component Structure

Components follow a consistent pattern:

```tsx
interface InterfaceProps {
  data: InterfaceData;
  onChange: (data: InterfaceData) => void;
}

const InterfaceComponent: React.FC<InterfaceProps> = ({ data, onChange }) => {
  return (
    <div className="interface-card">
      <h3>{data.name}</h3>
      {/* Component content */}
    </div>
  );
};
```

### API Services

Services handle API communication:

```typescript
const authService = {
  login: async (email: string, password: string) => {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      throw new Error('Login failed');
    }
    
    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    return data;
  }
};
```

### State Management

Frontend uses React hooks for state management:

```typescript
const [user, setUser] = useState<User | null>(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
```

## Database Migrations

### Creating a Migration

```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "Add new field"
alembic upgrade head
```

### Migration Structure

```python
def upgrade():
    op.create_table('new_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('new_table')
```

## Testing

### Backend Tests

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_get_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Linguard API"}
```

Run tests:
```bash
cd backend
source .venv/bin/activate
pytest
```

### Frontend Tests

```typescript
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from '../App';

test('renders without crashing', () => {
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
  expect(screen.getByText(/Linguard/i)).toBeInTheDocument();
});
```

Run tests:
```bash
cd frontend
pnpm test
```

## Environment Variables

### Backend (.env)

```
DATABASE_URL=postgresql://user:password@localhost/linguard
SECRET_KEY=your-secret-key-here
DEBUG=True
LOG_LEVEL=DEBUG
```

### Frontend (.env)

```
VITE_API_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Linguard
```

## Deployment Considerations

### Environment Variables

- Set `DEBUG=False` in production
- Use strong `SECRET_KEY`
- Configure proper `LOG_LEVEL`

### Database

- Use PostgreSQL in production
- Enable SSL connections
- Set up automatic backups

### Security

- Enable HTTPS
- Use strong passwords
- Implement rate limiting
- Sanitize all user inputs

## Troubleshooting

### Common Issues

#### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:** Check DATABASE_URL in .env file

#### Port Already in Use

```
ERROR: failed to bind to 0.0.0.0:8000: address already in use
```

**Solution:** Kill process or use different port

```bash
uvicorn app.main:app --reload --port 8001
```

#### Virtual Environment Not Found

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:** Activate virtual environment

```bash
source .venv/bin/activate
```

## Code Quality

### Linting

Backend:
```bash
cd backend
source .venv/bin/activate
ruff check .
```

Frontend:
```bash
cd frontend
pnpm lint
```

### Formatting

Backend:
```bash
ruff format .
```

Frontend:
```bash
cd frontend
pnpm format
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [React Documentation](https://react.dev/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## License

MIT License - see [LICENSE.md](../LICENSE.md) for details.
