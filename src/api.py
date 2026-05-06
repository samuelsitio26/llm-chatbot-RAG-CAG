"""
FastAPI Backend for Tourism Recommendation System
Uses Gemini API for LLM with SQLite User Management
"""

import os
import sys
import time
import glob
import uuid
import base64
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google OAuth imports 
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import GeminiChatModel
from hybrid_system import CAGSystem
import database as db
import manage_cache as cache_lifecycle
import location_service as loc_svc

# Global variables
model = None
cag_system = None
decision_agent = None


class ChatRequest(BaseModel):
    query: str
    use_cache: bool = True
    k: int = 8          # raised from 5 → 8: retrieve more chunks across 4 PDFs
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None  # frontend conv_* key
    max_new_tokens: int = 2048
    temperature: float = 0.7
    favorite_categories: Optional[List[str]] = None  # User's preferred wisata categories (personalizes prompt)


class ChatResponse(BaseModel):
    response: str
    cached: bool
    response_time: float
    sources: list = []
    scores: dict = {}
    cache_key: Optional[str] = None  # MD5 hash of query, used by frontend for feedback
    chat_db_id: Optional[int] = None  # Real PK from chat_history table, used for feedback FK
    variants: Optional[list] = None  # answer variants for comparison (if any)


# ============================================
# Authentication Models
# ============================================

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    favorite_categories: Optional[List[str]] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ============================================
# Authentication Helper
# ============================================

async def get_current_user(authorization: str = Header(None)):
    """Get current user from authorization token"""
    if not authorization:
        return None
    
    # Extract token from "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    user = db.validate_session(token)
    return user

async def require_auth(authorization: str = Header(...)):
    """Require authentication"""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

