FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies interactively (to ensure lock file is respected)
RUN uv sync --frozen --no-install-project

# ============================================
# Final Image
# ============================================
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies (e.g., ffmpeg is required for this project)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
