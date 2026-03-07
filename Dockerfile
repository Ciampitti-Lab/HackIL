# Part 1: Build Next.js static export
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci

COPY app/frontend/ ./
RUN npm run build


# Part 2: Python / Flask runtime
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY --from=frontend-builder /frontend/out ./static

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY pipelines/ ./pipelines/
COPY models/ ./models/
COPY data/processed/ ./data/processed/

COPY app/backend/ ./

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "server:app"]
