# ── Stage 1: Build Next.js static export ─────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci

COPY app/frontend/ ./
RUN npm run build
# Output lands in /frontend/out


# ── Stage 2: Python / Flask runtime ──────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Pull in the Next.js build output as Flask's static directory
COPY --from=frontend-builder /frontend/out ./static

# Install Python dependencies first (layer-cached unless requirements change)
COPY app/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Flask application
COPY app/backend/ ./

EXPOSE 8000

# 2 workers is plenty for a free-tier instance; adjust as needed
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "server:app"]
