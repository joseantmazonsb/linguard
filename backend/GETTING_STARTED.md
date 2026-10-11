# Getting Started with Linguard Backend

This guide will help you set up and run the Linguard backend API server for development.

## Prerequisites

- Python 3.8+
- pip or poetry (for dependency management)
- PostgreSQL, SQLite, or MySQL (database)
- pnpm (for frontend development)

## Setting Up the Backend

### 1. Navigate to the backend directory

```bash
cd /home/jose/projects/linguard/backend
```

### 2. Create a virtual environment

```bash
python3.12 -m venv .venv
```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

**Note:** If you encounter missing dependencies during installation, install them manually:

```bash
pip install email-validator psutil
```

### 5. Configure environment variables

Create a `.env` file in the backend directory:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```
DATABASE_URL=postgresql://user:password@localhost/linguard
SECRET_KEY=your-secret-key-here
```

## Running the Backend Server

### Development Mode

```bash
uvicorn app.main:app --reload --port 8000
```

The server will be available at `http://localhost:8000`

### Production Mode

For production, run without the `--reload` flag:

```bash
uvicorn app.main:app --port 8000
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Frontend Development

To run the frontend alongside the backend:

### 1. Navigate to frontend directory

```bash
cd /home/jose/projects/linguard/frontend
```

### 2. Install dependencies

```bash
pnpm install
```

### 3. Start the frontend dev server

```bash
pnpm dev
```

The frontend will be available at `http://localhost:5173`

## Running Both Frontend and Backend

You can run both servers in separate terminals:

**Terminal 1 (Backend):**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 (Frontend):**
```bash
cd frontend
pnpm dev
```

## Project Structure

```
backend/
├── app/
│   ├── api/              # API endpoints
│   │   ├── system.py     # System monitoring endpoints
│   │   └── ...
│   ├── db/               # Database models and sessions
│   ├── schemas/          # Pydantic schemas
│   ├── utils/            # Utility functions
│   ├── core/             # Core configuration
│   └── main.py           # Application entry point
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
└── alembic/              # Database migrations
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| FastAPI | Web framework |
| SQLAlchemy | ORM |
| Pydantic | Data validation |
| Uvicorn | ASGI server |
| psutil | System monitoring (CPU, memory) |
| email-validator | Email validation |
| cryptography | Encryption |
| asyncpg | PostgreSQL driver |

## Troubleshooting

### Missing dependencies

If you see errors about missing dependencies during `pip install`, run:

```bash
pip install email-validator psutil bcrypt
```

### Database connection errors

Check your `.env` file has the correct `DATABASE_URL`.

### Port already in use

If port 8000 is already in use:

```bash
uvicorn app.main:app --reload --port 8001
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](../LICENSE.md) file for details.
