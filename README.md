# TDS LLM Code Deployment

This repository runs a FastAPI service that receives coding tasks, generates an HTML solution (via an LLM or fallback), creates/updates a GitHub repo, and enables GitHub Pages.

## Quick start (local)

1. Create a `.env` file with these variables:

```
GITHUB_TOKEN=ghp_xxx
GITHUB_USERNAME=your-username
AIMLAPI_KEY=sk_xxx
AIMLAPI_BASE_URL=https://aipipe.org/openai/v1
AIMLAPI_MODEL=gpt-5-nano
SECRET=your-secret-key
```

2. Build and run locally with Docker (Windows PowerShell):

```powershell
docker build -t tds-project . ; docker run -e GITHUB_TOKEN -e GITHUB_USERNAME -e AIMLAPI_KEY -e SECRET -p 7860:7860 tds-project
```

3. Or run locally in Python venv:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app:app --host 0.0.0.0 --port 7860
```

## Hugging Face Spaces (Docker)

Hugging Face Spaces supports Docker-based apps. To deploy:

1. Create a new Space and choose "Docker".
2. Add your repo (or push this repo) to the Space.
3. Set required secrets in the Space settings: `GITHUB_TOKEN`, `GITHUB_USERNAME`, `AIMLAPI_KEY`, `SECRET`.
4. The provided `Dockerfile` will run the FastAPI app on port 7860.

Notes:
- The app expects POST /task requests with JSON payload including `secret` matching `SECRET`.
- If you have trouble with the AI Pipe OpenAI client, the code falls back to an internal HTML generator.

## Changelog
- Improved input normalization for `/task` (handles raw JSON and returns 200 accepted).
- Retries GitHub repo creation with suffixes when a name collision occurs.
- Fallback HTML generator produces interactive pages (CSV parsing, filters, GitHub fetch form).
