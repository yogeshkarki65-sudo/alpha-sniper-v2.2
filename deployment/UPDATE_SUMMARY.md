# Alpha Sniper V2.2 - Version Tracking Update

## Summary
Implemented comprehensive version tracking system to verify which code version is running on the server.

## What Was Added

### 1. Version Tracking Module
- **File**: `monitoring/version.py`
- Reads version metadata from build-time captured data
- Provides formatted version strings for logging and display

### 2. Enhanced Docker Build Process
- **File**: `Dockerfile` (modified)
- Captures git commit hash at build time via ARG variables
- Records ISO 8601 build timestamp
- Creates `/app/version.json` with all metadata
- Added curl for healthcheck support

### 3. Automated Build Script
- **File**: `deployment/build.sh` (new, executable)
- Single command to build with full version tracking
- Auto-captures: git commit hash, build timestamp, version number
- Shows build info in console output

### 4. Enhanced Health Check Endpoint
- **File**: `monitoring/healthcheck.py` (modified)
- Added version, git_commit, build_time, and uptime fields
- Allows remote version verification without SSH
- Endpoint: `http://SERVER_IP:8090/health`

### 5. Startup Improvements
- **File**: `main.py` (modified)
- Displays version information in startup logs
- Sends version info in Telegram startup alerts
- Format: "Alpha Sniper v2.2.0 (commit: 0993672, built: 2025-11-14T17:45:00Z)"

## How to Use

### Build with Version Tracking
```bash
cd ~/alpha-sniper-v2
./deployment/build.sh
```

### Deploy
```bash
docker compose down
docker compose up -d
```

### Verify Version
```bash
# Local check
curl http://localhost:8090/health

# Remote check
curl http://YOUR_SERVER_IP:8090/health

# Extract just version info
curl -s http://localhost:8090/health | jq '.version, .git_commit, .build_time'
```

### Example Health Response
```json
{
  "status": "healthy",
  "version": "2.2.0",
  "git_commit": "0993672",
  "build_time": "2025-11-14T17:45:00Z",
  "uptime": "2h 15m",
  "current_equity": 10000.00,
  "open_positions_count": 3,
  "daily_pnl": 150.25,
  "last_scanner_run": "2025-11-14T19:30:00",
  "last_trader_run": "2025-11-14T19:30:15"
}
```

## Benefits

1. **Quick Verification**: Check running version with single curl command
2. **No SSH Required**: Verify version remotely via HTTP endpoint
3. **Automatic Alerts**: Telegram notifications include version info
4. **Deployment Confidence**: Confirm correct code deployed before trading
5. **Troubleshooting**: Include version in bug reports and logs
6. **Audit Trail**: Build time and commit hash for compliance

## Technical Details

### Version Components
- **version**: Semantic version (2.2.0)
- **git_commit**: Full commit hash (shortened to 7 chars in display)
- **build_time**: ISO 8601 timestamp of Docker build
- **uptime**: Runtime duration since container start

### Build Arguments
The Dockerfile accepts these build-time arguments:
- `GIT_COMMIT`: Git commit hash from `git rev-parse HEAD`
- `BUILD_TIME`: UTC timestamp in ISO 8601 format
- `APP_VERSION`: Semantic version number (default: 2.2.0)

### Files Modified
- `Dockerfile` - Added version capture and curl installation
- `main.py` - Added version display and Telegram alerts
- `monitoring/healthcheck.py` - Enhanced with version endpoint

### Files Created
- `monitoring/version.py` - Version info module
- `deployment/build.sh` - Automated build script
- `deployment/VERSION_TRACKING.md` - Comprehensive documentation
- `deployment/UPDATE_SUMMARY.md` - This file

## Git Information
- **Branch**: `claude/verify-latest-version-01ArCikn5t78UcBM7JxPLCaj`
- **Commit**: `0993672`
- **Commit Message**: "Add comprehensive version tracking system"

## Next Steps

1. Pull the latest code from the branch
2. Run `./deployment/build.sh` to build with version tracking
3. Deploy with `docker compose up -d`
4. Verify with `curl http://localhost:8090/health`
5. Monitor Telegram for startup message with version info

## Important Notes

⚠️ **Always use `./deployment/build.sh`** instead of `docker compose build` directly to ensure version information is captured.

📚 **Full documentation** available in `deployment/VERSION_TRACKING.md`

🔍 **Troubleshooting**: If version shows "unknown", rebuild using the build script
