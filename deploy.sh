#!/bin/bash

echo "=========================================="
echo "Alpha Sniper V2 - Quick Deploy Script"
echo "=========================================="

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Install it first:"
    echo "sudo apt update && sudo apt install python3 python3-pip -y"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Create directories
echo ""
echo "Creating required directories..."
mkdir -p data logs backups

# Setup .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env created. IMPORTANT: Edit .env and add your Telegram credentials!"
    echo ""
    echo "To edit: nano .env"
    echo ""
    echo "Required settings:"
    echo "  - TELEGRAM_BOT_TOKEN (get from @BotFather)"
    echo "  - TELEGRAM_CHAT_ID (get from @userinfobot)"
    echo ""
    read -p "Press Enter to continue after you've edited .env..."
else
    echo "✅ .env file already exists"
fi

# Ask deployment method
echo ""
echo "Choose deployment method:"
echo "1) Test run (foreground - for testing)"
echo "2) Screen session (simple background)"
echo "3) Systemd service (production - recommended)"
echo "4) Docker (if docker-compose installed)"
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "Starting test run..."
        echo "Press Ctrl+C to stop"
        python3 main.py
        ;;
    2)
        echo ""
        echo "Starting in screen session..."
        screen -dmS alpha-sniper python3 main.py
        echo "✅ Bot started in background!"
        echo ""
        echo "Useful commands:"
        echo "  View bot: screen -r alpha-sniper"
        echo "  Detach: Ctrl+A then D"
        echo "  Stop bot: screen -r alpha-sniper then Ctrl+C"
        ;;
    3)
        echo ""
        echo "Creating systemd service..."

        # Get current user and path
        CURRENT_USER=$(whoami)
        CURRENT_PATH=$(pwd)

        # Create service file
        SERVICE_FILE="/tmp/alpha-sniper.service"
        cat > $SERVICE_FILE << EOF
[Unit]
Description=Alpha Sniper Trading Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_PATH
ExecStart=/usr/bin/python3 $CURRENT_PATH/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        echo "Moving service file to /etc/systemd/system/"
        sudo mv $SERVICE_FILE /etc/systemd/system/alpha-sniper.service

        echo "Enabling and starting service..."
        sudo systemctl daemon-reload
        sudo systemctl enable alpha-sniper
        sudo systemctl start alpha-sniper

        echo ""
        echo "✅ Service installed and started!"
        echo ""
        echo "Useful commands:"
        echo "  Status: sudo systemctl status alpha-sniper"
        echo "  Logs: sudo journalctl -u alpha-sniper -f"
        echo "  Stop: sudo systemctl stop alpha-sniper"
        echo "  Restart: sudo systemctl restart alpha-sniper"
        echo ""
        echo "Checking status..."
        sleep 2
        sudo systemctl status alpha-sniper --no-pager
        ;;
    4)
        echo ""
        echo "Starting with Docker..."
        docker-compose up -d
        echo ""
        echo "✅ Docker containers started!"
        echo ""
        echo "Useful commands:"
        echo "  Logs: docker-compose logs -f"
        echo "  Stop: docker-compose down"
        echo "  Restart: docker-compose restart"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor health: curl http://localhost:8080/health"
echo "2. Check Telegram for alerts"
echo "3. Run in SIM mode for 7-14 days before going LIVE"
echo ""
echo "Emergency stop: curl -X POST http://localhost:8081/emergency-stop"
echo ""
