#!/bin/bash
# ==================================================
# 🚀 Toba Chatbot - Automatic VPS Setup Script
# Run this on your VPS after SSH login
# ==================================================

set -e  # Exit on error

echo "=================================================="
echo "🏔️ TOBA TOURISM CHATBOT - VPS SETUP"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Update System
echo -e "${YELLOW}[1/8] Updating system...${NC}"
sudo apt update && sudo apt upgrade -y

# Step 2: Install Dependencies
echo -e "${YELLOW}[2/8] Installing dependencies...${NC}"
sudo apt install -y git curl wget unzip software-properties-common

# Install Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Nginx
sudo apt install -y nginx

# Step 3: Create app directory
echo -e "${YELLOW}[3/8] Setting up directories...${NC}"
sudo mkdir -p /var/www/toba-chatbot
cd /var/www/toba-chatbot

echo -e "${GREEN}✓ System setup complete!${NC}"
echo ""
echo "=================================================="
echo "📦 NEXT STEPS:"
echo "=================================================="
echo ""
echo "1. Upload your code to /var/www/toba-chatbot"
echo "   From your LOCAL machine, run:"
echo "   scp -r \"D:/Semester 8/TA II/Implementasi/*\" root@76.13.192.172:/var/www/toba-chatbot/"
echo ""
echo "2. After upload, run the app setup script:"
echo "   cd /var/www/toba-chatbot"
echo "   chmod +x setup_app.sh"
echo "   ./setup_app.sh"
echo ""
echo "=================================================="
