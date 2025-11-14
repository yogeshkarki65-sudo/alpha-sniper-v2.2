#!/bin/bash
# Build script for Alpha Sniper with version tracking

set -e

# Get git commit hash (full and short)
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_COMMIT_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Get current timestamp in ISO 8601 format
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Version number
APP_VERSION="2.2.0"

# Image name
IMAGE_NAME="alpha-sniper"

echo "========================================="
echo "Building Alpha Sniper V2"
echo "========================================="
echo "Version:     $APP_VERSION"
echo "Git Commit:  $GIT_COMMIT"
echo "Short Hash:  $GIT_COMMIT_SHORT"
echo "Build Time:  $BUILD_TIME"
echo "Image Tags:  $IMAGE_NAME:$GIT_COMMIT_SHORT, $IMAGE_NAME:latest"
echo "========================================="

# Build with docker compose, passing build args
docker compose build \
  --build-arg GIT_COMMIT="$GIT_COMMIT" \
  --build-arg BUILD_TIME="$BUILD_TIME" \
  --build-arg APP_VERSION="$APP_VERSION"

# Tag the image with commit hash for version tracking
echo ""
echo "🏷️  Tagging image with commit hash..."
docker tag alpha-sniper-v2:latest $IMAGE_NAME:$GIT_COMMIT_SHORT
docker tag alpha-sniper-v2:latest $IMAGE_NAME:$APP_VERSION
docker tag alpha-sniper-v2:latest $IMAGE_NAME:latest

echo ""
echo "✅ Build complete!"
echo ""
echo "Images tagged:"
echo "  - $IMAGE_NAME:$GIT_COMMIT_SHORT (commit-specific)"
echo "  - $IMAGE_NAME:$APP_VERSION (version-specific)"
echo "  - $IMAGE_NAME:latest (alias)"
echo ""
echo "To start the bot, run:"
echo "  docker compose up -d"
echo ""
echo "To check version:"
echo "  curl http://localhost:8090/health"
echo ""
echo "To view all images:"
echo "  docker images | grep $IMAGE_NAME"