async def require_admin(authorization: str = Header(...)):
    """Require admin role"""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup"""
    global model, cag_system, decision_agent
    
    print("=" * 60)
    print("🚀 Starting Tourism Recommendation API")
    print("=" * 60)
    
    try:
        # Initialize database
        print("📊 Initializing SQLite database...")
        db.init_database()
        
        # Initialize Gemini model
        print("📦 Loading Gemini API model...")
        model = GeminiChatModel(model_name="gemini-2.5-flash")
        
        # Initialize encoder for embeddings
        # Model: paraphrase-multilingual-MiniLM-L12-v2
        #   - Mendukung 50+ bahasa termasuk Bahasa Indonesia & nama-nama lokal Batak
        #   - Dimensi 384 (sama dengan model sebelumnya) → tidak perlu ubah struktur FAISS
        #   - FAISS index di-rebuild otomatis setiap startup → penggantian ini langsung aktif
        print("🔍 Loading embeddings encoder (multilingual)...")
        from langchain_huggingface import HuggingFaceEmbeddings
        encoder = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize CAG system (with model and encoder)
        print("🔧 Initializing CAG system...")
        cag_system = CAGSystem(model=model, encoder=encoder)
        
        # Load PDF documents
        print("📚 Loading PDF documents...")
        pdf_folder = os.path.join(os.path.dirname(__file__), "..", "database", "documents")
        pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
        if pdf_files:
            cag_system.load_documents(pdf_files)
            print(f"   ✅ Loaded {len(pdf_files)} PDF files")
        else:
            print("   ⚠️ No PDF files found in database/documents/")
        
        print("=" * 60)
        print("✅ All systems initialized successfully!")
        print("🌐 Server binding to: 0.0.0.0:8000")
        print("📍 Open in browser:")
        print("   • http://127.0.0.1:8000/")
        print("📚 API Docs: http://127.0.0.1:8000/docs")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error during startup: {e}")
        raise e
    
    yield
    
    # Cleanup on shutdown
    print("🛑 Shutting down...")
    if cag_system:
        cag_system.kv_cache.save_cache()
        print("💾 Cache saved on shutdown")


# Create FastAPI app
app = FastAPI(
    title="Tourism Recommendation API",
    description="RAG + CAG System for Danau Toba Tourism",
    version="2.0.0",
    lifespan=lifespan
)

# Session middleware for OAuth (required by authlib)
# Configure with same_site="lax" to allow OAuth redirects
SECRET_KEY = os.getenv("SECRET_KEY", "toba-tourism-secret-key-change-in-production")
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=False,  # Set True in production with HTTPS
    max_age=3600  # 1 hour session
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Google OAuth Setup
# ============================================
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://onierec.ai/api/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://onierec.ai")

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Tourism Recommendation API",
        "version": "2.0.0",
        "model": "Gemini 2.5 Flash",
        "status": "running"
    }


@app.get("/api/status")
async def get_status():
    """Get system status"""
    return {
        "status": "online",
        "model": "Gemini 2.5 Flash",
        "cache_enabled": True,
        "timestamp": datetime.now().isoformat()
    }


def classify_query_type(query: str) -> dict:
    """Classify query into tourism or non-tourism (hotel/restaurant/transport)"""
    import re
    
    query_lower = query.lower()
    
    # Non-tourism keywords (hotel, restaurant, transport)
    non_tourism_keywords = {
        'hotel': ['hotel', 'penginapan', 'homestay', 'resort', 'cottage', 'villa', 'motel'],
        'restaurant': ['restoran', 'rumah makan', 'warung', 'cafe', 'kuliner', 'makan', 'makanan'],
        'transport': ['transportasi', 'bus', 'travel', 'angkutan', 'rental', 'sewa mobil', 'ferry', 'kapal']
    }
    
    # Tourism keywords
    tourism_keywords = ['wisata', 'tempat', 'destinasi', 'rekomendasi', 'pantai', 'air terjun', 
                       'bukit', 'danau', 'pulau', 'objek wisata', 'lokasi']
    
    # Check for non-tourism
    for category, keywords in non_tourism_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return {'type': 'non_tourism', 'category': category}
    
    # Default to tourism if mentions tourism keywords or asking for recommendations
    if any(kw in query_lower for kw in tourism_keywords):
        return {'type': 'tourism', 'category': 'tourist_attraction'}
    
    # Default fallback
    return {'type': 'general', 'category': 'general'}


def _merge_conversation_state(prev_state: Dict[str, Any], query: str, answer: str, query_type: str) -> Dict[str, Any]:
    """Build compact state used for multi-turn context retention and coreference."""
    state = dict(prev_state or {})
    query_lower = (query or "").lower()

    explicit_place = None
    inferred_from_answer = None
    keep_previous_place = False
    try:
        if cag_system and hasattr(cag_system, "_extract_place_name"):
            explicit_place = cag_system._extract_place_name(query)

        # Follow-up turns should keep previous anchor unless user clearly switches place.
        if not explicit_place and state.get("last_place") and cag_system:
            is_ref = hasattr(cag_system, "_is_followup_reference_query") and cag_system._is_followup_reference_query(query)
            is_implicit = hasattr(cag_system, "_is_implicit_attribute_followup_query") and cag_system._is_implicit_attribute_followup_query(query)
            has_compare = any(kw in query_lower for kw in ["selain", "alternatif", "yang lain", "lainnya", "bandingkan", "dibanding"])
            keep_previous_place = bool(is_ref or is_implicit or has_compare)

        if not explicit_place and not keep_previous_place and cag_system and hasattr(cag_system, "_extract_place_from_assistant_answer"):
            inferred_from_answer = cag_system._extract_place_from_assistant_answer(answer)
    except Exception:
        explicit_place = None
        inferred_from_answer = None

    extracted_place = explicit_place or (None if keep_previous_place else inferred_from_answer)
    if extracted_place:
        state["last_place"] = extracted_place
        state["last_entity"] = extracted_place
        state["active_entity"] = extracted_place
        state["last_topic"] = extracted_place

    state["last_intent"] = query_type
    state["last_query"] = query[:300] if query else ""
    state["last_answer_preview"] = (answer or "")[:300]

    excluded = state.get("excluded_entities") or []
    if not isinstance(excluded, list):
        excluded = []

    if any(kw in query_lower for kw in ["selain", "alternatif", "yang lain", "lainnya"]):
        candidate = state.get("last_place")
        if candidate and candidate not in excluded:
            excluded.append(candidate)
    state["excluded_entities"] = excluded[-8:]
    return state


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, authorization: str = Header(None)):
    """Process chat request with smart location detection"""
    global cag_system, decision_agent
    
    if not cag_system:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    start_time = time.time()
    
    # Resolve user (optional auth)
    user = await get_current_user(authorization)
    user_id = user['id'] if user else None
    conv_id = request.conversation_id

    # Persist / update the conversation record so it exists in DB
    if conv_id:
        title = request.query[:50] if len(request.query) <= 50 else request.query[:47] + '...'
        db.upsert_conversation(conv_id, user_id, title)
        if user_id:
            owned = db.mark_conversation_accessed(conv_id, user_id)
            if not owned:
                raise HTTPException(status_code=403, detail="Conversation access denied")

    # Load conversation context so the LLM can answer follow-up questions
    # NOTE: We load history for BOTH logged-in users AND guests (user_id may be None).
    # Without this, guest/unauthenticated users get amnesia on every follow-up turn.
    chat_history = []
    conversation_state = {}
    if conv_id:
        chat_history = db.get_conversation_context(conv_id, limit=16, user_id=user_id)
        if user_id:
            conversation_state = db.get_conversation_state(conv_id, user_id)

    result = None  # initialize so finally block can safely reference it
    try:
        # Classify query type
        query_classification = classify_query_type(request.query)
        query_type = query_classification['type']
        
        print(f"📊 Query Type: {query_type} | Category: {query_classification['category']}")
        
        # Process query through CAG system
        # Pass user's favorite_categories so the LLM can bias recommendations
        user_prefs = request.favorite_categories or (user.get('favoriteCategories') if user else None) or []
        result = cag_system.get_response(
            query=request.query,
            chat_history=chat_history,
            conversation_state=conversation_state,
            use_cache=request.use_cache,
            k=request.k,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            user_preferences=user_prefs,
        )
        
        response_time = time.time() - start_time
        response_text = result.get("response", "")
        context = result.get("context", "")
        
        # Smart location extraction - only for location-specific queries
        relevant_locations = []
        show_map = loc_svc.is_location_query(request.query)
        
        if not show_map:
            print(f"💬 Non-location query - skipping map display")
        else:
            requested_count = loc_svc.extract_requested_count(request.query)
            relevant_locations = loc_svc.resolve_locations(
                query=request.query,
                response_text=response_text,
                context=context,
                query_type=query_type,
                requested_count=requested_count,
            )
        
        # Get decision scores
        scores = {}
        if decision_agent:
            try:
                preferences = decision_agent.extract_user_preferences(request.query)
                scores = {"preferences": preferences}
            except Exception as e:
                print(f"⚠️ Warning: Could not get scores: {e}")
        
        print(f"✅ Returning {len(relevant_locations)} locations to frontend")

        # Persist Q&A to DB BEFORE return so we can include the real PK in the response.
        # This allows the frontend to send the correct chat_db_id with feedback,
        # creating a valid FK link: feedback.chat_id → chat_history.id.
        chat_db_id = None
        if result is not None:
            source = result.get("source", "")
            saved_response = result.get("response", "")
            skip_sources = {"error", "no_relevant_context"}
            if saved_response and source not in skip_sources:
                elapsed_ms = int((time.time() - start_time) * 1000)
                try:
                    chat_db_id = db.save_chat(
                        user_id=user_id,
                        session_id=request.session_id or "",
                        conversation_id=conv_id,
                        question=request.query,
                        answer=saved_response,
                        category=source,
                        response_time_ms=elapsed_ms,
                        model_used="gemini-2.5-flash",
                    )
                except Exception as db_err:
                    print(f"⚠️ DB save failed (non-fatal): {db_err}")

        if user_id and conv_id and response_text:
            try:
                next_state = _merge_conversation_state(
                    prev_state=conversation_state,
                    query=request.query,
                    answer=response_text,
                    query_type=query_type,
                )
                db.upsert_conversation_state(conv_id, user_id, next_state)
            except Exception as state_err:
                print(f"⚠️ Conversation state save failed (non-fatal): {state_err}")

        return ChatResponse(
            response=response_text,
            cached=result.get("cache_used", False),
            response_time=response_time,
            sources=relevant_locations,
            scores=scores,
            cache_key=result.get("cache_key"),
            chat_db_id=chat_db_id,
            variants=None,  # variants only appear during regeneration flow
        )

    except Exception as e:
        print(f"❌ Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get cache statistics"""
    global cag_system
    
    if not cag_system:
        return {"error": "CAG system not initialized"}
    
    return cag_system.get_stats()


