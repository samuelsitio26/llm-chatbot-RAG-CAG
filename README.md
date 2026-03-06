# 🏔️ Sistem Rekomendasi Wisata Danau Toba

Chatbot berbasis **Hybrid CAG–RAG** untuk rekomendasi wisata Danau Toba. Sistem mengambil konteks dari dokumen PDF, mempercepat respons dengan mekanisme caching berlapis, dilengkapi autentikasi pengguna, peta interaktif dengan lokasi pengguna, dan 3-Layer Hallucination Guard.

## 🖼️ Preview UI

![Preview UI](frontend/public/images/page1.png)

---

## ✨ Fitur

- 🤖 **RAG** — Jawaban berbasis dokumen wisata PDF (FAISS + cosine similarity)
- ⚡ **CAG** — Staging cache → confirmed cache untuk respons cepat dan terverifikasi
- 🛡️ **3-Layer Hallucination Guard** — Threshold retrieval (0.30), staging cache, net-likes gate
- 🔄 **Auto-Regeneration** — Response buruk di-regen otomatis saat dislike (maks 3×)
- 🗺️ **Peta Interaktif** — Lokasi wisata Leaflet + tombol "Lokasi Saya" (geolocation browser)
- 📏 **Sort by Distance** — Marker diurutkan dari lokasi terdekat pengguna
- 👤 **Autentikasi** — Register/login email+password dan Google OAuth
- 🎨 **UI Batak Theme** — Desain terinspirasi budaya Batak
- 📊 **Comprehensive Evaluation** — Quantitative & Qualitative metrics
- 🔑 **Role-Based Access** — Role `admin`, `operator`, `user`

---

## 🛠️ Tech Stack

| Komponen | Teknologi |
|---|---|
| **LLM** | Gemini 2.5 Flash / 2.5 Pro / 2.0 Flash (rotasi kunci) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L12-v2` |
| **Vector Store** | FAISS (cosine similarity, threshold 0.30) |
| **Backend** | FastAPI + Uvicorn + SQLite |
| **Auth** | Session token (SHA-256+salt) + Google OAuth (Authlib) |
| **Frontend** | React 18 + Vite 5 + React Router v7 |
| **Maps** | Leaflet + React-Leaflet + OpenStreetMap (gratis, tanpa API key) |
| **Geolocation** | Browser `navigator.geolocation` (gratis, tanpa API key) |
| **Evaluation** | BERTScore, ROUGE, NLTK, scikit-learn |

---

## 📂 Struktur Project

```
├── database/
│   ├── avatars/               # Upload foto profil pengguna
│   ├── documents/             # Dokumen PDF sumber RAG
│   ├── FAQ/
│   │   └── faq_tourism.json   # Dataset FAQ untuk pre-populate cache
│   ├── kv_cache/
│   │   └── cache_index.json   # Cache confirmed + staging
│   └── Locations/
│       └── locations.json     # Data lokasi wisata untuk peta
├── frontend/
│   ├── public/                # Static assets (gambar, lagu)
│   ├── src/
│   │   ├── App.jsx            # Halaman chat utama + modal peta
│   │   ├── MapView.jsx        # Komponen peta Leaflet + geolocation
│   │   ├── components/
│   │   │   ├── AdminDashboard.jsx   # Panel admin
│   │   │   ├── Login.jsx            # Halaman login/register
│   │   │   ├── UserProfile.jsx      # Halaman profil pengguna
│   │   │   ├── AuthCallback.jsx     # Callback Google OAuth
│   │   │   ├── ProtectedRoute.jsx   # Guard rute login
│   │   │   └── GuestRoute.jsx       # Guard rute tamu
│   │   └── context/
│   │       └── AuthContext.jsx      # Global state autentikasi
│   ├── package.json
│   └── vite.config.js
├── logs/                      # Log lifecycle cache
├── notebooks/
│   └── Evaluate.ipynb         # Notebook evaluasi lengkap
├── src/
│   ├── api.py                 # FastAPI — semua endpoint
│   ├── hybrid_system.py       # Orchestrator: Cache → FAQ → FAISS → LLM
│   ├── model.py               # Wrapper Gemini REST API
│   ├── kv_cache_manager.py    # Staging + confirmed cache manager
│   ├── manage_cache.py        # Lifecycle cache (hapus/promosi mingguan)
│   ├── clear_invalid_cache.py # Utility bersihkan cache invalid
│   ├── decision_agent.py      # Ekstraksi preferensi dari query
│   ├── database.py            # SQLite: users, sessions, chat history
│   ├── evaluation.py          # Metrics evaluasi (BERTScore, ROUGE, dll.)
│   └── faq_generator.py       # Generator dan pengelola FAQ
├── requirements.txt
├── setup_app.sh
├── setup_vps.sh
└── test_response.py
```

---

## 🚀 Instalasi & Menjalankan (dari Nol)

### Prasyarat

Pastikan sudah terinstal:

| Software | Versi Minimum | Download |
|---|---|---|
| **Python** | 3.10+ | https://www.python.org/downloads/ |
| **Node.js** | 18+ (termasuk npm) | https://nodejs.org/ |
| **Git** | (opsional) | https://git-scm.com/ |

> Cek instalasi: `python --version` dan `node --version`

---

### Langkah 1 — Clone / Ekstrak Project

```bash
# Jika menggunakan Git
git clone <url-repo>
cd Implementasi

