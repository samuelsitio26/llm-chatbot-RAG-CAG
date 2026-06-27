# 🏔️ Danau Toba Tourism Recommendation System

A **Hybrid CAG-RAG** chatbot for Danau Toba tourism recommendations. The system retrieves context from PDF documents, uses a layered cache to speed up responses, stores conversation history per thread, supports feedback and answer regeneration, and includes user authentication, an interactive map with user geolocation, and a 3-Layer Hallucination Guard.

## 🖼️ UI Preview
![Preview UI](frontend/public/images/page1.png)

---

## ✨ Features

- 🤖 **RAG** — Document-grounded answers from tourism PDFs (FAISS + cosine similarity)
- ⚡ **CAG** — Staging cache → confirmed cache for fast and validated responses
- 🛡️ **3-Layer Hallucination Guard** — Retrieval threshold (0.30), staging cache, net-likes gate
- 🔄 **Auto-Regeneration** — Poor answers can be regenerated and compared as answer variants
- 🗺️ **Interactive Map** — Tourism locations via Leaflet + "My Location" button (browser geolocation)
- 📏 **Sort by Distance** — Markers automatically sorted by nearest to user location
- 👤 **Authentication** — Email + password registration/login + Google OAuth
- 🎨 **Batak Theme UI** — Visual style inspired by Batak culture
- 📊 **Comprehensive Evaluation** — Quantitative & qualitative metrics
- 🔑 **Role-Based Access** — Roles: `admin`, `operator`, `user`

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **LLM** | Gemini 2.5 Flash (GA) / 2.0 Flash / 1.5 Flash (Google Cloud Vertex AI) |
| **Embeddings** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **Vector Store** | FAISS + BM25 hybrid retrieval (cosine similarity, threshold 0.30) |
| **Backend** | FastAPI + Uvicorn + SQLite |
| **Auth** | Session token (SHA-256 + salt) + Google OAuth (Authlib) |
| **Frontend** | React 18 + Vite 5 + React Router v7 |
| **Maps** | Leaflet + React-Leaflet + OpenStreetMap (free, no API key) |
| **Geolocation** | Browser `navigator.geolocation` (free, no API key) |
| **Evaluation** | BERTScore, ROUGE, NLTK, scikit-learn |

---

## 📂 Project Structure

```
├── database/
│   ├── avatars/               # User avatar uploads
│   ├── documents/             # PDF documents as RAG knowledge source
│   ├── FAQ/
│   │   └── faq_tourism.json   # FAQ dataset for cache pre-population
│   ├── kv_cache/
│   │   └── cache_index.json   # Confirmed + staging cache storage
│   └── Locations/
│       └── locations.json     # Tourism location data for map
├── frontend/
│   ├── public/                # Static assets (images, audio)
│   ├── src/
│   │   ├── App.jsx            # Main chat page, feedback, regeneration, map modal
│   │   ├── MapView.jsx        # Leaflet map component + geolocation
│   │   ├── components/
│   │   │   ├── AdminDashboard.jsx   # Admin panel
│   │   │   ├── Login.jsx            # Login/register page
│   │   │   ├── UserProfile.jsx      # User profile page
│   │   │   ├── AuthCallback.jsx     # Google OAuth callback
│   │   │   ├── ProtectedRoute.jsx   # Protected route guard
│   │   │   └── GuestRoute.jsx       # Guest-only route guard
│   │   ├── routes.jsx         # Public/auth/protected/admin route config
│   │   └── context/
│   │       └── AuthContext.jsx      # Global authentication state
│   ├── package.json
│   └── vite.config.js
├── logs/                      # Cache lifecycle logs
├── notebooks/
│   └── Evaluate.ipynb         # Full evaluation notebook
├── src/
│   ├── api.py                 # FastAPI — all API endpoints
│   ├── hybrid_system.py       # Orchestrator: Cache → FAQ → FAISS → LLM
│   ├── model.py               # Gemini REST API wrapper
│   ├── kv_cache_manager.py    # Staging + confirmed cache manager
│   ├── manage_cache.py        # Cache lifecycle (weekly cleanup/promotion)
│   ├── clear_invalid_cache.py # Utility to clean invalid cache entries
│   ├── decision_agent.py      # User preference extraction from query
│   ├── database.py            # SQLite: users, sessions, chat history
│   ├── evaluation.py          # Evaluation metrics (BERTScore, ROUGE, etc.)
│   └── faq_generator.py       # FAQ generator and manager
├── requirements.txt
├── service-account.json       # Google Cloud Vertex AI credentials
├── setup_app.sh               # App deployment setup script
└── setup_vps.sh               # VPS environment setup script
```