# ============================================
# FAQ CRUD Endpoints
# ============================================

import json as _json

FAQ_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "FAQ", "faq_tourism.json")


def _read_faqs() -> list:
    """Read FAQ file and return only {question, answer} entries."""
    try:
        with open(FAQ_PATH, 'r', encoding='utf-8-sig') as f:
            data = _json.load(f)
        return [{"question": r.get("question", ""), "answer": r.get("answer", "")} for r in data]
    except FileNotFoundError:
        return []


def _write_faqs(faqs: list) -> None:
    """Persist FAQ list (only question + answer) to file."""
    os.makedirs(os.path.dirname(FAQ_PATH), exist_ok=True)
    with open(FAQ_PATH, 'w', encoding='utf-8') as f:
        _json.dump(faqs, f, ensure_ascii=False, indent=2)


class FAQRequest(BaseModel):
    question: str
    answer: str


@app.get("/api/faqs")
async def list_faqs():
    """List all FAQ entries (question + answer only)."""
    faqs = _read_faqs()
    return {"faqs": faqs, "count": len(faqs)}


@app.post("/api/faqs")
async def add_faq(body: FAQRequest, admin: dict = Depends(require_admin)):
    """[ADMIN] Add a new FAQ entry."""
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(status_code=400, detail="Pertanyaan dan jawaban tidak boleh kosong")
    faqs = _read_faqs()
    faqs.append({"question": body.question.strip(), "answer": body.answer.strip()})
    _write_faqs(faqs)
    return {"success": True, "message": "FAQ berhasil ditambahkan", "index": len(faqs) - 1}


@app.put("/api/faqs/{faq_index}")
async def update_faq(faq_index: int, body: FAQRequest, admin: dict = Depends(require_admin)):
    """[ADMIN] Update an existing FAQ entry by index."""
    faqs = _read_faqs()
    if faq_index < 0 or faq_index >= len(faqs):
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan")
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(status_code=400, detail="Pertanyaan dan jawaban tidak boleh kosong")
    faqs[faq_index] = {"question": body.question.strip(), "answer": body.answer.strip()}
    _write_faqs(faqs)
    return {"success": True, "message": "FAQ berhasil diperbarui"}


