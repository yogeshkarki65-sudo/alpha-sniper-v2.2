#!/bin/bash
#
# V4.1 Deployment Script
#
# This script copies all V4.1 patch files from this repository
# to your server's alpha-sniper-v2.2 directory.
#
# Usage:
#   1. Clone this repository to your local machine
#   2. SSH to your server
#   3. Run this script from the repository root
#

set -e  # Exit on error

echo "========================================="
echo "Alpha Sniper V4.1 Deployment Script"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "V4.1_PATCH_NOTES.md" ]; then
    echo "❌ Error: V4.1_PATCH_NOTES.md not found"
    echo "Please run this script from the repository root"
    exit 1
fi

# Get target directory (default: current directory)
TARGET_DIR="${1:-.}"

echo "📁 Target directory: $TARGET_DIR"
echo ""

# Create necessary directories
echo "📂 Creating directories..."
mkdir -p "$TARGET_DIR/v3/data"
mkdir -p "$TARGET_DIR/v3/regime"
mkdir -p "$TARGET_DIR/v3/scanner"
mkdir -p "$TARGET_DIR/v3/risk"
mkdir -p "$TARGET_DIR/v3/monitoring"
echo "✅ Directories created"
echo ""

# Copy all V4.1 files
echo "📋 Copying V4.1 patch files..."

# New files
cp -v v3/scanner/bear_resilient_long.py "$TARGET_DIR/v3/scanner/"
cp -v v3/monitoring/status_reporter.py "$TARGET_DIR/v3/monitoring/"

# Complete V4 files with bug fixes
cp -v v3/data/mexc_client.py "$TARGET_DIR/v3/data/"
cp -v v3/regime/detector.py "$TARGET_DIR/v3/regime/"
cp -v v3/scanner/features.py "$TARGET_DIR/v3/scanner/"
cp -v v3/scanner/signals.py "$TARGET_DIR/v3/scanner/"
cp -v v3/risk/risk_engine.py "$TARGET_DIR/v3/risk/"

# Configuration and documentation
cp -v .env.example "$TARGET_DIR/"
cp -v V4.1_PATCH_NOTES.md "$TARGET_DIR/"

echo "✅ All files copied"
echo ""

# Create __init__.py files if needed
echo "📝 Creating __init__.py files..."
touch "$TARGET_DIR/v3/__init__.py"
touch "$TARGET_DIR/v3/data/__init__.py"
touch "$TARGET_DIR/v3/regime/__init__.py"
touch "$TARGET_DIR/v3/scanner/__init__.py"
touch "$TARGET_DIR/v3/risk/__init__.py"
touch "$TARGET_DIR/v3/monitoring/__init__.py"
echo "✅ __init__.py files created"
echo ""

echo "========================================="
echo "✅ V4.1 Deployment Complete!"
echo "========================================="
echo ""
echo "📚 Next steps:"
echo ""
echo "1. Review the patch notes:"
echo "   cat $TARGET_DIR/V4.1_PATCH_NOTES.md"
echo ""
echo "2. Update your .env file:"
echo "   cp $TARGET_DIR/.env.example $TARGET_DIR/.env"
echo "   nano $TARGET_DIR/.env"
echo ""
echo "3. Test the status reporter:"
echo "   cd $TARGET_DIR"
echo "   source venv/bin/activate"
echo "   python3 -c \"from v3.monitoring.status_reporter import status_reporter; status_reporter.print_status()\""
echo ""
echo "4. Restart your bot:"
echo "   pkill -f v3_main.py"
echo "   python3 v3_main.py --mode SIM"
echo ""
echo "🎉 Happy trading!"
echo ""
