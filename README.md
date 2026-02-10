# 🏔️ Sistem Rekomendasi Wisata Danau Toba

Chatbot cerdas berbasis **RAG + CAG** untuk rekomendasi wisata Danau Toba. Sistem mengambil konteks dari 9 dokumen PDF, lalu mempercepat respon hingga **10x** dengan mekanisme caching.

## 🖼️ Preview UI

![Preview UI](frontend/public/images/page1.png)

## ✨ Fitur

- 🤖 **RAG** - Jawaban berdasarkan dokumen wisata
- ⚡ **CAG** - Caching untuk response cepat
- 🗺️ **Peta Interaktif** - Lokasi wisata dengan Leaflet
- 🎨 **UI Batak Theme** - Desain budaya Batak
- 📊 **Comprehensive Evaluation** - Quantitative & Qualitative metrics

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Gemini 2.0 Flash API |
| **Embeddings** | all-MiniLM-L12-v2 |
| **Vector Store** | FAISS |
| **Backend** | FastAPI |
| **Frontend** | React + Vite |
| **Evaluation** | BERTScore, NLTK, scikit-learn |

## 📊 Evaluation Metrics

Sistem evaluasi lengkap untuk mengukur performa RAG/CAG dan kualitas jawaban:

### Quantitative Metrics
1. **Efficiency**: Response Time, Cache Hit Rate (CHR)
2. **Retrieval**: RAG Recall, Effective Information Rate (EIR)
3. **Generation**: BERTScore (P/R/F1), Completeness, Hallucination Rate, Irrelevancy Score

### Qualitative Metrics
- User Judgment (Relevance, Accuracy, Completeness, Clarity, Usefulness, Overall)

📖 **Documentation**: 
- Complete Guide: [`docs/EVALUATION_METRICS.md`](docs/EVALUATION_METRICS.md)
- Quick Start: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- Implementation Status: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)

## 📂 Struktur

```
├── database/
│   ├── avatars/               # Avatar assets
│   ├── FQA/                   # Dataset FAQ
│   ├── kv_cache/              # Cache responses
│   ├── summary_cache/         # Cache ringkasan
│   ├── vectordatabase/        # Vector DB scripts
│   └── toba_chatbot.db        # SQLite database
├── frontend/
│   ├── public/                # Static assets (images, song)
│   ├── src/                   # React UI
│   └── vite.config.js         # Vite config
├── logs/                      # Logs dan hasil evaluasi
├── models/                    # Model artifacts
├── notebooks/
│   └── Evaluate.ipynb         # Evaluation notebook
├── src/
│   ├── api.py                 # Backend API
│   ├── model.py               # Gemini wrapper
│   ├── cag_system.py          # RAG + CAG pipeline
│   ├── evaluation.py          # Evaluation metrics system
│   └── app.py                 # FastAPI app entry
├── requirements.txt
├── setup_app.sh
├── setup_vps.sh
└── test_response.py
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
cd frontend
npm run dev
```

### 4. Akses

- 🌐 Frontend: http://localhost:3000
- � API Root: http://127.0.0.1:8000/
- 📚 API Docs: http://127.0.0.1:8000/docs

> **💡 Catatan:** 
> - Server backend **bind ke `0.0.0.0:8000`** agar bisa diakses dari jaringan local
> - Di browser, gunakan **`127.0.0.1`** atau **`localhost`** (jangan `0.0.0.0`)
> - Dari device lain di jaringan yang sama, gunakan IP komputer (mis. `192.168.1.x:8000`)

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

## 🧪 Running Evaluation

### Quick Test
```bash
cd src
python run_evaluation.py
```

### Full Evaluation (Jupyter Notebook)
```bash
jupyter notebook notebooks/Evaluate.ipynb
```

Atau copy cells dari `notebooks/evaluation_cells.py` untuk evaluasi lengkap dengan visualisasi.

### Evaluation Output
- Summary table dengan semua metrics
- Visualisasi perbandingan RAG vs CAG
- Detailed JSON results di `logs/evaluation/`
- CSV export untuk analisis lebih lanjut

## 👨‍💻 Author

**TASI-104** - IT Del

---

MIT License © 2024


