#!/bin/bash
# ==================================================
# 🚀 Toba Chatbot - App Setup Script
# Run this after uploading code to VPS
# ==================================================

set -e

echo "=================================================="
echo "🏔️ SETTING UP TOBA CHATBOT APPLICATION"
echo "=================================================="

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd /var/www/toba-chatbot

# Step 1: Setup Python Backend
echo -e "${YELLOW}[1/5] Setting up Python backend...${NC}"
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Backend dependencies installed${NC}"

# Step 2: Build Frontend
echo -e "${YELLOW}[2/5] Building frontend...${NC}"
cd frontend
npm install
npm run build
cd ..
echo -e "${GREEN}✓ Frontend built${NC}"

# Step 3: Create Systemd Service
echo -e "${YELLOW}[3/5] Creating backend service...${NC}"
sudo tee /etc/systemd/system/toba-backend.service > /dev/null << EOF
[Unit]
Description=Toba Tourism Chatbot Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/toba-chatbot
Environment="PATH=/var/www/toba-chatbot/.venv/bin"
ExecStart=/var/www/toba-chatbot/.venv/bin/python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable toba-backend
sudo systemctl start toba-backend
echo -e "${GREEN}✓ Backend service created${NC}"

# Step 4: Configure Nginx
echo -e "${YELLOW}[4/5] Configuring Nginx...${NC}"
sudo tee /etc/nginx/sites-available/toba-chatbot > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    root /var/www/toba-chatbot/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}
EOF

sudo ln -sf /etc/nginx/sites-available/toba-chatbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
echo -e "${GREEN}✓ Nginx configured${NC}"

# Step 5: Configure Firewall
echo -e "${YELLOW}[5/5] Configuring firewall...${NC}"
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
echo -e "${GREEN}✓ Firewall configured${NC}"

# Final check
echo ""
echo "=================================================="
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
echo "=================================================="
echo ""
echo "Your app is now running at:"
echo "  📱 Frontend: http://$(curl -s ifconfig.me)"
echo "  🔌 API: http://$(curl -s ifconfig.me)/api/status"
echo ""
echo "Useful commands:"
echo "  - View backend logs: sudo journalctl -u toba-backend -f"
echo "  - Restart backend: sudo systemctl restart toba-backend"
echo "  - Restart nginx: sudo systemctl restart nginx"
echo ""
