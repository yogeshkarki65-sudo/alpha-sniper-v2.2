FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck and sqlite3 for database queries
RUN apt-get update && apt-get install -y curl sqlite3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data logs backups

# Capture version information at build time
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown
ARG APP_VERSION=2.2.0

# Create version.json file
RUN echo "{\"version\":\"${APP_VERSION}\",\"git_commit\":\"${GIT_COMMIT}\",\"build_time\":\"${BUILD_TIME}\",\"build_source\":\"docker\"}" > /app/version.json

CMD ["python", "main.py"]
