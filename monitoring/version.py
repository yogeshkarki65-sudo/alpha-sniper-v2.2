import os
import json
from datetime import datetime

VERSION_FILE = "/app/version.json"

def get_version_info():
    """
    Retrieve version information from the version file.
    Returns dict with version, git_commit, build_time, and runtime info.
    """
    default_version = {
        "version": "2.2.0",
        "git_commit": "unknown",
        "build_time": "unknown",
        "build_source": "manual"
    }

    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                version_data = json.load(f)
                return version_data
        else:
            # Fallback: try to read from environment variables set at build time
            return {
                "version": os.getenv("APP_VERSION", "2.2.0"),
                "git_commit": os.getenv("GIT_COMMIT", "unknown"),
                "build_time": os.getenv("BUILD_TIME", "unknown"),
                "build_source": "env"
            }
    except Exception as e:
        print(f"Warning: Could not read version info: {e}")
        return default_version

def get_full_version_string():
    """
    Returns a formatted version string for logging.
    Example: "Alpha Sniper v2.2.0 (commit: 0e2e8a0, built: 2025-11-14T17:24:35Z)"
    """
    info = get_version_info()
    commit_short = info.get("git_commit", "unknown")[:7] if info.get("git_commit") != "unknown" else "unknown"

    return f"Alpha Sniper v{info['version']} (commit: {commit_short}, built: {info['build_time']})"
