# 🏔️ Sistem Rekomendasi Wisata Danau Toba

Chatbot cerdas berbasis **RAG + CAG** untuk rekomendasi wisata Danau Toba. Sistem mengambil konteks dari dokumen PDF, mempercepat respon dengan mekanisme caching berlapis, dilengkapi autentikasi pengguna, dan 3-Layer Hallucination Guard.

## 🖼️ Preview UI

![Preview UI](frontend/public/images/page1.png)

## ✨ Fitur

- 🤖 **RAG** - Jawaban berdasarkan dokumen wisata (PDF)
- ⚡ **CAG** - Staging cache → confirmed cache untuk response cepat dan terverifikasi
- 🛡️ **3-Layer Hallucination Guard** - Threshold retrieval, staging cache, net-likes gate
- 🔄 **Auto-Regeneration** - Response buruk di-regen otomatis saat dislike (maks 3x)
- 🗺️ **Peta Interaktif** - Lokasi wisata dengan Leaflet
- 👤 **Autentikasi Pengguna** - Register/login email+password dan Google OAuth
- 🎨 **UI Batak Theme** - Desain budaya Batak
- 📊 **Comprehensive Evaluation** - Quantitative & Qualitative metrics
- 🔑 **Role-Based Access** - Role `admin`, `operator`, `user`

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Gemini 2.5 Flash API |
| **Embeddings** | sentence-transformers/all-MiniLM-L12-v2 |
| **Vector Store** | FAISS (cosine similarity) |
| **Backend** | FastAPI + SQLite |
| **Auth** | Bearer token + Google OAuth (Authlib) |
| **Frontend** | React 18 + Vite + React Router v7 |
| **Maps** | Leaflet + React-Leaflet |
| **Evaluation** | BERTScore, ROUGE, NLTK, scikit-learn |

## 📊 Evaluation Metrics

Sistem evaluasi lengkap untuk mengukur performa RAG/CAG dan kualitas jawaban:

### Quantitative Metrics
1. **Efficiency**: Response Time, Cache Hit Rate (CHR)
2. **Retrieval**: RAG Recall, Effective Information Rate (EIR)
3. **Generation**: BERTScore (P/R/F1), Completeness, Hallucination Rate, Irrelevancy Score

### Qualitative Metrics
- User Judgment (Relevance, Accuracy, Completeness, Clarity, Usefulness, Overall)

## 📂 Struktur

```
├── database/
│   ├── avatars/               # Upload foto profil pengguna
│   ├── FAQ/                   # Dataset FAQ (faq_tourism.json)
│   ├── kv_cache/              # Cache responses (cache_index.json)
│   ├── Locations/             # Data lokasi wisata (locations.json)
│   ├── summary_cache/         # Cache ringkasan
│   ├── vectordatabase/        # Dokumen PDF sumber RAG
│   └── toba_chatbot.db        # SQLite database (users, sessions, history)
├── frontend/
│   ├── public/                # Static assets (images, song)
│   ├── src/
│   │   ├── App.jsx            # Halaman chat utama
│   │   ├── MapView.jsx        # Halaman peta interaktif
│   │   ├── components/        # AdminDashboard, Login, UserProfile, dll.
│   │   └── context/           # AuthContext (state login global)
│   └── vite.config.js
├── logs/                      # Logs dan hasil evaluasi
├── models/                    # Model artifacts
├── notebooks/
│   └── Evaluate.ipynb         # Evaluation notebook
├── src/
│   ├── api.py                 # FastAPI entry point (semua endpoint)
│   ├── model.py               # Gemini API wrapper
│   ├── cag_system.py          # RAG + CAG pipeline (orchestrator)
│   ├── decision_agent.py      # Query analyzer & preference extractor
│   ├── kv_cache_manager.py    # Staging + confirmed cache manager
│   ├── manage_cache.py        # Weekly lifecycle cache manager
│   ├── database.py            # SQLite user & session management
│   ├── evaluation.py          # Evaluation metrics
│   └── faq_generator.py       # FAQ generator dari PDF
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

Buat file `.env` di root project:
```env
# Wajib
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your-random-secret-key-here

# Opsional — untuk Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_URL=http://localhost:3000
```

> **⚠️ Catatan `.env`:**
> - `SECRET_KEY` digunakan untuk mengenkripsi session OAuth. Isi dengan string acak yang panjang.
> - Tanpa `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, fitur **Login dengan Google tidak akan berfungsi**, tapi login email+password tetap normal.
> - Jika dijalankan di laptop teman, pastikan file `.env` ikut disalin — file ini **tidak ter-commit di git**.

