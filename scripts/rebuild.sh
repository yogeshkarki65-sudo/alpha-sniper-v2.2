#!/bin/bash
# Quick rebuild script with version tracking

set -e

echo "🔄 Rebuilding Alpha Sniper V2..."

# Capture version info
export GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
export GIT_COMMIT_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export APP_VERSION="2.2.0"

echo "📦 Version: $APP_VERSION"
echo "🔖 Commit: $GIT_COMMIT_SHORT"
echo "⏰ Build Time: $BUILD_TIME"
echo ""

# Stop container
echo "⏹️  Stopping container..."
docker compose down

# Build with version info
echo "🔨 Building..."
docker compose build

# Start container
echo "▶️  Starting container..."
docker compose up -d

echo ""
echo "✅ Rebuild complete!"
echo ""
echo "📊 Check status:"
echo "  docker logs -f alpha-sniper-v2"
echo ""
echo "🏥 Check health:"
echo "  curl http://localhost:8090/health | python3 -m json.tool"
