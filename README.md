# 🏔️ Sistem Rekomendasi Wisata Danau Toba

Chatbot cerdas menggunakan **RAG + CAG** untuk rekomendasi wisata Danau Toba berbasis 9 dokumen PDF dengan response **10x lebih cepat** menggunakan caching.

## ✨ Fitur

- 🤖 **RAG** - Jawaban berdasarkan dokumen wisata
- ⚡ **CAG** - Caching untuk response cepat
- 🗺️ **Peta Interaktif** - Lokasi wisata dengan Leaflet
- 🎨 **UI Batak Theme** - Desain budaya Batak

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Gemini 2.0 Flash API |
| **Embeddings** | all-MiniLM-L12-v2 |
| **Vector Store** | FAISS |
| **Backend** | FastAPI |
| **Frontend** | React + Vite |

## 📂 Struktur

```
├── data/tourism/        # 9 PDF dokumen wisata
├── database/kv_cache/   # Cache responses
├── src/
│   ├── api.py           # Backend API
│   ├── model.py         # Gemini wrapper
│   └── cag_system.py    # RAG + CAG pipeline
└── frontend/src/        # React UI
```

## 🚀 Cara Menjalankan

### 1. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 2. Setup Environment

Buat file `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

### 3. Jalankan

**Terminal 1 - Backend:**
```bash
python src/api.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```

### 4. Akses

- 🌐 Frontend: http://localhost:3000
- 📚 API Docs: http://localhost:8000/docs

## 📡 API Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/chat` | POST | Kirim pertanyaan |
| `/api/status` | GET | Cek status sistem |
| `/api/stats` | GET | Statistik cache |

## 📝 Contoh Query

- "Rekomendasi hotel di Parapat"
- "Tempat makan enak di Samosir"
- "Wisata populer di Danau Toba"

## 👨‍💻 Author

**TASI-104** - IT Del

---

MIT License © 2024
