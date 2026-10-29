# Stage 1: build the officer console (React + TypeScript + Vite)
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# Stage 2: the verification service (FastAPI + engines), serving the built console
FROM python:3.12-slim
WORKDIR /srv/backend
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /srv/frontend/dist
ENV PYTHONUNBUFFERED=1
RUN useradd -m satya && chown -R satya /srv
USER satya
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
