FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Environment variables must be supplied at runtime — never embed credentials here.
ENV GEMINI_API_KEY=""
ENV GOOGLE_CLOUD_PROJECT=""
ENV GOOGLE_CLOUD_LOCATION=""

# Serve the FastAPI app (app.main is a Milestone-1 connectivity check script,
# not a server).  Env vars GEMINI_API_KEY / GOOGLE_CLOUD_PROJECT must be
# supplied at runtime (e.g. docker run --env-file .env).
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
