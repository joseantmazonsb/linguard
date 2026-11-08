# Build stage
FROM python:3.12-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first for better caching
COPY backend/requirements.lock.txt .

# Install backend dependencies with all dependencies
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock.txt

# Copy the complete frontend project, including TypeScript project references.
COPY frontend/ /build/frontend/

# Install Node.js
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Build frontend
WORKDIR /build/frontend
RUN npm ci
# tsc -b (type-check) && vite build — via the package.json build script
RUN npm run build
RUN mv /build/frontend/dist /build/frontend-build

WORKDIR /build

# Final stage
FROM python:3.12-slim-bookworm

LABEL maintainer="joseantmazonsb"
LABEL description="Linguard - WireGuard VPN Management"

# Install runtime dependencies incl. all VPN/firewall tooling Linguard drives
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    sudo \
    iptables \
    iproute2 \
    procps \
    wireguard-tools \
    openresolv \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash linguard

# Passwordless sudo for exactly the binaries Linguard manages. Paths are
# resolved at build time so the sudoers file matches the distro layout.
RUN set -eux; \
    cmds="wg wg-quick iptables ip6tables iptables-save iptables-restore ip6tables-save ip6tables-restore sysctl ip ifconfig"; \
    paths=""; \
    for c in $cmds; do \
      p="$(command -v "$c")" || { echo "ERROR: $c not found in image" >&2; exit 1; }; \
      paths="$paths, $p"; \
    done; \
    paths="${paths#, }"; \
    printf 'linguard ALL=(root) NOPASSWD: %s\n' "$paths" > /etc/sudoers.d/linguard; \
    chmod 0440 /etc/sudoers.d/linguard; \
    visudo -c

WORKDIR /app

# Copy wheels from builder
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* --no-deps && rm -rf /wheels

# Copy built frontend
COPY --from=builder /build/frontend-build /app/frontend-build
COPY version.json /app/version.json

# Copy application code, not local databases, backups or venvs.
COPY --chown=linguard:linguard backend/app/ /app/backend/app/

# Create writable directories; the default plugin directory is volume-mounted at runtime.
RUN find /app/backend/app -type d -name __pycache__ -prune -exec rm -rf {} + \
    && mkdir -p /app/data /app/backend/backups /app/backend/plugins \
    && chown -R linguard:linguard /app

# Set PYTHONPATH to include backend
ENV PYTHONPATH=/app/backend

# Persist the database connection config as well as the default SQLite file.
ENV LINGUARD_CONFIG_PATH=/app/data/linguard.config.json
ENV LINGUARD_SQLITE_PATH=/app/data/linguard.db

# Switch to non-root user
USER linguard

# Expose port
EXPOSE 8000

# Set working directory to backend
WORKDIR /app/backend

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application (single process: serves API and frontend)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
