"""
Main FastAPI application for TDS LLM Code Deployment Project
ULTRA-FAST: Returns 200 OK in <1 second after secret validation
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
import asyncio

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
    version="2.0.0"
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
    logger.info("🚀 Starting up TDS LLM API...")
    
    try:
        task_processor = TaskProcessor()
        logger.info("✅ Task processor initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize task processor: {e}")
        raise

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "TDS LLM Code Deployment API",
        "status": "running",
        "version": "2.0.0",
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
    Receive a coding task - ULTRA FAST response
    Returns 200 OK within 0.5-1 second after secret validation
    """
    request_start = time.time()
    
    try:
        # STEP 1: Get raw body bytes (fastest possible read)
        raw_body = await request.body()
        
        # STEP 2: Quick JSON parse (minimal processing)
        import json
        try:
            payload = json.loads(raw_body)
        except:
            # Invalid JSON - return 200 anyway
            logger.warning("⚠️ Invalid JSON received")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "accepted",
                    "message": "Request accepted (invalid JSON)",
                    "nonce": f"auto-{int(time.time())}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # STEP 3: IMMEDIATE SECRET CHECK (only thing that blocks 200)
        secret = payload.get('secret')
        if secret != settings.SECRET:
            # Invalid secret = 401 (security requirement)
            nonce = payload.get('nonce', 'unknown')
            logger.warning(f"🔒 Invalid secret for nonce: {nonce}")
            raise HTTPException(status_code=401, detail="Invalid secret")
        
        # STEP 4: Extract minimal info for immediate response
        nonce = payload.get('nonce') or f"auto-{int(time.time())}"
        task = payload.get('task', f"task-{nonce}")
        round_num = payload.get('round', 1)
        
        # STEP 5: Prepare 200 OK response IMMEDIATELY
        response_time = (time.time() - request_start) * 1000  # milliseconds
        logger.info(f"⚡ [{nonce}] Returning 200 OK after {response_time:.0f}ms")
        
        response_content = {
            "status": "accepted",
            "message": f"Task {task} accepted and queued for processing",
            "nonce": nonce,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # STEP 6: Queue background processing (happens AFTER response sent)
        # Fire-and-forget - don't wait for this
        asyncio.create_task(
            process_task_async(payload, nonce)
        )
        
        # STEP 7: Return 200 OK (client gets response NOW)
        return JSONResponse(
            status_code=200,
            content=response_content
        )
        
    except HTTPException:
        # Re-raise 401 for invalid secret
        raise
    except Exception as e:
        # Any other error - still return 200 OK
        logger.error(f"❌ Error in receive_task: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "message": f"Task accepted with error: {str(e)[:100]}",
                "nonce": f"error-{int(time.time())}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

async def process_task_async(payload: dict, nonce: str):
    """
    Async background processor - runs AFTER 200 response sent
    This is fire-and-forget - client doesn't wait for this
    """
    try:
        logger.info(f"[{nonce}] 🔄 Starting background processing...")
        
        # Import here to avoid slowing down the main endpoint
        from types import SimpleNamespace
        
        # Extract all data from payload
        task = payload.get('task', f"task-{nonce}")
        round_num = int(payload.get('round', 1)) if payload.get('round') is not None else 1
        brief = payload.get('brief', '')
        email = payload.get('email', 'unknown@local')
        evaluation_url = payload.get('evaluation_url', '')
        endpoint = payload.get('endpoint', '')
        secret = payload.get('secret', '')
        checks = payload.get('checks', []) or []
        
        # Process attachments
        raw_attachments = payload.get('attachments', []) or []
        attachments = []
        for att in raw_attachments:
            try:
                if isinstance(att, dict):
                    attachments.append(SimpleNamespace(
                        name=att.get('name', 'unnamed'),
                        url=att.get('url', '')
                    ))
            except Exception as e:
                logger.warning(f"[{nonce}] Skipping malformed attachment: {e}")
        
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
        
        logger.info(f"[{nonce}] 📋 Task: {task} (Round {round_num})")
        logger.info(f"[{nonce}] 📝 Brief: {brief[:80]}...")
        
        # Process the task (this takes 5-8 minutes)
        result = await task_processor.process_task(task_request)
        
        # Log result
        if result.get('success'):
            logger.info(f"[{nonce}] ✅ Task completed successfully!")
            logger.info(f"[{nonce}] 🔗 Repo: {result.get('repo_url')}")
            logger.info(f"[{nonce}] 🌐 Pages: {result.get('pages_url')}")
        else:
            logger.error(f"[{nonce}] ❌ Task failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"[{nonce}] 💥 Background processing crashed: {e}", exc_info=True)

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