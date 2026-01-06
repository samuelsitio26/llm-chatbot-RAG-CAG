# 🏔️ Sistem Rekomendasi Wisata Danau Toba
## RAG + CAG dengan UI Batak Cultural Theme

Sistem rekomendasi wisata cerdas menggunakan **RAG (Retrieval-Augmented Generation)** dan **CAG (Cache-Augmented Generation)** dengan model **Google Gemma 2B IT**. Sistem ini memberikan rekomendasi wisata di Danau Toba berdasarkan 9 dokumen PDF dengan response **10x lebih cepat** menggunakan caching.

**🏢 Developed for HPC IT Del**

---

## ✨ Fitur Utama

- 🤖 **RAG System** - Jawaban berdasarkan 9 PDF dokumen wisata Toba
- ⚡ **CAG Caching** - Response 10x lebih cepat untuk query serupa
- 🎨 **UI Batak Theme** - Desain dengan motif budaya Batak dan Danau Toba
- 📊 **Analytics** - Monitor cache hit rate, response time, statistics
- 🎯 **Decision Agent** - Scoring system untuk rekomendasi terbaik
- 🚀 **Dual Frontend** - Pilihan Streamlit (Python) atau React (modern UI)

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Google Gemma 2B IT (HuggingFace) |
| **Embeddings** | sentence-transformers/all-MiniLM-L12-v2 |
| **Vector Store** | FAISS |
| **Backend** | FastAPI + Python |
| **Frontend** | React + Vite / Streamlit |
| **Cache** | K-V Cache + Summary Cache |
| **GPU** | CUDA Support (HPC IT Del)

---

## � Struktur Project

```
llm-chatbot-rag/
├── data/
│   └── tourism/              # 9 PDF dokumen wisata Toba
├── database/
│   ├── kv_cache/            # Cache responses
│   └── summary_cache/       # Cache summaries
├── src/
│   ├── api.py              # FastAPI backend
│   ├── app_cag.py          # Streamlit UI (alternatif)
│   ├── cag_system.py       # CAG pipeline
│   ├── decision_agent.py   # Scoring & ranking
│   ├── evaluation.py       # Performance metrics
│   ├── kv_cache_manager.py # Cache management
│   └── model.py            # LLM wrapper
├── frontend/
│   ├── public/images/      # Logo & background Batak
│   └── src/               # React UI components
├── .env                    # HuggingFace token
└── requirements.txt        # Python dependencies
```

---

## 🚀 Quick Start - Cara Menjalankan

### **Persiapan (Sekali Saja)**

```bash
# 1. Masuk ke folder project
cd ~/test/llm-chatbot-rag

# 2. Aktifkan conda environment
conda activate llm-rag

# 3. Cek dependencies sudah terinstall
pip list | grep -E "torch|transformers|langchain|faiss|fastapi"

# 4. Pastikan ada 9 PDF di folder data/tourism/
ls -la data/tourism/*.pdf | wc -l
# Output harus: 9

# 5. Cek .env file (HuggingFace token)
cat .env
```

---

### **Opsi 1: FastAPI Backend + React Frontend (RECOMMENDED)** 🎨

**Terminal 1 - Backend:**
```bash
conda activate llm-rag
cd ~/test/llm-chatbot-rag
python src/api.py
```

**Terminal 2 - Frontend:**
```bash
conda activate base  # npm ada di base environment
cd ~/test/llm-chatbot-rag/frontend
npm run dev
```

**Akses:**
- Frontend: http://172.22.222.118:3000
- Backend API: http://172.22.222.118:8000
- API Docs: http://172.22.222.118:8000/docs

---

### **Opsi 2: Streamlit (Simple)** 🐍

```bash
conda activate llm-rag
cd ~/test/llm-chatbot-rag
streamlit run src/app_cag.py --server.port 8501 --server.address 0.0.0.0
```

**Akses:** http://172.22.222.118:8501

---

## 📊 Perbandingan Frontend

