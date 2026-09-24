#!/bin/bash

# Salary Reconciliation Agent - Linux deployment (systemd)
#
# Installs scheduler.py as a systemd service that runs continuously. Schedule:
#   14th 09:00  EPF upload reminder
#   16th 18:00  full monthly run (RMS download -> reconcile -> email report)
#
# On macOS use install_launchd.sh instead.

echo "=================================="
echo "Salary Reconciliation Agent Setup"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Variables - Updated paths
AGENT_DIR="$HOME/Downloads/Agent/Reconciliation"
SERVICE_NAME="salary-reconciliation-agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
USER="$SUDO_USER"

# If SUDO_USER is not set (running as actual root), use the current user
if [ -z "$USER" ]; then
    USER=$(whoami)
fi

echo "Installation Details:"
echo "  Agent Directory: $AGENT_DIR"
echo "  Service Name: $SERVICE_NAME"
echo "  Running as User: $USER"
echo ""

echo "Step 1: Verifying directory exists..."
if [ ! -d "$AGENT_DIR" ]; then
    echo "ERROR: Directory $AGENT_DIR does not exist!"
    echo "Please ensure the agent is extracted to: $AGENT_DIR"
    exit 1
fi
echo "✓ Directory verified"
echo ""

echo "Step 2: Installing Python dependencies..."
cd "$AGENT_DIR"
pip3 install -r requirements-agent.txt
echo "✓ Dependencies installed (browser + reconciliation core)"
echo ""

echo "Step 3: Creating systemd service..."
cat > $SERVICE_FILE << EOF
[Unit]
Description=Salary Reconciliation Agent (EPF reminder on the 14th, monthly run on the 16th)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 $AGENT_DIR/scheduler.py
Restart=always
RestartSec=10
StandardOutput=append:$AGENT_DIR/logs/service.log
StandardError=append:$AGENT_DIR/logs/service_error.log

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Service file created"
echo ""

echo "Step 4: Setting up directories and permissions..."
mkdir -p "$AGENT_DIR"/{downloads,epf_uploads,reports,logs}
chown -R $USER:$USER "$AGENT_DIR"
chmod 600 "$AGENT_DIR/.env" 2>/dev/null || echo "Note: .env file not found yet (will be created by user)"
echo "✓ Directories configured"
echo ""

echo "Step 5: Reloading systemd..."
systemctl daemon-reload
echo "✓ Systemd reloaded"
echo ""

echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Verify .env file exists and has correct credentials:"
echo "   nano $AGENT_DIR/.env"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "3. Enable auto-start on boot:"
echo "   sudo systemctl enable $SERVICE_NAME"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "5. Check what is due and what has already run:"
echo "   python3 $AGENT_DIR/scheduler.py --status"
echo ""
echo "6. Run a job immediately (do not wait for the calendar):"
echo "   python3 $AGENT_DIR/scheduler.py --run-now recon"
echo ""
echo "7. View logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo "   OR"
echo "   tail -f $AGENT_DIR/logs/service.log"
echo ""
echo "=================================="