@app.delete("/api/faqs/{faq_index}")
async def delete_faq(faq_index: int, admin: dict = Depends(require_admin)):
    """[ADMIN] Delete a FAQ entry by index."""
    faqs = _read_faqs()
    if faq_index < 0 or faq_index >= len(faqs):
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan")
    removed = faqs.pop(faq_index)
    _write_faqs(faqs)
    return {"success": True, "message": "FAQ berhasil dihapus", "removed_question": removed["question"]}


# ============================================
# KV Cache Hard-Wipe Endpoint
# ============================================

class CacheWipeRequest(BaseModel):
    confirm_text: str  # must equal "HAPUS CACHE" exactly


@app.delete("/api/admin/cache/kv/wipe")
async def wipe_kv_cache(body: CacheWipeRequest, admin: dict = Depends(require_admin)):
    """[ADMIN] Permanently wipe the entire KV cache (confirmed + staging).
    Requires body.confirm_text == 'HAPUS CACHE' as a safety guard.
    """
    if body.confirm_text != "HAPUS CACHE":
        raise HTTPException(
            status_code=400,
            detail="Konfirmasi salah. Ketikkan tepat: HAPUS CACHE"
        )

    global cag_system
    if not cag_system:
        raise HTTPException(status_code=503, detail="CAG system not initialized")

    stats_before = cag_system.kv_cache.get_stats()
    confirmed_before = stats_before.get("size", 0)
    staging_before   = stats_before.get("staging_items", 0)

    cag_system.kv_cache.clear()

    print(f"🗑️ [ADMIN:{admin['username']}] KV cache wiped — confirmed={confirmed_before}, staging={staging_before}")

    return {
        "success": True,
        "message": f"KV Cache berhasil dihapus. {confirmed_before} confirmed + {staging_before} staging entries dihapus.",
        "removed_confirmed": confirmed_before,
        "removed_staging":   staging_before,
    }



@app.get("/api/locations")
async def get_locations():
    """Get tourism locations with coordinates from extracted data"""
    import json
    
    locations_file = os.path.join(
        os.path.dirname(__file__), "..", "database", "Locations", "locations.json"
    )
    
    try:
        if os.path.exists(locations_file):
            with open(locations_file, 'r', encoding='utf-8') as f:
                locations_data = json.load(f)

            # Pass all fields from locations.json directly to the frontend
            enhanced_locations = []
            for loc in locations_data:
                if loc.get("lat") is None or loc.get("lng") is None:
                    continue
                enhanced_locations.append({
                    "name":        loc.get("name", ""),
                    "lat":         loc.get("lat"),
                    "lng":         loc.get("lng"),
                    "description": loc.get("description", ""),
                    "category":    loc.get("category", "wisata"),
                    "location":    loc.get("location", ""),
                    "address":     loc.get("address", ""),
                    "price":       loc.get("price", ""),
                    "hours":       loc.get("hours", ""),
                    "rating":      loc.get("rating"),
                    "source":      loc.get("source", ""),
                })

            return {
                "success": True,
                "locations": enhanced_locations,
                "count": len(enhanced_locations)
            }
        else:
            # Return default Toba locations if file doesn't exist
            default_locations = [
                {
                    "name": "Parapat",
                    "lat": 2.6631,
                    "lng": 98.9332,
                    "description": "Pintu gerbang utama Danau Toba",
                    "source": "default",
                    "category": "city"
                },
                {
                    "name": "Pulau Samosir",
                    "lat": 2.6500,
                    "lng": 98.8500,
                    "description": "Pulau di tengah Danau Toba",
                    "source": "default",
                    "category": "island"
                },
                {
                    "name": "Tuktuk",
                    "lat": 2.6642,
                    "lng": 98.8575,
                    "description": "Desa wisata di Samosir",
                    "source": "default",
                    "category": "village"
                },
                {
                    "name": "Tomok",
                    "lat": 2.6297,
                    "lng": 98.8864,
                    "description": "Makam Raja Sidabutar",
                    "source": "default",
                    "category": "culture"
                },
                {
                    "name": "Ambarita",
                    "lat": 2.6858,
                    "lng": 98.8283,
                    "description": "Batu Parsidangan bersejarah",
                    "source": "default",
                    "category": "culture"
                },
                {
                    "name": "Simanindo",
                    "lat": 2.7236,
                    "lng": 98.7947,
                    "description": "Museum Batak & Sigale-gale",
                    "source": "default",
                    "category": "museum"
                },
                {
                    "name": "Air Terjun Sipiso-piso",
                    "lat": 2.9089,
                    "lng": 98.5244,
                    "description": "Air terjun tertinggi di Indonesia",
                    "source": "default",
                    "category": "waterfall"
                },
                {
                    "name": "Balige",
                    "lat": 2.3339,
                    "lng": 99.0614,
                    "description": "Kota di tepi Danau Toba",
                    "source": "default",
                    "category": "city"
                },
                {
                    "name": "Tongging",
                    "lat": 2.9167,
                    "lng": 98.5333,
                    "description": "Desa wisata dengan pemandangan Danau Toba",
                    "source": "default",
                    "category": "village"
                },
                {
                    "name": "Pangururan",
                    "lat": 2.6333,
                    "lng": 98.7500,
                    "description": "Ibukota Samosir",
                    "source": "default",
                    "category": "city"
                }
            ]
            
            return {
                "success": True,
                "locations": default_locations,
                "count": len(default_locations),
                "info": "Using default locations. Run extraction script for document-based locations."
            }
    
    except Exception as e:
        print(f"❌ Error loading locations: {e}")
        # Fallback to minimal default
        return {
            "success": True,
            "locations": [
                {
                    "name": "Danau Toba",
                    "lat": 2.6500,
                    "lng": 98.8500,
                    "description": "Danau vulkanik terbesar di Asia Tenggara",
                    "source": "default",
                    "category": "lake"
                }
            ],
            "count": 1,
            "error": str(e)
        }


