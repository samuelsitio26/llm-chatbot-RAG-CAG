# 🏔️ Sistem Rekomendasi Wisata Danau Toba

Chatbot cerdas menggunakan **RAG + CAG** untuk rekomendasi wisata Danau Toba berbasis 9 dokumen PDF dengan response **10x lebih cepat** menggunakan caching.

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

Sistem evaluasi lengkap untuk mengukur performa RAG/CAG:

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
├── data/
│   ├── tourism/              # 9 PDF dokumen wisata
│   └── evaluation_dataset.json  # Test dataset untuk evaluasi
├── database/
│   ├── kv_cache/             # Cache responses
│   └── user_judgments.json   # User evaluation data
├── src/
│   ├── api.py                # Backend API
│   ├── model.py              # Gemini wrapper
│   ├── cag_system.py         # RAG + CAG pipeline
│   ├── evaluation.py         # ✨ Evaluation metrics system
│   └── run_evaluation.py     # ✨ Evaluation runner
├── notebooks/
│   ├── Evaluate.ipynb        # Evaluation notebook
│   └── evaluation_cells.py   # ✨ Ready-to-use cells
├── docs/                     # ✨ Documentation
└── frontend/src/             # React UI
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

## � Running Evaluation

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

## �👨‍💻 Author

**TASI-104** - IT Del

---

MIT License © 2024
