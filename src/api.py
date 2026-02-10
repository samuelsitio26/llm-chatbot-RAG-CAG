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
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File
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
from cag_system import CAGSystem
from decision_agent import DecisionMakingAgent
import database as db

# Global variables
model = None
cag_system = None
decision_agent = None


class ChatRequest(BaseModel):
    query: str
    use_cache: bool = True
    k: int = 5
    session_id: Optional[str] = None
    max_new_tokens: int = 2048
    temperature: float = 0.7


class ChatResponse(BaseModel):
    response: str
    cached: bool
    response_time: float
    sources: list = []
    scores: dict = {}


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
        print("🔍 Loading embeddings encoder...")
        from langchain_huggingface import HuggingFaceEmbeddings
        encoder = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L12-v2",
            model_kwargs={'device': 'cpu'}
        )
        
        # Initialize CAG system (with model and encoder)
        print("🔧 Initializing CAG system...")
        cag_system = CAGSystem(model=model, encoder=encoder)
        
        # Load PDF documents
        print("📚 Loading PDF documents...")
        pdf_folder = os.path.join(os.path.dirname(__file__), "..", "database", "vectordatabase")
        pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
        if pdf_files:
            cag_system.load_documents(pdf_files)
            print(f"   ✅ Loaded {len(pdf_files)} PDF files")
        else:
            print("   ⚠️ No PDF files found in database/vectordatabase/")
        
        # Initialize decision agent
        print("🎯 Initializing decision agent...")
        decision_agent = DecisionMakingAgent()
        
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
        "model": "Gemini 2.0 Flash",
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


def is_location_query(query: str) -> bool:
    """Check if user is specifically asking about a place/location.
    Only these queries should trigger the map display.
    Examples: 'dimana pantai X', 'lokasi air terjun Y', 'tempat wisata di Z'
    """
    query_lower = query.lower()
    
    # Keywords that indicate user is asking about a specific place/location
    location_keywords = [
        'dimana', 'di mana', 'lokasi', 'keberadaan', 'alamat',
        'tempat wisata', 'letak', 'posisi', 'koordinat',
        'cara menuju', 'cara ke', 'rute ke', 'jalan menuju', 'arah ke',
        'peta', 'map', 'titik lokasi',
        'terletak', 'berada di', 'ada di mana',
    ]
    
    # Patterns: "rekomendasi N tempat", "5 wisata terbaik", etc.
    import re
    recommendation_patterns = [
        r'\d+\s*(tempat|wisata|destinasi|lokasi|pantai|air terjun|danau|bukit|pulau)',
        r'rekomendasi\s*(tempat|wisata|destinasi|pantai|air terjun)',
        r'tempat.*(terbaik|terindah|populer|favorit|bagus)',
        r'wisata.*(terbaik|terindah|populer|favorit|bagus)',
        r'daftar.*(tempat|wisata|destinasi|pantai)',
        r'list.*(tempat|wisata|destinasi|pantai)',
    ]
    
    # Check direct location keywords
    if any(kw in query_lower for kw in location_keywords):
        return True
    
    # Check recommendation patterns (asking for list of places)
    for pattern in recommendation_patterns:
        if re.search(pattern, query_lower):
            return True
    
    return False


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


def extract_requested_count(query: str) -> int:
    """Extract how many items user wants (1, 2, 3, 5, 10, etc)"""
    import re
    
    query_lower = query.lower()
    
    # Pattern 1: "5 tempat", "3 lokasi", "10 rekomendasi"
    pattern1 = re.search(r'(\d+)\s*(tempat|lokasi|rekomendasi|hotel|restoran|wisata)', query_lower)
    if pattern1:
        return int(pattern1.group(1))
    
    # Pattern 2: "satu", "dua", "tiga", etc (Indonesian numbers)
    number_words = {
        'satu': 1, 'dua': 2, 'tiga': 3, 'empat': 4, 'lima': 5,
        'enam': 6, 'tujuh': 7, 'delapan': 8, 'sembilan': 9, 'sepuluh': 10
    }
    for word, num in number_words.items():
        if word in query_lower:
            return num
    
    # Pattern 3: "top 5", "top 10"
    pattern3 = re.search(r'top\s*(\d+)', query_lower)
    if pattern3:
        return int(pattern3.group(1))
    
    # Default based on query intent
    if 'terbaik' in query_lower or 'top' in query_lower:
        return 5  # Default top 5 untuk "terbaik"
    elif 'beberapa' in query_lower:
        return 3
    else:
        return 5  # Default 5 rekomendasi


