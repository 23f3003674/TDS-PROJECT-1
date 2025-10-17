"""
Main FastAPI application for TDS LLM Code Deployment Project
Receives task requests, generates solutions, and submits to GitHub
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import logging
from datetime import datetime
import threading

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
async def receive_task(request: Request):
    """
    Immediately return 200 OK if secret matches, then process task in a separate thread.
    """
    try:
        try:
            payload = await request.json()
        except Exception:
            logger.warning("Received non-JSON or invalid JSON body for /task")
            payload = {}

        secret = payload.get("secret") if isinstance(payload, dict) else None
        nonce = payload.get("nonce", f"auto-{int(datetime.utcnow().timestamp())}")
        task_name = payload.get("task", f"task-{nonce}")

        # ✅ Step 1: Verify secret
        if secret != settings.SECRET:
            logger.warning(f"❌ Invalid secret received for task {nonce}")
            raise HTTPException(status_code=401, detail="Invalid secret")

        # ✅ Step 2: Return 200 OK immediately
        logger.info(f"✅ Secret matched for task {nonce}. Returning 200 OK and spawning thread.")
        response = TaskResponse(
            status="ok",
            message=f"Secret verified for {task_name}. Task will process in background thread.",
            nonce=nonce,
            timestamp=datetime.utcnow().isoformat()
        )

        # ✅ Step 3: Start background processing in a separate thread
        def background_thread():
            try:
                from types import SimpleNamespace
                raw_attachments = payload.get('attachments', []) or []
                attachments = [
                    SimpleNamespace(name=a.get('name'), url=a.get('url'))
                    for a in raw_attachments if isinstance(a, dict)
                ]
                task_request_obj = SimpleNamespace(
                    email=payload.get('email', 'unknown@local'),
                    task=task_name,
                    round=int(payload.get('round', 1)),
                    nonce=nonce,
                    brief=payload.get('brief', ''),
                    attachments=attachments,
                    checks=payload.get('checks', []) or [],
                    evaluation_url=payload.get('evaluation_url', ''),
                    endpoint=payload.get('endpoint', ''),
                    secret=secret
                )

                logger.info(f"Thread started for task {nonce}")
                import asyncio
                asyncio.run(task_processor.process_task(task_request_obj))
                logger.info(f"Thread finished processing task {nonce}")
            except Exception as e:
                logger.error(f"Thread failed for task {nonce}: {e}", exc_info=True)

        threading.Thread(target=background_thread, daemon=True).start()
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling /task request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    

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