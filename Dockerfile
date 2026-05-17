FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cached layer)
COPY pyproject.toml uv.lock* ./

# Install dependencies into the system python (no venv inside Docker)
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY ./app ./app

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]