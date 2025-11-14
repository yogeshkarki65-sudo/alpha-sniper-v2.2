#!/bin/bash
# Zero-trust deployment script with version validation

set -e

echo "========================================="
echo "🚀 ALPHA SNIPER - ZERO-TRUST DEPLOYMENT"
echo "========================================="

# Step 1: Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "⚠️  Warning: You have uncommitted changes"
    git status -s
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Get current version info
GIT_COMMIT_SHORT=$(git rev-parse --short HEAD)
APP_VERSION="2.2.0"

echo ""
echo "Deploying version:"
echo "  Version: $APP_VERSION"
echo "  Commit:  $GIT_COMMIT_SHORT"
echo ""

# Step 3: Build with version tracking
echo "Building Docker image..."
./deployment/build.sh

# Step 4: Stop existing container
echo ""
echo "Stopping existing container..."
docker compose down

# Step 5: Deploy with version validation
echo ""
echo "Starting with version validation..."
EXPECTED_VERSION=$APP_VERSION EXPECTED_COMMIT=$GIT_COMMIT_SHORT docker compose up -d

# Step 6: Wait for health check
echo ""
echo "Waiting for health check..."
sleep 5

# Step 7: Verify deployment
echo ""
echo "Verifying deployment..."
RESPONSE=$(curl -s http://localhost:8090/health)

if [ $? -eq 0 ]; then
    DEPLOYED_VERSION=$(echo $RESPONSE | jq -r '.version')
    DEPLOYED_COMMIT=$(echo $RESPONSE | jq -r '.git_commit')

    echo ""
    echo "========================================="
    echo "✅ DEPLOYMENT SUCCESSFUL"
    echo "========================================="
    echo "Expected: $APP_VERSION ($GIT_COMMIT_SHORT)"
    echo "Deployed: $DEPLOYED_VERSION ($DEPLOYED_COMMIT)"
    echo ""

    if [ "$DEPLOYED_VERSION" = "$APP_VERSION" ] && [ "$DEPLOYED_COMMIT" = "$GIT_COMMIT_SHORT" ]; then
        echo "✅ Version validation PASSED"
    else
        echo "❌ Version validation FAILED"
        echo ""
        echo "Health response:"
        echo $RESPONSE | jq '.'
        exit 1
    fi
else
    echo "❌ Health check failed"
    echo "Check logs: docker logs alpha-sniper-v2"
    exit 1
fi

echo ""
echo "To view logs:"
echo "  docker logs -f alpha-sniper-v2"
echo ""
echo "To check status:"
echo "  curl http://localhost:8090/health | jq '.'"
