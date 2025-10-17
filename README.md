---
title: TDS LLM Code Deployment System
emoji: "🚀"
colorFrom: blue
colorTo: green
sdk: docker
sdk_version: "1.0"
app_file: app.py
pinned: false
---

# 🚀 TDS LLM Code Deployment System

An automated system that receives coding tasks, generates solutions using LLM, and deploys them to GitHub Pages - all within 8 minutes!

## 📋 Summary

This project is an **end-to-end automated code deployment pipeline** that:
1. **Receives** task requests via REST API
2. **Generates** HTML/CSS/JavaScript solutions using GPT-5 Nano
3. **Creates** GitHub repositories automatically
4. **Deploys** to GitHub Pages
5. **Submits** results to evaluation endpoints

Built for the **Tools in Data Science (TDS)** course, this system demonstrates the power of LLM-assisted development and automated deployment workflows.

---

## 🎯 Features

### Core Functionality
- ✅ **REST API** - FastAPI-based endpoint for receiving tasks
- ✅ **LLM Integration** - GPT-5 Nano via AI Pipe for code generation
- ✅ **GitHub Automation** - Automatic repo creation and file commits
- ✅ **GitHub Pages** - Instant deployment of generated applications
- ✅ **Round-Based Updates** - Supports iterative improvements (Round 1 & 2)
- ✅ **Webhook Notifications** - POST results to evaluation endpoints

### Technical Highlights
- 🚀 **Fast Processing** - Completes full workflow in < 8 minutes
- 🔄 **Background Tasks** - Asynchronous processing with FastAPI
- 🛡️ **Error Handling** - Comprehensive retry logic and fallbacks
- 📊 **Logging** - Detailed logs for debugging and monitoring
- 🔐 **Secure** - Secret-based authentication for API requests

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Instructor API │
│   (Sends Task)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application (app.py)        │
│  ┌────────────────────────────────────────┐ │
│  │  Task Processor (task_processor.py)   │ │
│  │                                        │ │
│  │  ┌──────────────┐  ┌───────────────┐ │ │
│  │  │ Code         │  │ GitHub        │ │ │
│  │  │ Generator    │  │ Manager       │ │ │
│  │  └──────┬───────┘  └───────┬───────┘ │ │
│  └─────────┼──────────────────┼─────────┘ │
└────────────┼──────────────────┼───────────┘
             │                  │
             ▼                  ▼
      ┌─────────────┐    ┌──────────────┐
      │  GPT-5 Nano │    │   GitHub API │
      │  (AI Pipe)  │    │              │
      └─────────────┘    └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ GitHub Pages │
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │  Evaluation  │
                          │   Endpoint   │
                          └──────────────┘
```

---

## 🚀 Setup

### Prerequisites

- Python 3.11+
- GitHub Personal Access Token (with `repo` permissions)
- AI Pipe API Key (for GPT-5 Nano)
- Hugging Face account (for deployment)

### Installation

```bash
# Clone the repository
git clone https://github.com/23f3003674/TDS-PROJECT-1.git
cd TDS-PROJECT-1

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file or set environment variables:

```bash
# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_token_here
GITHUB_USERNAME=your_github_username

# AI Pipe Configuration
AIMLAPI_KEY=your_aimlapi_key_here
AIMLAPI_BASE_URL=https://aipipe.org/openai/v1
AIMLAPI_MODEL=gpt-5-nano

# API Security
SECRET=your_secret_key_here

# Server Configuration
API_HOST=0.0.0.0
API_PORT=7860
LOG_LEVEL=INFO
```

### Running Locally

