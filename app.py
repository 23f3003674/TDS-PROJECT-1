"""
Main FastAPI application for TDS LLM Code Deployment Project
Receives task requests, generates solutions, and submits to GitHub
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import logging
from datetime import datetime

from task_processor import TaskProcessor
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TDS LLM Code Deployment API",
    description="API endpoint for receiving and processing coding tasks",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize task processor
task_processor = None

class Attachment(BaseModel):
    name: str
    url: str

class TaskRequest(BaseModel):
    email: str
    task: str
    round: int
    nonce: str
    brief: str
    attachments: Optional[List[Attachment]] = []
    checks: Optional[List[Dict]] = []
    evaluation_url: str
    endpoint: str
    secret: str

class TaskResponse(BaseModel):
    status: str
    message: str
    nonce: str
    timestamp: str

@app.on_event("startup")
async def startup_event():
    """Initialize task processor on startup"""
    global task_processor
    logger.info("Starting up TDS LLM API...")
    
    try:
        task_processor = TaskProcessor()
        logger.info("Task processor initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize task processor: {e}")
        raise

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "TDS LLM Code Deployment API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "receive_task": "POST /task",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "processor_ready": task_processor is not None,
        "github_configured": bool(settings.GITHUB_TOKEN),
        "aimlapi_configured": bool(settings.AIMLAPI_KEY)
    }

@app.post("/task", response_model=TaskResponse)
async def receive_task(
    task_request: TaskRequest,
    background_tasks: BackgroundTasks
):
    """
    Receive a coding task from instructors
    """
    try:
        logger.info(f"Received task: {task_request.task} (Round {task_request.round})")
        logger.info(f"Brief: {task_request.brief[:100]}...")
        
        # Validate secret
        if task_request.secret != settings.SECRET:
            logger.warning(f"Invalid secret received for task {task_request.nonce}")
            raise HTTPException(status_code=401, detail="Invalid secret")
        
        # Queue task for background processing
        background_tasks.add_task(
            process_task_background,
            task_request
        )
        
        return TaskResponse(
            status="accepted",
            message=f"Task {task_request.task} accepted and queued for processing",
            nonce=task_request.nonce,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error receiving task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

async def process_task_background(task_request: TaskRequest):
    """Background task processor"""
    try:
        logger.info(f"Processing task {task_request.nonce} in background...")
        
        result = await task_processor.process_task(task_request)
        
        if result['success']:
            logger.info(f"Task {task_request.nonce} completed successfully")
            logger.info(f"Repo: {result['repo_url']}")
            logger.info(f"Pages: {result['pages_url']}")
        else:
            logger.error(f"Task {task_request.nonce} failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Background processing failed for {task_request.nonce}: {e}", exc_info=True)

@app.get("/status/{nonce}")
async def get_task_status(nonce: str):
    """Check status of a task by nonce"""
    try:
        status = task_processor.get_task_status(nonce)
        if not status:
            raise HTTPException(status_code=404, detail="Task not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks():
    """List all processed tasks (for debugging)"""
    try:
        tasks = task_processor.list_all_tasks()
        return {
            "total": len(tasks),
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
        log_level="info"
    )