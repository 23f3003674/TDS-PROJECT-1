"""
Main FastAPI application for TDS LLM Code Deployment Project
Receives task requests, generates solutions, and submits to GitHub
OPTIMIZED: Returns 200 OK immediately after secret validation
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import logging
from datetime import datetime
import time

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

@app.post("/task")
async def receive_task(request: Request, background_tasks: BackgroundTasks):
    """
    Receive a coding task from instructors
    OPTIMIZED: Returns 200 OK immediately after secret validation
    """
    try:
        # Parse JSON payload
        try:
            payload = await request.json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON body: {e}")
            # Return 200 with error message but still accept
            return JSONResponse(
                status_code=200,
                content={
                    "status": "accepted",
                    "message": "Task accepted but payload parsing failed",
                    "nonce": f"auto-{int(time.time())}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # IMMEDIATE SECRET VALIDATION - Return 401 if invalid
        secret = payload.get('secret')
        if secret != settings.SECRET:
            nonce = payload.get('nonce', 'unknown')
            logger.warning(f"Invalid secret received for task {nonce}")
            raise HTTPException(status_code=401, detail="Invalid secret")
        
        # SECRET IS VALID - Generate immediate response
        nonce = payload.get('nonce') or f"auto-{int(time.time())}"
        task = payload.get('task', f"task-{nonce}")
        
        # Create immediate 200 OK response
        response_data = {
            "status": "accepted",
            "message": f"Task {task} accepted and queued for processing",
            "nonce": nonce,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Queue background processing AFTER preparing response
        background_tasks.add_task(
            process_task_background_safe,
            payload
        )
        
        logger.info(f"✅ Accepted task: {task} (Round {payload.get('round', 1)})")
        
        # Return 200 OK immediately
        return JSONResponse(status_code=200, content=response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 401)
        raise
    except Exception as e:
        # Log error but still return 200 OK
        logger.error(f"Error in receive_task: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "message": f"Task accepted with errors: {str(e)}",
                "nonce": f"error-{int(time.time())}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

async def process_task_background_safe(payload: dict):
    """
    Background task processor with safe payload normalization
    This runs AFTER the 200 OK response is sent
    """
    try:
        # Normalize payload into task request object
        from types import SimpleNamespace
        
        nonce = payload.get('nonce') or f"auto-{int(time.time())}"
        task = payload.get('task', f"task-{nonce}")
        round_num = int(payload.get('round', 1)) if payload.get('round') is not None else 1
        brief = payload.get('brief', '')
        email = payload.get('email', 'unknown@local')
        evaluation_url = payload.get('evaluation_url', '')
        endpoint = payload.get('endpoint', '')
        secret = payload.get('secret', '')
        checks = payload.get('checks', []) or []
        
        # Convert attachments
        raw_attachments = payload.get('attachments', []) or []
        attachments = []
        for a in raw_attachments:
            try:
                if isinstance(a, dict):
                    attachments.append(SimpleNamespace(
                        name=a.get('name', 'unnamed'),
                        url=a.get('url', '')
                    ))
            except Exception as e:
                logger.warning(f"Skipping malformed attachment: {e}")
                continue
        
        # Create task request object
        task_request = SimpleNamespace(
            email=email,
            task=task,
            round=round_num,
            nonce=nonce,
            brief=brief,
            attachments=attachments,
            checks=checks,
            evaluation_url=evaluation_url,
            endpoint=endpoint,
            secret=secret
        )
        
        logger.info(f"[{nonce}] Processing task in background: {task} (Round {round_num})")
        logger.info(f"[{nonce}] Brief: {brief[:100]}...")
        
        # Process the task
        result = await task_processor.process_task(task_request)
        
        if result['success']:
            logger.info(f"[{nonce}] ✅ Task completed successfully")
            logger.info(f"[{nonce}] Repo: {result['repo_url']}")
            logger.info(f"[{nonce}] Pages: {result['pages_url']}")
        else:
            logger.error(f"[{nonce}] ❌ Task failed: {result.get('error')}")
            
    except Exception as e:
        nonce = payload.get('nonce', 'unknown') if isinstance(payload, dict) else 'unknown'
        logger.error(f"[{nonce}] ❌ Background processing failed: {e}", exc_info=True)

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