```bash
# Run the FastAPI application
python app.py

# Or with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

The API will be available at:
- **Base URL:** http://localhost:7860
- **API Docs:** http://localhost:7860/docs
- **Health Check:** http://localhost:7860/health

---

## 📖 Usage

### API Endpoints

#### 1. Health Check
```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-17T12:00:00.000000",
  "processor_ready": true,
  "github_configured": true,
  "aimlapi_configured": true
}
```

#### 2. Submit Task
```bash
POST /task
```

**Request Body:**
```json
{
  "email": "student@example.com",
  "task": "task-name",
  "round": 1,
  "nonce": "unique-id-123",
  "brief": "Create a Bootstrap page with...",
  "attachments": [],
  "checks": [
    {"js": "document.querySelector('#element') !== null"}
  ],
  "evaluation_url": "https://eval.example.com/callback",
  "endpoint": "https://your-api.hf.space",
  "secret": "your-secret-key"
}
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Task task-name accepted and queued for processing",
  "nonce": "unique-id-123",
  "timestamp": "2025-10-17T12:00:00.000000"
}
```

#### 3. Check Task Status
```bash
GET /status/{nonce}
```

#### 4. List All Tasks
```bash
GET /tasks
```

### Example: Submit a Task

```bash
curl -X POST https://krishnagoel23-tds-project-1.hf.space/task \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "task": "hello-world",
    "round": 1,
    "nonce": "test-'$(date +%s)'",
    "brief": "Create a Bootstrap page with h1 id=\"title\" and button id=\"btn\".",
    "checks": [
      {"js": "document.querySelector(\"#title\") !== null"},
      {"js": "document.querySelector(\"#btn\") !== null"}
    ],
    "evaluation_url": "https://webhook.site/your-id",
    "endpoint": "https://krishnagoel23-tds-project-1.hf.space",
    "secret": "your-secret",
    "attachments": []
  }'
```

---

## 🛠️ Code Explanation

### Project Structure

```
TDS-PROJECT-1/
├── app.py                  # FastAPI application (main entry point)
├── task_processor.py       # Orchestrates task completion workflow
├── code_generator.py       # LLM-based code generation
├── github_manager.py       # GitHub API interactions
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container configuration
├── .dockerignore          # Docker ignore patterns
├── README.md              # This file
└── test_suite.py          # Test scripts
```

### Key Components

#### 1. `app.py` - FastAPI Application
- Receives HTTP requests
- Validates authentication (secret key)
- Queues tasks for background processing
- Returns immediate acceptance response

#### 2. `task_processor.py` - Task Orchestrator
Manages the complete workflow:
1. **Code Generation** - Calls GPT-5 Nano to generate HTML/CSS/JS
2. **Repository Management** - Creates or updates GitHub repo
3. **File Commit** - Commits generated files (index.html, README.md, LICENSE)
4. **Pages Deployment** - Enables GitHub Pages
5. **Evaluation Submission** - POSTs results to callback URL

#### 3. `code_generator.py` - LLM Integration
- Uses OpenAI SDK to communicate with GPT-5 Nano
- Builds comprehensive prompts with task requirements
- Decodes base64 attachments (CSV, Markdown, etc.)
- Falls back to template-based generation if LLM fails

#### 4. `github_manager.py` - GitHub Automation
- Creates repositories via GitHub API
- Commits multiple files in a single transaction
- Handles both new repos and updates
- Enables GitHub Pages hosting

### Workflow

```
1. Receive Task
   ↓
2. Validate Secret
   ↓
3. Queue Background Job
   ↓
4. Return 200 OK (< 2 seconds)
   
   [Background Processing]
   ↓
5. Generate Code with GPT-5 Nano (1-2 min)
   ↓
6. Create/Update GitHub Repo (10-30 sec)
   ↓
7. Commit Files (index.html, README, LICENSE)
   ↓
8. Enable GitHub Pages (5-10 sec)
   ↓
9. POST Results to Evaluation URL
   ↓
10. Complete (Total: 5-6 minutes)
```

---

## ✅ Testing

### Run Test Suite

```bash
# Interactive menu
python3 test_suite.py

# Run specific test
python3 test_suite.py snake
python3 test_suite.py csv
python3 test_suite.py github

# Run all tests
python3 test_suite.py --all
```

### Quick Health Check

```bash
curl https://krishnagoel23-tds-project-1.hf.space