---

## 🚀 Installation & Run Guide

### Prerequisites

Ensure the following tools are installed:

| Software | Minimum Version | Download |
|---|---|---|
| **Python** | 3.10+ | https://www.python.org/downloads/ |
| **Node.js** | 18+ (includes npm) | https://nodejs.org/ |
| **Git** | (optional) | https://git-scm.com/ |

> Verify installation: `python --version` and `node --version`

---

### Step 1 — Clone / Extract Project

```bash
# If using Git
git clone <repo-url>
cd Implementasi

# Or extract ZIP and enter project folder
cd Implementasi
```

---

### Step 2 — Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux / macOS)
source .venv/bin/activate
```

> After activation, the terminal prompt will change to `(.venv) ...`

---

### Step 3 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

> This installs all backend libraries: FastAPI, LangChain, FAISS, sentence-transformers, Gemini client, etc. May take a few minutes.

---

### Step 4 — Create `.env` File & Service Account

1. Create a Service Account on Google Cloud Console with the **Vertex AI User** role.
2. Download the JSON credentials file, rename it to `service-account.json`, and place it in the project root.
3. Create a `.env` file in the **project root**:

```env
# ── REQUIRED: Google Cloud Vertex AI ───────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GOOGLE_CLOUD_PROJECT=chatbot-toba
VERTEX_LOCATION=us-central1

# Random long secret for session encryption (do not publish)
SECRET_KEY=replace-with-a-long-random-secure-string

# ── OPTIONAL: Google OAuth (login with Google account) ─────────────────────
# If not set, "Login with Google" will be disabled,
# but email + password login will still work.
# GOOGLE_CLIENT_ID=your_google_client_id
# GOOGLE_CLIENT_SECRET=your_google_client_secret
# GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
# FRONTEND_URL=http://localhost:3000
```

> ⚠️ Never commit `.env` or `service-account.json` to Git. Both are already in `.gitignore`.

---

### Step 5 — Install Frontend Dependencies

```bash
cd frontend
npm install
```

> This installs React, Vite, Leaflet, etc. into `frontend/node_modules/`.

---

### Step 6 — Run the System

You need **two terminals** running in parallel.

**Terminal 1 — Backend (FastAPI):**

```bash
# From project root with active .venv
python src/api.py
```

Wait until output appears:

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

Wait until output appears:

```
  VITE v5.x.x  ready in ...ms
  ➜  Local:   http://localhost:3000/
```

---

### Step 7 — Open in Browser

| Access | URL |
|---|---|
| 🌐 App | http://localhost:3000 |
| 🔌 API | http://localhost:8000 |
| 📚 Swagger Docs | http://localhost:8000/docs |

> **Default admin account** (created automatically on first run):
> - Username: `admin`
> - Password: `admin123`
> - ⚠️ Change the password immediately after first login.

---

## 🗺️ Map & Geolocation Features

Click the **Location Map** button in the sidebar to open the map modal:

- **Red markers** — tourism points from `database/Locations/locations.json`
- **"📍 My Location" button** — detects your position via browser GPS (free, no API key)
- **Blue marker** — your current location
- **Distance in popup** — each marker shows distance from your position (km)
- **Nearest-first sorting** — marker list automatically sorted by closest distance

> The browser will request location permission. Click "Allow".

---

## 📡 API Endpoints

### Chat & System

| Endpoint | Method | Function |
|---|---|---|
| `/api/chat` | POST | Send question to chatbot |
| `/api/chat/regenerate` | POST | Regenerate answer for the same question |
| `/api/chat/choose-variant` | POST | Choose original or regenerated answer |
| `/api/status` | GET | System and model status |
| `/api/stats` | GET | Cache statistics |
| `/api/locations` | GET | Tourism location data |
| `/api/feedback` | POST | Submit like/dislike feedback |
| `/api/feedback/stats` | GET | Feedback statistics |

### Authentication

| Endpoint | Method | Function |
|---|---|---|
| `/api/auth/register` | POST | Register new account |
| `/api/auth/login` | POST | Login with email + password |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Get active user profile |
| `/api/auth/validate` | GET | Validate session token |
| `/api/auth/google/login` | GET | Redirect to Google OAuth |
| `/api/auth/google/callback` | GET | Google OAuth callback |

### User Profile

| Endpoint | Method | Function |
|---|---|---|
| `/api/user/profile` | PUT | Update user profile |
| `/api/user/change-password` | POST | Change password |
| `/api/user/history` | GET | Get chat history |
| `/api/user/history` | DELETE | Delete chat history |
| `/api/user/avatar/upload` | POST | Upload avatar image |
| `/api/user/avatar/base64` | POST | Update avatar via emoji/base64 |
| `/api/conversations` | GET | List conversation threads |
| `/api/conversations/{conversation_id}/history` | GET | Get conversation history |

### Admin (Role `admin`)

| Endpoint | Method | Function |
|---|---|---|
| `/api/admin/users` | GET | List all users |
| `/api/admin/stats` | GET | System statistics |
| `/api/admin/analytics` | GET | Admin analytics |
| `/api/admin/user/{id}` | DELETE | Deactivate user |
| `/api/admin/cache/lifecycle` | GET | Preview cache lifecycle |
| `/api/admin/cache/lifecycle/execute` | POST | Execute cache lifecycle |
| `/api/admin/cache/prepopulate` | POST | Pre-populate cache from FAQ |
| `/api/admin/cache/kv/wipe` | DELETE | Wipe all KV cache entries |

### Cache

| Endpoint | Method | Function |
|---|---|---|
| `/api/clear` | POST | Clear cache |
| `/api/optimize` | POST | Optimize cache |

---

## 👤 Authentication System

### Email + Password
- Passwords are hashed using SHA-256 + salt before storage
- Login generates a **session token** stored in SQLite
- Token is sent as `Authorization: Bearer <token>` on every request

### Google OAuth
- Google login saves the `email` and `name` from the Google account
- If the email is already registered, the account is automatically linked

### Roles

| Role | Access |
|---|---|
| `user` | Chat, profile, history |
| `operator` | + cache management |
| `admin` | + all admin endpoints |

---

## ⚡ Cache System (CAG)

The response pipeline runs in the following order:

```
User Query
    │
    ▼