# Atau ekstrak ZIP dan masuk ke foldernya
cd Implementasi
```

---

### Langkah 2 — Buat Virtual Environment Python

```bash
# Buat virtual environment
python -m venv .venv

# Aktifkan (Windows)
.venv\Scripts\activate

# Aktifkan (Linux / macOS)
source .venv/bin/activate
```

> Setelah aktif, prompt terminal akan berubah menjadi `(.venv) ...`

---

### Langkah 3 — Install Dependensi Python

```bash
pip install -r requirements.txt
```

> Proses ini mengunduh semua library backend: FastAPI, LangChain, FAISS, sentence-transformers, Gemini client, dll. Bisa memakan waktu beberapa menit.

---

### Langkah 4 — Buat File `.env`

Buat file `.env` di **root folder project** (sejajar dengan `requirements.txt`):

```env
# ── WAJIB ──────────────────────────────────────────
# Dapatkan API key Gemini di: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# String acak panjang untuk enkripsi session (isi bebas, jangan publish)
SECRET_KEY=ganti-dengan-string-acak-yang-panjang-dan-aman

# ── OPSIONAL: Multiple API Key (rotasi otomatis jika satu kena rate limit) ──
# GEMINI_API_KEYS=key1,key2,key3

# ── OPSIONAL: Google OAuth (login dengan akun Google) ──────────────────────
# Jika tidak diisi, fitur "Login dengan Google" tidak aktif
# tapi login email+password tetap berjalan normal
# GOOGLE_CLIENT_ID=your_google_client_id
# GOOGLE_CLIENT_SECRET=your_google_client_secret
# GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
# FRONTEND_URL=http://localhost:3000
```

> ⚠️ File `.env` **tidak boleh di-commit ke Git**. Sudah ada di `.gitignore`.

---

### Langkah 5 — Install Dependensi Frontend

```bash
cd frontend
npm install
```

> Proses ini mengunduh React, Vite, Leaflet, dll. ke folder `frontend/node_modules/`.

---

### Langkah 6 — Jalankan Sistem

Butuh **dua terminal** yang terbuka secara bersamaan.

**Terminal 1 — Backend (FastAPI):**
```bash
# Dari root folder project, dengan .venv aktif
python src/api.py
```

Tunggu hingga muncul output seperti:
```
✅ Model initialized
✅ Embedding model loaded
📄 Loading documents...
🚀 Server started at http://0.0.0.0:8000
```

**Terminal 2 — Frontend (React + Vite):**
```bash
cd frontend
npm run dev
```

Tunggu hingga muncul:
```
  VITE v5.x.x  ready in ...ms
  ➜  Local:   http://localhost:3000/
```

---

### Langkah 7 — Buka di Browser

| Akses | URL |
|---|---|
| 🌐 Aplikasi | http://localhost:3000 |
| 🔌 API | http://localhost:8000 |
| 📚 Swagger Docs | http://localhost:8000/docs |

> **Akun admin default** (dibuat otomatis saat pertama kali dijalankan):
> - Username: `admin`
> - Password: `admin123`
> - ⚠️ Segera ganti password setelah login pertama kali.

---

## 🗺️ Fitur Peta & Geolocation

Klik tombol **Peta Lokasi** di sidebar → Modal peta terbuka:

- **Marker merah** — lokasi wisata dari `database/Locations/locations.json`
- **Tombol "📍 Lokasi Saya"** — klik untuk menemukan posisi Anda menggunakan GPS browser (gratis, tanpa API key)
- **Marker biru** — posisi Anda saat ini
- **Jarak di popup** — setiap marker menampilkan jarak dari posisi Anda (km)
- **Sort terdekat** — marker diurutkan otomatis dari yang paling dekat

> Browser akan meminta izin akses lokasi. Klik "Izinkan" / "Allow".

---

## 📡 API Endpoints

### Chat & Sistem
| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/chat` | POST | Kirim pertanyaan ke chatbot |
| `/api/status` | GET | Status sistem & model |
| `/api/stats` | GET | Statistik cache |
| `/api/locations` | GET | Data lokasi wisata |
| `/api/feedback` | POST | Submit like/dislike |
| `/api/feedback/stats` | GET | Statistik feedback |

