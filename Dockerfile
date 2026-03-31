# ResearchPulse Backend — Multi-stage Dockerfile
# Builds a slim Python image with the ResearchPulse package installed.

# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY researchpulse/ ./researchpulse/

# Install the package
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code and config
COPY researchpulse/ ./researchpulse/
COPY config.yaml ./config.yaml
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

# Create non-root user
RUN useradd --create-home appuser
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health').raise_for_status()" || exit 1

# Default command: run API server
CMD ["uvicorn", "researchpulse.outputs.dashboard_api:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