[1] KV Cache (confirmed) ──── HIT ──▶ Return cached response directly
    │ MISS
    ▼
[2] FAQ Search ─────────────── MATCH ▶ Return answer + save to staging cache
    │ NO MATCH
    ▼
[3] FAISS + BM25 Retrieval (RAG) ─ score ≥ 0.30 ──▶ Send context to Gemini
    │ score < 0.30
    ▼
[4] Gemini (without context) ──▶ General answer
    │
    ▼
Response → Staging Cache → (after positive signal) → Confirmed Cache
```

### Cache Lifecycle

Runs weekly via `manage_cache.py`:

- **Delete**: access < 5 times AND age > 21 days
- **Promote to FAQ**: access ≥ 5 times AND net-likes ≥ 1
- **Delete low quality**: access ≥ 5 times AND net-likes < 0

### Conversation Flow

- Each chat is stored as a conversation thread, allowing the sidebar to display history per topic.
- Follow-up queries containing words like "it" or "that" are grounded to the last discussed location.
- If a cached answer is unsatisfactory, the user can dislike it and choose a regenerated response instead.

---

## 📊 Evaluation

```bash
# Run full evaluation notebook
jupyter notebook notebooks/Evaluate.ipynb
```

**Evaluated metrics:**

1. **Efficiency**: Response Time, Cache Hit Rate (CHR)
2. **Retrieval**: RAG Recall, Effective Information Rate (EIR)
3. **Generation**: BERTScore (P/R/F1), Completeness, Hallucination Rate, Irrelevancy Score
4. **Qualitative**: Relevance, Accuracy, Completeness, Clarity, Usefulness

---

## 🧹 Utilities

```bash
# Clean invalid/corrupted cache entries
python src/clear_invalid_cache.py

# Preview cache lifecycle (dry-run, no changes applied)
python src/manage_cache.py

# Execute cache lifecycle (deletion & promotion)
python src/manage_cache.py --execute
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Ensure the virtual environment is active and run `pip install -r requirements.txt` |
| `DefaultCredentialsError` or Error 401 | Ensure `service-account.json` exists in the project root and `.env` contains `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json` |
| Backend not starting | Check if port 8000 is already in use: `netstat -ano \| findstr :8000` |
| Frontend cannot connect to backend | Ensure the backend is running on port 8000 before starting the frontend |
| Geolocation not working | Allow location permission in browser; HTTP on non-localhost is usually restricted |
| `npm: command not found` | Install Node.js from https://nodejs.org/ |

---

## 👨‍💻 Author

**TASI-104** — Institut Teknologi Del

---

MIT License © 2025

---

### VPS Deployment

```bash
# Update on VPS
bash ~/llm-chatbot-RAG-CAG/deploy.sh

# Clear KV cache (Windows)
Remove-Item -Recurse -Force "D:\Semester 8\TA II\Implementasi\database\kv_cache\*" -ErrorAction SilentlyContinue
```