@app.post("/api/clear")
async def clear_cache():
    """Clear all cache"""
    global cag_system
    
    if not cag_system:
        return {"error": "CAG system not initialized"}
    
    cag_system.clear_cache()
    return {"message": "Cache cleared successfully"}


@app.post("/api/optimize")
async def optimize_cache():
    """Optimize cache by removing old entries"""
    global cag_system
    
    if not cag_system:
        return {"error": "CAG system not initialized"}
    
    cag_system.optimize_cache()
    return {"message": "Cache optimized."}


# ============================================
# Cache Lifecycle Management Endpoints
# ============================================

@app.get("/api/admin/cache/lifecycle")
async def cache_lifecycle_report(
    max_age_days: int = None,
    max_entries: int = None,
    min_access: int = None,
    current_user: dict = Depends(require_admin)
):
    """
    [ADMIN] Laporan lifecycle cache (dry-run).
    Query params (semua opsional, gunakan default jika tidak diisi):
      - max_age_days : hari tanpa akses → kandidat hapus      (default: 21)
      - max_entries  : batas maksimum entri cache; 0=unlimited (default: 500)
      - min_access   : threshold akses minimum                 (default: 5)
    """
    try:
        report = cache_lifecycle.get_lifecycle_report(
            max_age_days=max_age_days,
            max_entries=max_entries,
            min_access=min_access,
        )
        return {
            "success": True,
            "report":  report,
            "note":    "Ini dry-run. Gunakan POST /api/admin/cache/lifecycle/execute untuk menerapkan."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LifecycleExecuteRequest(BaseModel):
    max_age_days: Optional[int] = None
    max_entries:  Optional[int] = None
    min_access:   Optional[int] = None


@app.post("/api/admin/cache/lifecycle/execute")
async def cache_lifecycle_execute(
    body: LifecycleExecuteRequest = LifecycleExecuteRequest(),
    current_user: dict = Depends(require_admin)
):
    """
    [ADMIN] Jalankan lifecycle cache dengan parameter yang bisa dikonfigurasi.
    Body JSON (semua opsional):
      - max_age_days : hari tanpa akses → hapus               (default: 21)
      - max_entries  : batas maksimum entri; 0=unlimited       (default: 500)
      - min_access   : threshold akses minimum                 (default: 5)
    """
    try:
        report = cache_lifecycle.execute_lifecycle(
            max_age_days=body.max_age_days,
            max_entries=body.max_entries,
            min_access=body.min_access,
        )
        summary = report.get("summary", {})
        return {
            "success": True,
            "summary": summary,
            "message": (
                f"Dihapus: {summary.get('to_delete', 0)} entries | "
                f"Dipromosi ke FAQ: {summary.get('to_promote', 0)} entries"
            )
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/cache/prepopulate")
async def cache_prepopulate_from_faq(current_user: dict = Depends(require_admin)):
    """
    [ADMIN] Pre-populate KV cache langsung dari FAQ yang sudah punya field 'answer'.
    Tidak memanggil LLM – jawaban FAQ langsung disimpan ke cache.
    """
    global cag_system
    if not cag_system:
        raise HTTPException(status_code=503, detail="CAG system not initialized")
    try:
        result = cag_system.faq_gen.pre_populate_cache_from_answers(
            cag_system.kv_cache
        )
        return {
            "success": True,
            "added":   result["added"],
            "skipped": result["skipped"],
            "message": f"{result['added']} entries dari FAQ ditambahkan ke cache"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Authentication Endpoints
# ============================================

@app.post("/api/auth/register")
async def register(request: RegisterRequest, req: Request):
    """Register a new user"""
    result = db.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        name=request.name
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Auto-login after registration
    login_result = db.authenticate_user(
        username=request.username,
        password=request.password,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent")
    )
    
    return login_result


@app.post("/api/auth/login")
async def login(request: LoginRequest, req: Request):
    """Login user"""
    result = db.authenticate_user(
        username=request.username,
        password=request.password,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent")
    )
    
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    
    return result


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(...)):
    """Logout user"""
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    db.logout_user(token)
    return {"success": True, "message": "Logged out successfully"}


# ============================================
# Google OAuth Endpoints
# ============================================

@app.get("/api/auth/google/login")
async def google_login(request: Request):
    """Redirect user to Google login page"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    redirect_uri = GOOGLE_REDIRECT_URI
    print(f"🔑 Starting Google OAuth, redirect_uri: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        print(f"📥 Google callback received")
        
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)
        print(f"✅ Token received from Google")
        
        # Get user info from token
        userinfo = token.get('userinfo')
        if not userinfo:
            # Try to get from id_token
            try:
                userinfo = await oauth.google.parse_id_token(token, nonce=None)
            except Exception as e:
                print(f"⚠️ Could not parse id_token: {e}")
                # Fallback: get userinfo from userinfo endpoint
                userinfo = token.get('userinfo')
        
        if not userinfo:
            print("❌ No userinfo in token")
            return RedirectResponse(f"{FRONTEND_URL}/login?error=no_userinfo")
        
        email = userinfo.get('email')
        name = userinfo.get('name')
        picture = userinfo.get('picture')
        
        print(f"👤 User info: email={email}, name={name}")
        
        if not email:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=no_email")
        
        # Get or create user in database
        result = db.get_or_create_google_user(
            email=email,
            name=name,
            avatar=picture,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        if not result.get("success"):
            error_msg = result.get('error', 'OAuth failed')
            print(f"❌ DB error: {error_msg}")
            return RedirectResponse(f"{FRONTEND_URL}/login?error={error_msg}")
        
        # Redirect to frontend with token
        auth_token = result.get("token")
        print(f"✅ Login successful, redirecting to frontend")
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={auth_token}")
        
    except Exception as e:
        print(f"❌ Google OAuth error: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")


@app.get("/api/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    """Get current user info"""
    return {"user": user}


@app.get("/api/auth/validate")
async def validate_token(authorization: str = Header(None)):
    """Validate token and return user if valid"""
    user = await get_current_user(authorization)
    if user:
        return {"valid": True, "user": user}
    return {"valid": False, "user": None}


# ============================================
# User Profile Endpoints
# ============================================

@app.put("/api/user/profile")
async def update_profile(request: UpdateProfileRequest, user: dict = Depends(require_auth)):
    """Update user profile"""
    update_data = {}
    if request.name is not None:
        update_data['name'] = request.name
    if request.avatar is not None:
        update_data['avatar'] = request.avatar
    if request.bio is not None:
        update_data['bio'] = request.bio
    if request.location is not None:
        update_data['location'] = request.location
    if request.favorite_categories is not None:
        update_data['favorite_categories'] = request.favorite_categories
    
    result = db.update_user(user['id'], **update_data)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Return updated user
    updated_user = db.get_user_by_id(user['id'])
    return {"success": True, "user": updated_user}


@app.post("/api/user/change-password")
async def change_password(request: ChangePasswordRequest, user: dict = Depends(require_auth)):
    """Change user password"""
    result = db.change_password(
        user_id=user['id'],
        old_password=request.old_password,
        new_password=request.new_password
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.get("/api/user/history")
async def get_chat_history(user: dict = Depends(require_auth), limit: int = 50):
    """Get user chat history"""
    history = db.get_user_chat_history(user['id'], limit)
    return {"history": history}


@app.get("/api/conversations")
async def get_conversations(user: dict = Depends(require_auth)):
    """Return list of conversation threads for the logged-in user."""
    convs = db.get_user_conversations(user['id'])
    return {"conversations": convs}


@app.get("/api/conversations/last")
async def get_last_conversation(user: dict = Depends(require_auth)):
    """Return the last opened conversation for the logged-in user."""
    conv = db.get_last_opened_conversation(user['id'])
    return {"conversation": conv}


@app.post("/api/conversations/{conversation_id}/activate")
async def activate_conversation(conversation_id: str, user: dict = Depends(require_auth)):
    """Mark a conversation as active/last-opened for this user."""
    ok = db.mark_conversation_accessed(conversation_id, user['id'])
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "conversation_id": conversation_id}


@app.get("/api/conversations/{conversation_id}/history")
async def get_conversation_history(conversation_id: str, user: dict = Depends(require_auth)):
    """Return full Q&A turns for a specific conversation (for reload from DB)."""
    ok = db.mark_conversation_accessed(conversation_id, user['id'])
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    history = db.get_conversation_context(conversation_id, limit=100, user_id=user['id'])
    return {"conversation_id": conversation_id, "history": history}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(require_auth)):
    """Delete a single conversation and its chat history."""
    ok = db.delete_conversation(conversation_id, user['id'])
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to delete conversation")
    return {"success": True}


@app.delete("/api/conversations")
async def clear_all_conversations(user: dict = Depends(require_auth)):
    """Delete ALL conversations for the logged-in user."""
    deleted = db.clear_user_conversations(user['id'])
    return {"success": True, "deleted": deleted}


# ============================================
# Admin Endpoints
# ============================================

@app.get("/api/admin/users")
async def get_all_users(admin: dict = Depends(require_admin), include_inactive: bool = False):
    """Get all users (admin only)"""
    users = db.get_all_users(include_inactive)
    return {"users": users}


@app.get("/api/admin/stats")
async def get_system_stats(admin: dict = Depends(require_admin)):
    """Get system statistics (admin only)"""
    stats = db.get_system_stats()
    feedback = db.get_feedback_stats()
    return {"stats": stats, "feedback": feedback}


@app.get("/api/admin/analytics")
async def get_analytics(
    limit: int = 50,
    admin: dict = Depends(require_admin)
):
    """Get comprehensive CAG vs RAG research analytics (admin only)"""
    data = db.get_analytics_data(limit_recent=limit)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data


@app.delete("/api/admin/user/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """Delete (deactivate) user (admin only)"""
    if user_id == admin['id']:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    result = db.delete_user(user_id, admin['id'])
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Feedback Endpoints
# ============================================

class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int  # 1 for like, -1 for dislike
    comment: Optional[str] = None
    cache_key: Optional[str] = None   # MD5 hash of query from ChatResponse.cache_key
    chat_db_id: Optional[int] = None  # Real PK from ChatResponse.chat_db_id → chat_history.id


@app.post("/api/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    authorization: str = Header(None)
):
    """Submit feedback for a chat response — with toggle support.
    
    Toggle behaviour (like ChatGPT):
      - If user clicks same rating again → toggles OFF (rating = 0)
      - If user clicks different rating → switches to that rating
      - Like and dislike are mutually exclusive
    
    Dislike policy:
      - Dislikes are accumulated in KV cache (total_dislikes++)
      - NOT immediately deleted — cleaned up during Lifecycle Cache policy
      - Lifecycle evicts staging entries with net_likes ≤ -3
      - Lifecycle deletes popular confirmed entries with net_likes < 0
      - Explicit regeneration is done via the Regenerate button, not auto-triggered
    """
    user    = await get_current_user(authorization)
    user_id = user['id'] if user else None

    # Build a stable message hash for toggle lookup
    message_hash = request.cache_key or str(hash(request.message_id) % 2147483647)

    try:
        # 1. Persist to DB with toggle logic
        # Use real DB id if provided, otherwise fall back to hash (legacy)
        chat_id = request.chat_db_id if request.chat_db_id else hash(request.message_id) % 2147483647
        fb_result = db.save_feedback(
            user_id=user_id,
            chat_id=chat_id,
            rating=request.rating,
            comment=request.comment,
            message_hash=message_hash,
        )
        final_rating = fb_result.get("rating", request.rating)

        # 2. Propagate to KV cache quality tracker (accumulate likes/dislikes)
        cache_action = "none"
        if request.cache_key and cag_system and final_rating != 0:
            feedback_result = cag_system.kv_cache.record_feedback(request.cache_key, final_rating)
            cache_action = feedback_result.get("action", "none")
            print(f"👍 Cache feedback: key={request.cache_key[:8]}... action={cache_action}")
            
            # Dislike is accumulated — lifecycle policy will handle eviction
            # No automatic background regen; user can explicitly click Regenerate button
            if final_rating < 0:
                print(f"👎 Dislike recorded for {request.cache_key[:8]}... (will be evaluated during lifecycle cleanup)")

        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "rating": final_rating,
            "toggled": fb_result.get("toggled", False),
            "action": fb_result.get("action", "created"),
            "cache_action": cache_action,
        }

    except Exception as e:
        print(f"❌ Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/stats")
async def get_feedback_statistics():
    """Get feedback statistics"""
    stats = db.get_feedback_stats()
    return stats


# ============================================
# Avatar Upload Endpoints
# ============================================

# Create avatars directory if not exists
AVATARS_DIR = os.path.join(os.path.dirname(__file__), "..", "database", "avatars")
os.makedirs(AVATARS_DIR, exist_ok=True)

@app.post("/api/user/avatar/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth)
):
    """Upload avatar image"""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail="File type not allowed. Use JPEG, PNG, GIF, or WebP"
        )
    
    # Validate file size (max 2MB)
    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 2MB")
    
    try:
        # Generate unique filename
        ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"avatar_{user['id']}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(AVATARS_DIR, filename)
        
        # Save file
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Create avatar URL (relative path)
        avatar_url = f"/api/avatars/{filename}"
        
        # Update user avatar in database
        result = db.update_user(user['id'], avatar=avatar_url)
        
        if result["success"]:
            return {
                "success": True,
                "avatar_url": avatar_url,
                "message": "Avatar uploaded successfully"
            }
        else:
            # Remove uploaded file if db update fails
            os.remove(filepath)
            raise HTTPException(status_code=500, detail="Failed to update avatar")
            
    except Exception as e:
        print(f"❌ Error uploading avatar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/avatar/base64")
async def upload_avatar_base64(
    request: Request,
    user: dict = Depends(require_auth)
):
    """Upload avatar as base64 string (for emoji/small images)"""
    try:
        body = await request.json()
        avatar_data = body.get("avatar")
        
        if not avatar_data:
            raise HTTPException(status_code=400, detail="Avatar data required")
        
        # If it's an emoji (short string), save directly
        if len(avatar_data) < 20:
            result = db.update_user(user['id'], avatar=avatar_data)
            if result["success"]:
                return {"success": True, "avatar": avatar_data}
            raise HTTPException(status_code=500, detail="Failed to update avatar")
        
        # If it's base64 image, decode and save
        if avatar_data.startswith("data:image"):
            # Extract base64 data
            header, data = avatar_data.split(",", 1)
            ext = header.split("/")[1].split(";")[0]
            
            # Decode
            image_bytes = base64.b64decode(data)
            
            # Validate size
            if len(image_bytes) > 2 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Image too large. Maximum 2MB")
            
            # Save file
            filename = f"avatar_{user['id']}_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = os.path.join(AVATARS_DIR, filename)
            
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            
            avatar_url = f"/api/avatars/{filename}"
            result = db.update_user(user['id'], avatar=avatar_url)
            
            if result["success"]:
                return {"success": True, "avatar": avatar_url}
            
            os.remove(filepath)
            raise HTTPException(status_code=500, detail="Failed to update avatar")
        
        # Direct string (emoji)
        result = db.update_user(user['id'], avatar=avatar_data)
        if result["success"]:
            return {"success": True, "avatar": avatar_data}
        
        raise HTTPException(status_code=500, detail="Failed to update avatar")
        
    except Exception as e:
        print(f"❌ Error uploading avatar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import FileResponse

@app.get("/api/avatars/{filename}")
async def get_avatar(filename: str):
    """Serve avatar image"""
    filepath = os.path.join(AVATARS_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Avatar not found")


# ============================================
# Regenerate & Choose Variant Endpoints
# ============================================

class RegenerateRequest(BaseModel):
    question: str
    old_answer: str
    cache_key: Optional[str] = None
    conversation_id: Optional[str] = None


class ChooseVariantRequest(BaseModel):
    variant_id: int
    question_hash: Optional[str] = None
    chosen_answer: str


@app.post("/api/chat/regenerate")
async def regenerate_answer(request: RegenerateRequest, authorization: str = Header(None)):
    """Generate a new answer for the same question, bypassing cache."""
    global cag_system

    if not cag_system:
        raise HTTPException(status_code=503, detail="System not initialized")

    user = await get_current_user(authorization)
    user_prefs = user.get('favoriteCategories') if user else []

    # Load conversation context
    chat_history = []
    conversation_state = {}
    if request.conversation_id and user:
        chat_history = db.get_conversation_context(
            request.conversation_id,
            limit=8,
            user_id=user['id'],
        )
        conversation_state = db.get_conversation_state(request.conversation_id, user['id'])

    try:
        # Force fresh generation — skip cache
        result = cag_system.get_response(
            query=request.question,
            chat_history=chat_history,
            conversation_state=conversation_state,
            use_cache=False,   # always bypass cache for regeneration
            k=8,
            max_new_tokens=2048,
            temperature=0.9,   # slightly higher temp for variation
            user_preferences=user_prefs or [],
        )

        new_answer = result.get("response", "")
        new_cache_key = result.get("cache_key") or request.cache_key

        variants = [
            {"id": -1, "answer": request.old_answer, "source": "original", "votes": 0},
            {"id": -2, "answer": new_answer, "source": "regenerated", "votes": 0},
        ]

        print(f"🔄 Regenerated answer for: {request.question[:50]}...")

        return {
            "old_answer": request.old_answer,
            "new_answer": new_answer,
            "variants": variants,
            "cache_key": new_cache_key,
        }

    except Exception as e:
        print(f"❌ Error regenerating: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/choose-variant")
async def choose_variant(request: ChooseVariantRequest, authorization: str = Header(None)):
    """Record which variant the user chose and update the KV cache accordingly."""
    global cag_system

    try:
        # Update KV cache with the chosen answer if we have a hash
        if request.question_hash and cag_system:
            # If user chose regenerated (-2), that answer replaces the cached one
            if request.variant_id == -2:
                cag_system.kv_cache.update_entry(
                    request.question_hash, request.chosen_answer
                )
                print(f"💾 Cache updated with chosen regenerated answer: {request.question_hash[:8]}...")
            elif request.variant_id == -1:
                # User preferred original — record a like to reinforce it
                cag_system.kv_cache.record_feedback(request.question_hash, 1)
                print(f"👍 Original answer reinforced: {request.question_hash[:8]}...")

        return {"success": True, "message": "Variant choice recorded"}

    except Exception as e:
        print(f"❌ Error choosing variant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
