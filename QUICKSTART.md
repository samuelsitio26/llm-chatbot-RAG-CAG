# ⚡ Quick Start - 3 Langkah Mudah

## 🎯 Cara Menjalankan Sistem (Paling Mudah)

### **Langkah 1: Persiapan**
```bash
cd ~/test/llm-chatbot-rag
conda activate llm-rag
ls data/tourism/*.pdf | wc -l  # Harus ada 9 PDF
```

---

### **Langkah 2: Start Backend (Terminal 1)**
```bash
python src/api.py
```
**Tunggu sampai muncul:** `Uvicorn running on http://0.0.0.0:8000`

---

### **Langkah 3: Start Frontend (Terminal 2 - BARU)**
```bash
# Buka terminal baru (jangan tutup terminal 1!)
conda activate base  # npm ada di base
cd ~/test/llm-chatbot-rag/frontend
npm run dev
```

---

## 🌐 Akses Aplikasi

**Buka browser:**
- **Frontend:** http://172.22.222.118:3000
- **Backend API:** http://172.22.222.118:8000
- **API Docs:** http://172.22.222.118:8000/docs

---

## 🛑 Cara Stop

```bash
# Di masing-masing terminal, tekan:
Ctrl + C

# Atau kill semua process:
pkill -f "api.py"
pkill -f "vite"
```

---

## 🔍 Troubleshooting Cepat

| Problem | Solution |
|---------|----------|
| **npm not found** | `conda activate base` |
| **Port already in use** | `lsof -i :8000` lalu `kill -9 <PID>` |
| **PDF not found** | Copy 9 PDF ke `data/tourism/` |
| **Backend error** | Check: `cat .env` (harus ada token) |

---

## 💡 Tips

**Pakai tmux agar tetap jalan setelah logout:**
```bash
# Start backend
tmux new -d -s backend 'conda activate llm-rag && python src/api.py'

# Start frontend  
tmux new -d -s frontend 'conda activate base && cd frontend && npm run dev'

# Check status
tmux ls

# Stop semua
tmux kill-session -t backend
tmux kill-session -t frontend
```

---

**Dokumentasi lengkap:** Lihat `README.md`
