FROM python:3.11-slim

WORKDIR /app

# Install sqlite3 and other system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data logs backups

CMD ["python", "main.py"]