def get_top_tourism_locations(count: int = 5, category: str = None) -> list:
    """Get top N tourism locations from locations.json sorted by rating"""
    import json
    import os
    
    locations_file = os.path.join(
        os.path.dirname(__file__), "..", "database", "Locations", "locations.json"
    )
    
    try:
        if not os.path.exists(locations_file):
            return []
        
        with open(locations_file, 'r', encoding='utf-8') as f:
            all_locations = json.load(f)
        
        # Filter by category if specified
        if category:
            filtered = [loc for loc in all_locations if loc.get('category') == category]
        else:
            filtered = all_locations
        
        # Sort by rating (descending)
        sorted_locs = sorted(filtered, key=lambda x: x.get('rating', 0), reverse=True)
        
        # Return top N
        top_n = sorted_locs[:count]
        
        return [{
            'name': loc.get('name'),
            'lat': loc.get('lat'),
            'lng': loc.get('lng'),
            'category': loc.get('category'),
            'rating': loc.get('rating'),
            'price': loc.get('price'),
            'description': loc.get('description', '')
        } for loc in top_n]
        
    except Exception as e:
        print(f"⚠️ Warning: Could not load locations: {e}")
        return []


def extract_coordinates_from_context(context: str) -> list:
    """Extract lat/lng coordinates from RAG context (PDF content)"""
    import re
    
    coordinates = []
    
    # Pattern 1: Latitude/Longitude format
    # Example: Latitude: 2.6631, Longitude: 98.9332 or Lat: 2.6631, Lng: 98.9332
    pattern1 = re.finditer(
        r'(?:Lat(?:itude)?|lat)[\s:]*(-?\d+\.?\d*)[,\s]*(?:Long?(?:itude)?|lng?)[\s:]*(-?\d+\.?\d*)',
        context,
        re.IGNORECASE
    )
    
    for match in pattern1:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            
            # Validate for Toba region (Sumatra)
            if 1.5 <= lat <= 4.0 and 97.0 <= lng <= 100.0:
                # Try to extract name from nearby text
                start = max(0, match.start() - 100)
                end = min(len(context), match.end() + 100)
                nearby_text = context[start:end]
                
                # Extract potential name (text before coordinate)
                name_match = re.search(r'([A-Z][A-Za-z\s]{2,50})[\s\n]*(?:Lat|lat)', nearby_text)
                name = name_match.group(1).strip() if name_match else f"Lokasi ({lat:.3f}, {lng:.3f})"
                
                coordinates.append({
                    'name': name,
                    'lat': lat,
                    'lng': lng,
                    'source': 'pdf_extraction',
                    'category': 'from_document'
                })
        except (ValueError, AttributeError):
            continue
    
    # Pattern 2: Simple coordinate pairs (2.6631, 98.9332)
    pattern2 = re.finditer(r'(\d+\.\d{4,})\s*[,;]\s*(\d+\.\d{4,})', context)
    
    for match in pattern2:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            
            if 1.5 <= lat <= 4.0 and 97.0 <= lng <= 100.0:
                # Avoid duplicates
                if not any(abs(c['lat'] - lat) < 0.001 and abs(c['lng'] - lng) < 0.001 for c in coordinates):
                    coordinates.append({
                        'name': f"Lokasi ({lat:.4f}, {lng:.4f})",
                        'lat': lat,
                        'lng': lng,
                        'source': 'pdf_extraction',
                        'category': 'from_document'
                    })
        except ValueError:
            continue
    
    return coordinates


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat request with smart location detection"""
    global cag_system, decision_agent
    
    if not cag_system:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    start_time = time.time()
    
    try:
        # Classify query type
        query_classification = classify_query_type(request.query)
        query_type = query_classification['type']
        
        print(f"📊 Query Type: {query_type} | Category: {query_classification['category']}")
        
        # Process query through CAG system
        result = cag_system.get_response(
            query=request.query,
            use_cache=request.use_cache,
            k=request.k,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature
        )
        
        response_time = time.time() - start_time
        response_text = result.get("response", "")
        context = result.get("context", "")
        
        # Smart location extraction - only for location-specific queries
        relevant_locations = []
        show_map = is_location_query(request.query)
        
        if not show_map:
            print(f"💬 Non-location query - skipping map display")
        elif query_type == 'tourism':
            # TOURISM: Get from locations.json based on rating
            requested_count = extract_requested_count(request.query)
            print(f"🏖️ Tourism location query - Requesting {requested_count} locations")
            
            # Get top N locations
            top_locations = get_top_tourism_locations(count=requested_count)
            
            # Also check if specific locations mentioned in response
            response_lower = response_text.lower()
            for loc in top_locations:
                if loc['name'].lower() in response_lower:
                    relevant_locations.append(loc)
            
            # If no specific mentions, use top N by rating
            if not relevant_locations:
                relevant_locations = top_locations
                
        elif query_type == 'non_tourism':
            # NON-TOURISM: Extract from RAG context (PDF)
            print(f"🏨 Non-tourism location query - Extracting from PDF context")
            
            # Extract coordinates from RAG context
            pdf_locations = extract_coordinates_from_context(context)
            
            if pdf_locations:
                # Limit based on user request
                requested_count = extract_requested_count(request.query)
                relevant_locations = pdf_locations[:requested_count]
                print(f"📍 Found {len(relevant_locations)} locations in PDF")
            else:
                print("⚠️ No coordinates found in PDF context")
        
        else:
            # GENERAL location query: Try to find any mentioned locations
            print(f"💬 General location query - Checking for location mentions")
            relevant_locations = extract_mentioned_locations(response_text)
        
        # Get decision scores
        scores = {}
        if decision_agent:
            try:
                preferences = decision_agent.extract_user_preferences(request.query)
                scores = {"preferences": preferences}
            except Exception as e:
                print(f"⚠️ Warning: Could not get scores: {e}")
        
        print(f"✅ Returning {len(relevant_locations)} locations to frontend")
        
        return ChatResponse(
            response=response_text,
            cached=result.get("cache_used", False),
            response_time=response_time,
            sources=relevant_locations,
            scores=scores
        )
        
    except Exception as e:
        print(f"❌ Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def extract_mentioned_locations(response_text: str) -> list:
    """Extract location names explicitly mentioned in response (fallback method)"""
    import json
    import os
    
    locations_file = os.path.join(
        os.path.dirname(__file__), "..", "database", "Locations", "locations.json"
    )
    
    try:
        if not os.path.exists(locations_file):
            return []
        
        with open(locations_file, 'r', encoding='utf-8') as f:
            all_locations = json.load(f)
        
        relevant = []
        response_lower = response_text.lower()
        
        for loc in all_locations:
            location_name = loc.get('name', '').lower()
            if location_name in response_lower:
                relevant.append({
                    'name': loc.get('name'),
                    'lat': loc.get('lat'),
                    'lng': loc.get('lng'),
                    'category': loc.get('category'),
                    'rating': loc.get('rating'),
                    'description': loc.get('description', '')[:100] + '...'
                })
        
        return relevant[:5]  # Max 5 untuk general queries
        
    except Exception as e:
        print(f"⚠️ Warning: Could not extract locations: {e}")
        return []


@app.get("/api/stats")
async def get_stats():
    """Get cache statistics"""
    global cag_system
    
    if not cag_system:
        return {"error": "CAG system not initialized"}
    
    return cag_system.get_stats()


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
            
            # Enhance location data with better names from source
            enhanced_locations = []
            for idx, loc in enumerate(locations_data):
                # Try to get better name from source
                source = loc.get("source", "")
                name = loc.get("name", "")
                
                # Create better location names based on source
                if "transportasi" in source.lower():
                    name = f"Transportasi - Lokasi {idx + 1}"
                elif "fasilitas" in source.lower():
                    name = f"Fasilitas Umum - Lokasi {idx + 1}"
                elif "hotel" in source.lower() or "penginapan" in source.lower():
                    name = f"Hotel/Penginapan - Lokasi {idx + 1}"
                elif "wisata" in source.lower() or "pantai" in source.lower():
                    name = f"Tempat Wisata - Lokasi {idx + 1}"
                else:
                    name = f"Lokasi {idx + 1}"
                
                enhanced_locations.append({
                    "name": name,
                    "lat": loc.get("lat"),
                    "lng": loc.get("lng"),
                    "description": f"Sumber: {source}",
                    "source": source,
                    "category": loc.get("category", "general")
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


@app.delete("/api/user/history")
async def clear_chat_history(user: dict = Depends(require_auth)):
    """Clear user chat history"""
    success = db.clear_user_chat_history(user['id'])
    return {"success": success}


@app.get("/api/user/activity")
async def get_activity(user: dict = Depends(require_auth), limit: int = 50):
    """Get user activity log"""
    activity = db.get_user_activity(user['id'], limit)
    return {"activity": activity}


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


@app.post("/api/feedback")
async def submit_feedback(
    request: FeedbackRequest, 
    authorization: str = Header(None)
):
    """Submit feedback for a chat response"""
    # Get user if authenticated
    user = await get_current_user(authorization)
    user_id = user['id'] if user else None
    
    try:
        # Save feedback to database
        result = db.save_feedback(
            user_id=user_id,
            chat_id=hash(request.message_id) % 2147483647,  # Convert message_id to int
            rating=request.rating,
            comment=request.comment
        )
        
        if result:
            return {
                "success": True, 
                "message": "Feedback submitted successfully",
                "rating": request.rating
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
            
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
