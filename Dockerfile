# ============================================================
# Retail Lens — production container for Cloud Run
#
# Stage 1 builds the React frontend (VITE_API_BASE_URL=/api so the
# browser calls the same origin — no CORS).
# Stage 2 is the runtime: FastAPI serves both the API and the built
# frontend. Node.js is included because the MCP Toolbox for Databases
# is spawned as a stdio subprocess (npx @toolbox-sdk/server).
#
# Authentication on Cloud Run is via the attached service account
# (ADC through the metadata server) — NO GEMINI_API_KEY required:
#   GOOGLE_GENAI_USE_VERTEXAI=TRUE + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION
# ============================================================

# ---------- Stage 1: build the frontend ----------
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN VITE_API_BASE_URL=/api npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim
WORKDIR /app

# Node.js 22 (nodesource) — required by the MCP Toolbox subprocess.
# Pre-warm the npx cache so the toolbox package is not downloaded on
# the first chat request (cold-start latency).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && npx -y @toolbox-sdk/server --version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY tools.yaml .
COPY --from=frontend-build /build/dist ./frontend/dist

# Vertex AI is the default LLM backend in this container.
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE

EXPOSE 8080
# Cloud Run injects $PORT (default 8080).
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