| Aspek | React (Opsi 1) | Streamlit (Opsi 2) |
|-------|----------------|-------------------|
| **UI Design** | ⭐⭐⭐⭐⭐ Modern, Batak theme, animasi | ⭐⭐⭐ Simple, functional |
| **Setup** | Butuh 2 terminal (backend + frontend) | Hanya 1 terminal |
| **Performance** | Fast, responsive | Good |
| **Customization** | Sangat flexible | Limited |
| **Recommended For** | Demo, presentasi, production | Testing, quick prototype |

---

## 🎯 Fitur CAG (Cache-Augmented Generation)

### **Apa itu CAG?**
Cache-Augmented Generation menyimpan response untuk query yang serupa, sehingga query berikutnya **10x lebih cepat**!

### **Cara Kerja:**
1. **Query Pertama (Cache MISS):** Generate response (2-5 detik)
2. **Query Serupa (Cache HIT):** Ambil dari cache (0.1-0.5 detik) ⚡

### **Test CAG:**
```bash
# Query 1 (slow - generate baru)
Tanya: "Rekomendasi pantai untuk honeymoon budget 10 juta"
Response: ~3 detik

# Query 2 (fast - dari cache)
Tanya: "Rekomendasi pantai untuk honeymoon budget 10 juta"
Response: ~0.3 detik ⚡ (10x lebih cepat!)
```

---

## 🎨 UI Batak Cultural Theme

Frontend React memiliki desain khusus dengan tema budaya Batak:

### **Fitur Visual:**
- 🏔️ **Hero Section** - Logo Batak besar dengan animasi floating
- 🌊 **Background** - Foto Danau Toba dengan opacity
- 🎨 **Warna** - Merah (#dc2626), Hitam (#1a1a1a), Emas (#fbbf24)
- ✨ **Animasi** - Float, slide, pulse, bounce (60fps)
- 💬 **Welcome** - Greeting "Horas!" dengan 6 example queries

### **Gambar yang Digunakan:**
- `logo.png` - Logo motif Batak (120px di hero)
- `slide_bar.jpg` - Logo kecil di header
- `latarbelakang.jpg` - Background Danau Toba
- `example.jpg` - Hero background

---

## 📈 Performance & Statistics

### **Monitoring:**
- ✅ Cache hit rate
- ✅ Response time (cached vs non-cached)
- ✅ Total queries processed
- ✅ Most popular queries
- ✅ Recommendation scores

### **Access Statistics:**
- **React UI:** Klik tombol "📊 Statistics"
- **Streamlit UI:** Klik "📈 Show Stats" di sidebar
- **API:** `curl http://localhost:8000/api/stats`
---

## 🐛 Troubleshooting

### **Problem: Backend tidak menemukan PDF**
```bash
# Cek apakah ada 9 PDF
ls -la data/tourism/*.pdf | wc -l

# Jika kurang dari 9, copy PDF Anda
cp /path/to/your/*.pdf data/tourism/
```

### **Problem: Port already in use**
```bash
# Cari process yang pakai port
lsof -i :8000  # atau :3000 untuk frontend

# Kill process
kill -9 <PID>
```

### **Problem: npm command not found**
```bash
# npm ada di environment base
conda deactivate
conda activate base
cd ~/test/llm-chatbot-rag/frontend
npm run dev
```

### **Problem: Model loading error**
```bash
# Cek GPU
nvidia-smi

# Cek CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Jika False, akan fallback ke CPU (lebih lambat)
```

---

## 💡 Tips & Best Practices

### **Untuk Development:**
```bash
# Run dengan tmux (persistent setelah logout)
tmux new-session -d -s backend 'conda activate llm-rag && python src/api.py'
tmux new-session -d -s frontend 'conda activate base && cd frontend && npm run dev'

# Check sessions
tmux list-sessions

# Attach to session
tmux attach -t backend

# Detach: Ctrl+B lalu D
```

### **Untuk Production:**
```bash
# Build frontend
cd frontend
npm run build

# Serve dengan production server
npm run preview
```

### **Maintenance:**
```bash
# Optimize cache (hapus item jarang dipakai)
curl -X POST http://localhost:8000/api/optimize

# Clear semua cache
curl -X POST http://localhost:8000/api/clear

# View statistics
curl http://localhost:8000/api/stats | python -m json.tool
```

---

## 📊 API Endpoints

### **Backend (Port 8000):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System health check |
| `/api/chat` | POST | Send query & get response |
| `/api/stats` | GET | Cache statistics |
| `/api/optimize` | POST | Optimize cache |
| `/api/clear` | POST | Clear all cache |
| `/docs` | GET | Interactive API documentation |

### **Example API Call:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Rekomendasi pantai untuk honeymoon",
    "use_cache": true,
    "k": 5,
    "session_id": "test123"
  }'
