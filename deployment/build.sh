#!/bin/bash
# Build script for Alpha Sniper with version tracking

set -e

# Get git commit hash
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Get current timestamp in ISO 8601 format
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Version number
APP_VERSION="2.2.0"

echo "========================================="
echo "Building Alpha Sniper V2"
echo "========================================="
echo "Version:     $APP_VERSION"
echo "Git Commit:  $GIT_COMMIT"
echo "Build Time:  $BUILD_TIME"
echo "========================================="

# Build with docker compose, passing build args
docker compose build \
  --build-arg GIT_COMMIT="$GIT_COMMIT" \
  --build-arg BUILD_TIME="$BUILD_TIME" \
  --build-arg APP_VERSION="$APP_VERSION"

echo ""
echo "✅ Build complete!"
echo ""
echo "To start the bot, run:"
echo "  docker compose up -d"
echo ""
echo "To check version:"
echo "  curl http://localhost:8090/health"
