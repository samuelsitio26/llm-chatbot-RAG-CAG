# 🚀 Panduan Deployment VPS Hostinger
## Sistem Rekomendasi Wisata Danau Toba

### 📋 Informasi VPS
- **OS**: Ubuntu 22.04 LTS
- **IP**: 76.13.192.172
- **SSH**: `ssh root@76.13.192.172`

---

## 🔧 LANGKAH 1: Koneksi ke VPS

Buka terminal/PowerShell dan jalankan:
```bash
ssh root@76.13.192.172
```
Masukkan password root (dari Hostinger panel).

---

## 🔧 LANGKAH 2: Update System & Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y git curl wget unzip software-properties-common

# Install Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Nginx
sudo apt install -y nginx

# Install Certbot for SSL (optional but recommended)
sudo apt install -y certbot python3-certbot-nginx

# Check versions
python3.11 --version
node --version
npm --version
nginx -v
```

---

## 🔧 LANGKAH 3: Clone Repository

```bash
# Create app directory
sudo mkdir -p /var/www/toba-chatbot
cd /var/www/toba-chatbot

# Clone your repository (atau upload manual dengan SCP)
# Option 1: Clone dari GitHub (jika repo ada di GitHub)
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .

# Option 2: Upload manual dari local (jalankan di LOCAL terminal, bukan VPS)
# scp -r "D:/Semester 8/TA II/Implementasi/*" root@76.13.192.172:/var/www/toba-chatbot/
```

---

## 🔧 LANGKAH 4: Setup Backend (Python/FastAPI)

```bash
cd /var/www/toba-chatbot

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create environment file
cat > .env << EOF
MODEL_PATH=models/
DEBUG=False
HOST=0.0.0.0
PORT=8000
EOF

# Test backend (should run without errors)
python -c "from src.api import app; print('Backend OK!')"
```

---

## 🔧 LANGKAH 5: Setup Frontend (React/Vite)

```bash
cd /var/www/toba-chatbot/frontend

# Install dependencies
npm install

# Create production build
npm run build

# The build output will be in /var/www/toba-chatbot/frontend/dist
```

---

## 🔧 LANGKAH 6: Create Systemd Service untuk Backend

```bash
# Create service file
sudo cat > /etc/systemd/system/toba-backend.service << EOF
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

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable toba-backend
sudo systemctl start toba-backend

# Check status
sudo systemctl status toba-backend
```

---

## 🔧 LANGKAH 7: Configure Nginx

```bash
# Create Nginx config
sudo cat > /etc/nginx/sites-available/toba-chatbot << EOF
server {
    listen 80;
    server_name 76.13.192.172;  # Ganti dengan domain jika ada

    # Frontend (React)
    root /var/www/toba-chatbot/frontend/dist;
    index index.html;

    # Handle React Router
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API Proxy
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }

    # Static files caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/toba-chatbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

---

## 🔧 LANGKAH 8: Configure Firewall

```bash
# Allow HTTP, HTTPS, and SSH
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Check status
sudo ufw status
```

---

## 🔧 LANGKAH 9: (Optional) Setup SSL dengan Domain

Jika Anda punya domain:
```bash
# Point domain A record to 76.13.192.172
# Then run:
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## 🔧 LANGKAH 10: Update Frontend untuk Production

Di file `frontend/src/context/AuthContext.jsx`, ubah API URL:
```javascript
// Ubah dari:
const API_BASE = 'http://localhost:8000/api';

// Menjadi:
const API_BASE = '/api';  // Relative URL untuk production
```

Dan di `frontend/vite.config.js`, tambahkan proxy untuk development:
```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 📝 Commands Cheatsheet

```bash
# Restart backend
sudo systemctl restart toba-backend

# View backend logs
sudo journalctl -u toba-backend -f

# Restart nginx
sudo systemctl restart nginx

# View nginx logs
sudo tail -f /var/log/nginx/error.log

# Rebuild frontend
cd /var/www/toba-chatbot/frontend && npm run build

# Pull latest code (jika menggunakan Git)
cd /var/www/toba-chatbot && git pull
```

---

## 🔍 Troubleshooting

### Backend tidak jalan:
```bash
# Check status
sudo systemctl status toba-backend

# Check logs
sudo journalctl -u toba-backend -n 50

# Test manual
cd /var/www/toba-chatbot
source .venv/bin/activate
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

### Frontend tidak tampil:
```bash
# Check nginx error
sudo tail -f /var/log/nginx/error.log

# Check if build exists
ls -la /var/www/toba-chatbot/frontend/dist/
```

### Port 8000 sudah dipakai:
```bash
# Find process
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>
```

---

## 🎉 Testing

Setelah semua selesai, buka browser dan akses:
- **Frontend**: http://76.13.192.172
- **API Status**: http://76.13.192.172/api/status

---

## 📞 Need Help?

Jika ada error, jalankan:
```bash
# Collect all logs
sudo journalctl -u toba-backend -n 100 > /tmp/backend.log
sudo tail -100 /var/log/nginx/error.log > /tmp/nginx.log
cat /tmp/backend.log /tmp/nginx.log
```

Copy output error-nya dan tanyakan lagi!