### 3. Jalankan

**Terminal 1 — Backend:**
```bash
python src/api.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### 4. Akses

- 🌐 Frontend: http://localhost:3000
- 🔌 API Root: http://127.0.0.1:8000/
- 📚 API Docs (Swagger): http://127.0.0.1:8000/docs

> **💡 Catatan Jaringan:**
> - Server backend **bind ke `0.0.0.0:8000`** agar bisa diakses dari jaringan lokal.
> - Di browser, gunakan **`127.0.0.1`** atau **`localhost`** (bukan `0.0.0.0`).
> - Dari device lain di jaringan yang sama, gunakan IP komputer (mis. `192.168.1.x:8000`).
> - Jika diakses dari laptop teman di jaringan berbeda, pastikan port 8000 dan 3000 tidak diblokir firewall.

## 📡 API Endpoints

### Chat & System
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/chat` | POST | Kirim pertanyaan ke chatbot |
| `/api/status` | GET | Cek status sistem & model |
| `/api/stats` | GET | Statistik cache |
| `/api/locations` | GET | Data lokasi wisata |
| `/api/feedback` | POST | Submit like/dislike response |
| `/api/feedback/stats` | GET | Statistik feedback |

### Autentikasi
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/auth/register` | POST | Daftar akun baru (email, username, password) |
| `/api/auth/login` | POST | Login dengan username + password |
| `/api/auth/logout` | POST | Logout (hapus session) |
| `/api/auth/me` | GET | Data pengguna yang sedang login |
| `/api/auth/validate` | GET | Validasi token aktif |
| `/api/auth/google/login` | GET | Redirect ke Google OAuth |
| `/api/auth/google/callback` | GET | Callback setelah Google OAuth |

### Profil Pengguna
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/user/profile` | PUT | Update nama, bio, lokasi, kategori favorit |
| `/api/user/change-password` | POST | Ganti password |
| `/api/user/history` | GET | Riwayat chat |
| `/api/user/history` | DELETE | Hapus riwayat chat |
| `/api/user/activity` | GET | Log aktivitas pengguna |
| `/api/user/avatar/upload` | POST | Upload foto profil (file) |
| `/api/user/avatar/base64` | POST | Upload foto profil (base64/emoji) |
| `/api/avatars/{filename}` | GET | Serve file avatar |

### Admin (Butuh Role `admin`)
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/admin/users` | GET | Daftar semua pengguna |
| `/api/admin/stats` | GET | Statistik sistem & feedback |
| `/api/admin/user/{id}` | DELETE | Nonaktifkan pengguna |
| `/api/admin/cache/lifecycle` | GET | Preview lifecycle cache |
| `/api/admin/cache/lifecycle/execute` | POST | Jalankan lifecycle cache |
| `/api/admin/cache/prepopulate` | POST | Pre-populate cache dari FAQ |

### Cache Management
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/api/clear` | POST | Bersihkan cache |
| `/api/optimize` | POST | Optimasi cache |

## 👤 Sistem Autentikasi

### Registrasi & Login Email
Saat register, data yang disimpan ke database:
- `username` (unik)
- `email` (unik)
- `password` (di-hash dengan SHA-256 + salt)
- `name`, `avatar`, `role` (default: `user`)

Login menggunakan `username` + `password`, menghasilkan **session token** yang disimpan di SQLite dan dikirim sebagai `Bearer token` di header.

### Google OAuth
Login dengan Google menyimpan `email` dan `name` dari akun Google ke database. Jika email sudah terdaftar, akun akan terhubung otomatis.

### Role
| Role | Akses |
|------|-------|
| `user` | Chat, profil, riwayat |
| `operator` | + manajemen cache |
| `admin` | + semua endpoint admin |

## 📝 Contoh Query

- "Rekomendasi hotel di Parapat"
- "Tempat makan enak di Samosir"
- "Wisata populer di Danau Toba"
- "Dimana lokasi Air Terjun Situmurun?"

## 🧪 Running Evaluation

### Full Evaluation (Jupyter Notebook)
```bash
jupyter notebook notebooks/Evaluate.ipynb
```

### Evaluation Output
- Summary table dengan semua metrics
- Visualisasi perbandingan RAG vs CAG
- Detailed JSON results di `logs/evaluation/`

## 👨‍💻 Author

**TASI-104** - IT Del

---

MIT License © 2024