```

---

## 🎓 Untuk Pengembangan Lebih Lanjut

### **Tambah Fitur Baru:**
1. Edit `src/cag_system.py` untuk logic RAG/CAG
2. Edit `src/decision_agent.py` untuk scoring system
3. Edit `frontend/src/App.jsx` untuk UI React
4. Edit `src/app_cag.py` untuk Streamlit UI

### **Customize UI Theme:**
- Edit `frontend/src/App.css` untuk styling
- Ganti gambar di `frontend/public/images/`
- Ubah warna di `:root` variables

### **Add More PDFs:**
1. Copy PDF ke `data/tourism/`
2. Restart backend
3. System akan auto-load PDF baru

---

## 📝 License

MIT License - Copyright (c) 2024

---

## 🙏 Acknowledgments

- **HPC IT Del** - Infrastructure & GPU support
- **HuggingFace** - Model hosting (Google Gemma 2B)
- **LangChain** - RAG framework
- **FAISS** - Vector search engine

---

## 📞 Support

Jika mengalami masalah:
1. Check terminal logs (backend & frontend)
2. Verify 9 PDF files ada di `data/tourism/`
3. Test API: `curl http://localhost:8000/api/status`
4. Check browser console (F12) untuk frontend errors

**System Requirements:**
- ✅ GPU: CUDA-capable (5GB+ VRAM recommended)
- ✅ RAM: 16GB+ recommended
- ✅ Disk: 20GB+ free space (untuk models & cache)
- ✅ Python: 3.10+
- ✅ Node.js: 18+ (untuk React frontend)

---

**Happy Coding!** 🚀

**Torch Path Warning (Dapat Diabaikan)**
```
Examining the path of torch.classes raised: Tried to instantiate class '__path__._path'...
```
✅ Internal warning, tidak mempengaruhi fungsi

**Port Sudah Digunakan:**
```bash
streamlit run src/app.py --server.port 8502
```

**Out of Memory (OOM) Error:**
- Model membutuhkan ~5GB VRAM
- Cek usage: `nvidia-smi`
- Stop proses lain yang menggunakan GPU

---
## 📩 Requirements

- **Python 3.8+** (Recommended: 3.10)
- **HPC IT Del Environment**: Conda atau Virtual Environment
- **GPU (Optional)**: NVIDIA GPU dengan CUDA untuk performa lebih cepat
- Libraries listed in `requirements.txt`

### Verifikasi GPU (Opsional):
```bash
python -c "import torch; print('GPU Available:', torch.cuda.is_available())"
```

---

## 💡 Use Cases

- 📄 **Document Q&A**: Ask questions about technical manuals, reports, papers

- 📚 **Research Assistant**: Quickly find information from academic papers

- 📋 **Policy Analysis**: Query company policies, legal documents, regulations

- 🏥 **Medical Records**: Search through patient records or medical literature

- 📖 **Learning Tool**: Interactive way to study from textbooks and notes

- 🏢 **Enterprise Knowledge Base**: Internal documentation assistant

---

## 🔐 Privacy & Offline Use
This chatbot supports offline embeddings using Hugging Face or Llama models. You are free from vendor lock-in and API rate limits.



---

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/yashdew3/ragbot/issues) (if you have one) or open a new issue to discuss changes. Pull requests are also appreciated.

---

## 🧑‍💻 Author

- **Built by**: Leon
- **Adapted for HPC IT Del**: tasi2425112
- **Infrastructure**: HPC IT Del with CUDA GPU Support
- **Model**: Google Gemma 2B IT via HuggingFace Transformers