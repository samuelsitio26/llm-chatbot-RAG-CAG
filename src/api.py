"""
FastAPI Backend for Tourism Recommendation System
Uses Gemini API for LLM with SQLite User Management
"""

import os
import sys
import time
import glob
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

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
        from langchain_community.embeddings import HuggingFaceEmbeddings
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
        print("🌐 API ready at http://0.0.0.0:8000")
        print("📚 Docs available at http://0.0.0.0:8000/docs")
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat request"""
    global cag_system, decision_agent
    
    if not cag_system:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    start_time = time.time()
    
    try:
        # Process query through CAG system (use get_response method)
        result = cag_system.get_response(
            query=request.query,
            use_cache=request.use_cache,
            k=request.k,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature
        )
        
        response_time = time.time() - start_time
        
        # Get decision scores if available
        scores = {}
        if decision_agent:
            try:
                preferences = decision_agent.extract_user_preferences(request.query)
                scores = {"preferences": preferences}
            except Exception as e:
                print(f"⚠️ Warning: Could not get scores: {e}")
                scores = {}
        
        return ChatResponse(
            response=result.get("response", ""),
            cached=result.get("cache_used", False),
            response_time=response_time,
            sources=[],
            scores=scores
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
