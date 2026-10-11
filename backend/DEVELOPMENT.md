# Backend Development Guide

This guide provides detailed information for developing the Linguard backend API.

## Quick Start

### 1. Setup Virtual Environment

```bash
cd /home/jose/projects/linguard/backend
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If installation fails due to missing dependencies, install them manually:

```bash
pip install email-validator psutil bcrypt cryptography
```

### 3. Configure Database

Edit `.env` file:

```
DATABASE_URL=sqlite:///./linguard.db
# OR for PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/linguard
```

### 4. Run Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
app/
├── api/              # API route handlers
│   ├── auth.py       # Authentication endpoints
│   ├── interface.py  # Interface management
│   ├── peer.py       # Peer management
│   └── system.py     # System monitoring
├── core/             # Core configuration
│   ├── config.py     # Application settings
│   └── security.py   # Security utilities
├── db/               # Database layer
│   ├── session.py    # Database session management
│   ├── base.py       # Base model
│   └── models.py     # SQLAlchemy models
├── schemas/          # Pydantic schemas
│   ├── auth.py       # Authentication schemas
│   ├── interface.py  # Interface schemas
│   └── peer.py       # Peer schemas
├── utils/            # Utility functions
│   ├── validation.py # Data validation
│   └── helpers.py    # Helper functions
└── main.py           # Application entry point
```

## Database Models

### Creating a New Model

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.sql import func
from app.db.base import Base
from datetime import datetime

class PeerModel(Base):
    __tablename__ = "peers"
    
    id = Column(Integer, primary_key=True, index=True)
    interface_id = Column(Integer, ForeignKey("interfaces.id"), nullable=False)
    public_key = Column(String, nullable=False)
    preset = Column(String, default="default")
    name = Column(String, nullable=True)
    allowed_ips = Column(String, nullable=False)
    endpoint = Column(String, nullable=True)
    persistent_keepalive = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Database Session Management

```python
from app.db.session import SessionLocal, get_db

def get_interfaces(db: Session = Depends(get_db)):
    interfaces = InterfaceModel.get_all(db)
    return interfaces
```

## API Endpoints

### Defining a New Endpoint

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.interface import InterfaceCreate, InterfaceResponse
from app.core.config import get_settings

router = APIRouter()

@router.post(
    "/interfaces",
    response_model=InterfaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new WireGuard interface"
)
async def create_interface(
    interface_data: InterfaceCreate,
    db: Session = Depends(get_db),
    settings = Depends(get_settings)
):
    """
    Create a new WireGuard interface.
    
    - **interface_data**: Interface creation data
    - **db**: Database session
    """
    
    # Check if interface with this name already exists
    existing = InterfaceModel.get_by_name(db, name=interface_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interface '{interface_data.name}' already exists"
        )
    
    # Create new interface
    new_interface = InterfaceModel(
        name=interface_data.name,
        private_key=generate_private_key(),
        public_key=generate_public_key(interface_data.private_key),
        listen_port=settings.WIREGUARD_PORT
    )
    
    db.add(new_interface)
    db.commit()
    db.refresh(new_interface)
    
    return InterfaceResponse.model_validate(new_interface)
```

## Request/Response Schemas

### Creating a Schema

```python
from pydantic import BaseModel, field_validator, EmailStr
from typing import Optional

class InterfaceCreate(BaseModel):
    """Schema for creating a new interface."""
    name: str
    private_key: Optional[str] = None
    listen_port: Optional[int] = 51820
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate interface name."""
        if not v.strip():
            raise ValueError('Name cannot be empty')
        if len(v) > 50:
            raise ValueError('Name must be 50 characters or less')
        return v.strip()

class InterfaceResponse(InterfaceCreate):
    """Schema for interface response."""
    id: int
    public_key: str
    created_at: datetime
    
    class Config:
        from_attributes = True
```

## Authentication

### JWT Token Generation

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.core.config import settings

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt
```

### Password Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

## System Monitoring

The system monitoring module uses `psutil` for CPU and memory monitoring:

```python
import psutil
from fastapi import APIRouter, Depends
from app.db.session import get_db

router = APIRouter()

@router.get("/system")
async def get_system_info():
    """Get current system information."""
    # Memory information
    mem = psutil.virtual_memory()
    
    # CPU information
    cpu_percent = psutil.cpu_percent(interval=None)
    
    # Disk information
    disk = psutil.disk_usage('/')
    
    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total": mem.total,
            "available": mem.available,
            "percent": mem.percent
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "percent": disk.percent
        }
    }
```

**Important:** `psutil` must be installed:

```bash
pip install psutil==5.9.0
```

## Validation Utilities

The `app/utils/validation.py` module provides utility functions:

```python
from pydantic import BaseModel, field_validator, validator
from typing import Optional
import re

def validate_email(value: Optional[str], field_name: str = "Email") -> Optional[str]:
    """
    Validate an email address.
    
    Args:
        value: The email to validate
        field_name: The field name for error messages
        
    Returns:
        The validated and stripped email, or None if empty
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        return None
    
    stripped = value.strip()
    if not stripped:
        return None
    
    # Basic email pattern validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, stripped):
        raise ValueError(f"{field_name} must be a valid email address")
    
    if len(strippied) > 254:  # RFC 5321
        raise ValueError(f"{field_name} must not exceed 254 characters")
    
    return stripped
```

## Testing

### Setting Up Test Environment

```bash
cd backend
source .venv/bin/activate
```

### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

# Override settings for testing
settings.DEBUG = True

def test_create_interface(client: TestClient):
    """Test creating a new interface."""
    response = client.post(
        "/api/v1/interfaces",
        json={"name": "test-interface", "private_key": "test-key"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-interface"
    assert "public_key" in data
```

### Running Tests

```bash
pytest
```

Or with coverage:

```bash
pytest --cov=app --cov-report=html
```

## Dependencies

### Adding a New Dependency

1. Add to `requirements.txt`:
   ```
   package_name==version
   ```

2. Install in virtual environment:
   ```bash
   pip install package_name
   ```

3. Import in code:
   ```python
   import package_name
   ```

### Currently Used Dependencies

- `psutil==5.9.0` - System monitoring (CPU, memory)
- `email-validator` - Email validation (may need manual install)
- `bcrypt` - Password hashing
- `cryptography` - Cryptographic operations

## Environment Variables

```
DATABASE_URL=sqlite:///./linguard.db
SECRET_KEY=your-secret-key-here
DEBUG=True
LOG_LEVEL=DEBUG
WIREGUARD_PORT=51820
```

## Common Issues

### Missing psutil Module

```
ModuleNotFoundError: No module named 'psutil'
```

**Solution:**
```bash
pip install psutil==5.9.0
```

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
1. Check DATABASE_URL in .env
2. Ensure database server is running
3. Verify credentials are correct

### Port Already in Use

```
ERROR: failed to bind to 0.0.0.0:8000: address already in use
```

**Solution:**
```bash
uvicorn app.main:app --reload --port 8001
```

Or kill the process:
```bash
lsof -ti:8000 | xargs kill -9
```

## API Documentation

Once running, access the API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
