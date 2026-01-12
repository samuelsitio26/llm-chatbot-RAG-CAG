"""
FastAPI Backend for Tourism Recommendation System
Uses Gemini API for LLM
"""

import os
import sys
import time
import glob
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import GeminiChatModel
from cag_system import CAGSystem
from decision_agent import DecisionMakingAgent

# Global variables
model = None
cag_system = None
decision_agent = None


class ChatRequest(BaseModel):
    query: str
    use_cache: bool = True
    k: int = 5
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    cached: bool
    response_time: float
    sources: list = []
    scores: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup"""
    global model, cag_system, decision_agent
    
    print("=" * 60)
    print("🚀 Starting Tourism Recommendation API")
    print("=" * 60)
    
    try:
        # Initialize Gemini model
        print("📦 Loading Gemini API model...")
        model = GeminiChatModel(model_name="gemini-2.0-flash")
        
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
        pdf_folder = os.path.join(os.path.dirname(__file__), "..", "data", "tourism")
        pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
        if pdf_files:
            cag_system.load_documents(pdf_files)
            print(f"   ✅ Loaded {len(pdf_files)} PDF files")
        else:
            print("   ⚠️ No PDF files found in data/tourism/")
        
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
        "model": "Gemini 2.0 Flash",
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
            k=request.k
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
