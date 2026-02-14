FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Install build tools (needed for tgcrypto on Python 3.13)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies interactively (to ensure lock file is respected)
RUN uv sync --frozen --no-install-project

# ============================================
# Final Image
# ============================================
FROM python:3.13-slim-bookworm

WORKDIR /app

# Install system dependencies (ffmpeg for remuxing, mkvtoolnix for font extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mkvtoolnix \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