### Autentikasi
| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/auth/register` | POST | Daftar akun baru |
| `/api/auth/login` | POST | Login email + password |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Data pengguna aktif |
| `/api/auth/google/login` | GET | Redirect ke Google OAuth |
| `/api/auth/google/callback` | GET | Callback Google OAuth |

### Profil Pengguna
| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/user/profile` | PUT | Update profil |
| `/api/user/change-password` | POST | Ganti password |
| `/api/user/history` | GET | Riwayat chat |
| `/api/user/history` | DELETE | Hapus riwayat chat |
| `/api/user/avatar/upload` | POST | Upload foto profil |

### Admin (Role `admin`)
| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/admin/users` | GET | Daftar semua pengguna |
| `/api/admin/stats` | GET | Statistik sistem |
| `/api/admin/user/{id}` | DELETE | Nonaktifkan pengguna |
| `/api/admin/cache/lifecycle` | GET | Preview lifecycle cache |
| `/api/admin/cache/lifecycle/execute` | POST | Jalankan lifecycle cache |
| `/api/admin/cache/prepopulate` | POST | Pre-populate cache dari FAQ |

### Cache
| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/clear` | POST | Bersihkan cache |
| `/api/optimize` | POST | Optimasi cache |

---

## 👤 Sistem Autentikasi

### Email + Password
- Password di-hash dengan SHA-256 + salt sebelum disimpan
- Login menghasilkan **session token** yang disimpan di SQLite
- Token dikirim sebagai `Authorization: Bearer <token>` di setiap request

### Google OAuth
- Login dengan Google menyimpan `email` dan `name` dari akun Google
- Jika email sudah terdaftar, akun terhubung otomatis

### Role
| Role | Akses |
|---|---|
| `user` | Chat, profil, riwayat |
| `operator` | + manajemen cache |
| `admin` | + semua endpoint admin |

---

## ⚡ Sistem Cache (CAG)

Pipeline respons berjalan dalam urutan:

```
Query Pengguna
    │
    ▼
[1] KV Cache (confirmed) ──── HIT ──▶ Kembalikan respons langsung
    │ MISS
    ▼
[2] FAQ Search ─────────────── MATCH ▶ Kembalikan + simpan ke cache
    │ NO MATCH
    ▼
[3] FAISS Retrieval (RAG) ─── score ≥ 0.30 ──▶ Kirim ke Gemini
    │ score < 0.30
    ▼
[4] Gemini (tanpa konteks) ──▶ Jawaban umum
    │
    ▼
Respons → Staging Cache → (setelah like) → Confirmed Cache
```

### Lifecycle Cache
Dijalankan mingguan (`manage_cache.py`):
- **Hapus**: akses < 5 kali DAN umur > 21 hari
- **Promosi ke FAQ**: akses ≥ 5 kali DAN net-likes ≥ 1
- **Hapus (buruk)**: akses ≥ 5 kali DAN net-likes < 0

---

## 📊 Evaluasi

```bash
# Jalankan notebook evaluasi lengkap
jupyter notebook notebooks/Evaluate.ipynb
```

**Metrics yang dihitung:**
1. **Efficiency**: Response Time, Cache Hit Rate (CHR)
2. **Retrieval**: RAG Recall, Effective Information Rate (EIR)
3. **Generation**: BERTScore (P/R/F1), Completeness, Hallucination Rate, Irrelevancy Score
4. **Qualitative**: Relevance, Accuracy, Completeness, Clarity, Usefulness

---

## 🧹 Utilitas

```bash
# Bersihkan cache yang invalid/korup
python src/clear_invalid_cache.py

# Preview lifecycle cache (dry-run, tidak ada perubahan)
python src/manage_cache.py

# Jalankan lifecycle cache (hapus & promosi)
python src/manage_cache.py --execute

# Test respons chatbot dari terminal
python test_response.py
```

---

## ❓ Troubleshooting

| Masalah | Solusi |
|---|---|
| `ModuleNotFoundError` | Pastikan virtual environment aktif dan `pip install -r requirements.txt` sudah dijalankan |
| `GEMINI_API_KEY not set` | Pastikan file `.env` ada di root folder dan berisi `GEMINI_API_KEY` |
| Backend tidak start | Cek apakah port 8000 sudah dipakai: `netstat -ano \| findstr :8000` |
| Frontend tidak terhubung ke backend | Pastikan backend sudah running di port 8000 sebelum membuka frontend |
| Geolocation tidak bekerja | Izinkan akses lokasi di browser; tidak bekerja di HTTP non-localhost |
| `npm: command not found` | Install Node.js dari https://nodejs.org/ |

---

## 👨‍💻 Author

**TASI-104** — Institut Teknologi Del

---

MIT License © 2025


