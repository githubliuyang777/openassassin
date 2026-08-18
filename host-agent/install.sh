#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO="githubliuyang777/openassassin"

usage() {
    echo "Usage: curl -fsSL https://github.com/${REPO}/releases/latest/download/install.sh | bash -s -- --token <TOKEN> --server <URL>"
    echo ""
    echo "Required:"
    echo "  --token TOKEN     Host agent token from openAssassin platform"
    echo "  --server URL      openAssassin platform URL (e.g. https://ops.example.com)"
    echo ""
    echo "Optional:"
    echo "  --interval SEC    Report interval in seconds (default: 30)"
    exit 1
}

TOKEN=""
SERVER=""
INTERVAL=30
ARCH=$(uname -m)

case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    *)       echo -e "${RED}Unsupported architecture: $ARCH${NC}"; exit 1 ;;
esac

while [[ $# -gt 0 ]]; do
    case $1 in
        --token)    TOKEN="$2"; shift 2 ;;
        --server)   SERVER="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        *)          usage ;;
    esac
done

if [[ -z "$TOKEN" ]] || [[ -z "$SERVER" ]]; then
    usage
fi

echo -e "${GREEN}=== openAssassin Host Agent Installer ===${NC}"
echo "Server:   $SERVER"
echo "Interval: ${INTERVAL}s"
echo "Arch:     $ARCH"
echo ""

INSTALL_PATH="/usr/local/bin/host-agent"
DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/host-agent-linux-${ARCH}"

# Stop existing service if running
if systemctl is-active --quiet host-agent 2>/dev/null; then
    echo "Stopping existing host-agent service..."
    systemctl stop host-agent
fi

# Remove existing binary to avoid overwrite failure
if [ -f "$INSTALL_PATH" ]; then
    echo "Removing existing binary: $INSTALL_PATH"
    rm -f "$INSTALL_PATH"
fi

echo "Downloading host-agent from: $DOWNLOAD_URL"
if command -v curl &> /dev/null; then
    curl -fsSL -o "$INSTALL_PATH" "$DOWNLOAD_URL" || {
        echo -e "${RED}Failed to download host-agent binary${NC}"
        exit 1
    }
elif command -v wget &> /dev/null; then
    wget -q -O "$INSTALL_PATH" "$DOWNLOAD_URL" || {
        echo -e "${RED}Failed to download host-agent binary${NC}"
        exit 1
    }
else
    echo -e "${RED}Neither curl nor wget found. Please install one of them.${NC}"
    exit 1
fi

chmod +x "$INSTALL_PATH"
echo -e "${GREEN}Binary installed to $INSTALL_PATH${NC}"

# Create systemd service
SERVICE_FILE="/etc/systemd/system/host-agent.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=openAssassin Host Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_PATH --server $SERVER --token $TOKEN --interval $INTERVAL
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable --now host-agent

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo "Check status:  systemctl status host-agent"
echo "View logs:     journalctl -u host-agent -f"
