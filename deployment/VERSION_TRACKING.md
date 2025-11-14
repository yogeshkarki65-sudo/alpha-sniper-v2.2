# Version Tracking Guide

## Overview
Alpha Sniper V2 now includes comprehensive version tracking to help you verify which code is running on your server.

## Quick Check
To quickly check the version running on your server:
```bash
curl http://localhost:8090/health
```

Or from a remote machine:
```bash
curl http://YOUR_SERVER_IP:8090/health
```

Example response:
```json
{
  "status": "healthy",
  "version": "2.2.0",
  "git_commit": "0e2e8a0",
  "build_time": "2025-11-14T17:24:35Z",
  "uptime": "2h 15m",
  "current_equity": 10000.00,
  "open_positions_count": 3,
  "daily_pnl": 150.25,
  "last_scanner_run": "2025-11-14T19:30:00",
  "last_trader_run": "2025-11-14T19:30:15"
}
```

## Building with Version Tracking

### Option 1: Use the Build Script (Recommended)
```bash
cd ~/alpha-sniper-v2.2
./deployment/build.sh
```

This script automatically:
- Captures the current git commit hash
- Records the build timestamp
- Passes version information to Docker
- Creates the container with full version tracking

### Option 2: Manual Docker Build
```bash
GIT_COMMIT=$(git rev-parse HEAD)
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker compose build \
  --build-arg GIT_COMMIT="$GIT_COMMIT" \
  --build-arg BUILD_TIME="$BUILD_TIME" \
  --build-arg APP_VERSION="2.2.0"
```

## Deployment Workflow

### Initial Deployment
```bash
# 1. Pull latest code
cd ~/alpha-sniper-v2.2
git pull origin main

# 2. Build with version tracking
./deployment/build.sh

# 3. Start the bot
docker compose up -d

# 4. Verify version
curl http://localhost:8090/health | jq '.version, .git_commit, .build_time'
```

### Update Workflow
```bash
# 1. Pull new code
git pull origin main

# 2. Rebuild with new version
./deployment/build.sh

# 3. Restart
docker compose down
docker compose up -d

# 4. Verify the new version is running
curl http://localhost:8090/health
```

## Version Information Details

### Version Fields
- **version**: Semantic version number (e.g., "2.2.0")
- **git_commit**: Short git commit hash (first 7 characters)
- **build_time**: ISO 8601 timestamp when the Docker image was built
- **uptime**: How long the current instance has been running

### Where Version Info Appears

1. **Startup Logs**
   ```
   ============================================================
   🚀 ALPHA SNIPER V2 - Starting...
   ============================================================
   📦 Alpha Sniper v2.2.0 (commit: 0e2e8a0, built: 2025-11-14T17:24:35Z)
   ============================================================
   ```

2. **Health Check Endpoint**
   - Available at: `http://YOUR_SERVER:8090/health`
   - Returns JSON with full version details

3. **Telegram Alerts**
   - Startup message includes version and commit hash
   - Format: "🚀 Alpha Sniper V2 started successfully\n📦 Version: 2.2.0 (commit: 0e2e8a0)"

## Verification Examples

### Check if server is running latest code
```bash
# On your local machine
LOCAL_COMMIT=$(git rev-parse HEAD | cut -c1-7)

# On your server (or via curl)
SERVER_COMMIT=$(curl -s http://YOUR_SERVER:8090/health | jq -r '.git_commit')

if [ "$LOCAL_COMMIT" = "$SERVER_COMMIT" ]; then
    echo "✅ Server is running the latest code"
else
    echo "⚠️  Version mismatch!"
    echo "   Local:  $LOCAL_COMMIT"
    echo "   Server: $SERVER_COMMIT"
fi
```

### Monitor version in Telegram
When your bot starts or restarts, you'll automatically receive a Telegram message with the version information.

### Check container build time
```bash
docker inspect alpha-sniper-v2 | grep Created
```

Compare this with the `build_time` from the health endpoint to ensure they match.

## Troubleshooting

### Version shows as "unknown"
This happens if the container was built without the build script. To fix:
```bash
./deployment/build.sh
docker compose up -d
```

### Health endpoint returns different commit than expected
1. Verify git status: `git log -1 --format="%H %s"`
2. Rebuild the container: `./deployment/build.sh`
3. Restart: `docker compose restart`

### Build time doesn't match container creation time
Small differences are normal (build vs run time). Large differences suggest the container wasn't rebuilt after code changes.

## Best Practices

1. **Always use build.sh**: Don't use `docker compose build` directly
2. **Check version after deployment**: Verify with health endpoint
3. **Include version in bug reports**: Copy the full health endpoint response
4. **Tag releases in git**: Use git tags for production deployments
   ```bash
   git tag -a v2.2.0 -m "Release 2.2.0"
   git push origin v2.2.0
   ```

## Integration with CI/CD

If you set up automated deployments, ensure your CI/CD pipeline:
1. Uses the `build.sh` script
2. Passes the correct git commit hash
3. Verifies version after deployment
4. Sends notifications with version info

Example GitHub Actions snippet:
```yaml
- name: Build with version
  run: ./deployment/build.sh

- name: Verify deployment
  run: |
    curl http://${{ secrets.SERVER_IP }}:8090/health
```
