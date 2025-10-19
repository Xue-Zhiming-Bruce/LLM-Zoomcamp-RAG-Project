import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os

from config import config
from rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Podcast Q&A API",
    description="A simple API for querying podcast content using RAG",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG service
rag_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global rag_service
    try:
        config.validate()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
    try:
        rag_service = RAGService()
        logger.info("RAG service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        rag_service = None

# Pydantic models for request/response
class ChatRequest(BaseModel):
    query: str
    limit: Optional[int] = None

class ChatResponse(BaseModel):
    answer: str
    sources: list
    query: str

class HealthResponse(BaseModel):
    status: str
    components: dict

# API Routes
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        health_status = rag_service.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint for asking questions"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        result = rag_service.chat(request.query, request.limit)
        return result
    except Exception as e:
        logger.error(f"Chat request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search")
async def search(query: str, limit: Optional[int] = None):
    """Search endpoint for finding similar content"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        results = rag_service.search_similar_content(query, limit)
        return {"results": results, "query": query}
    except Exception as e:
        logger.error(f"Search request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serve static files (frontend)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve the frontend HTML file"""
        index_path = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {"message": "Frontend not found. Please check the frontend directory."}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )