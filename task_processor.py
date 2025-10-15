"""
Task Processor - Orchestrates task completion workflow
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
import httpx

from code_generator import CodeGenerator
from github_manager import GitHubManager
from config import settings

logger = logging.getLogger(__name__)

class TaskProcessor:
    """Processes coding tasks end-to-end"""
    
    def __init__(self):
        self.code_generator = CodeGenerator()
        self.github_manager = GitHubManager()
        self.tasks = {}
        
    async def process_task(self, task_request) -> Dict[str, Any]:
        """Main task processing pipeline"""
        nonce = task_request.nonce
        
        try:
            self._update_task_status(nonce, "processing", "Generating code...")
            
            # Step 1: Generate code
            logger.info(f"[{nonce}] Step 1: Generating code...")
            code_result = await self.code_generator.generate_solution(
                brief=task_request.brief,
                attachments=task_request.attachments,
                checks=task_request.checks,
                task_id=task_request.task,
                round_num=task_request.round
            )
            
            if not code_result['success']:
                raise Exception(f"Code generation failed: {code_result.get('error')}")
            
            # Determine repo name (NO round number in name)
            repo_name = f"tds-{task_request.task}-{task_request.email.split('@')[0]}"
            repo_name = repo_name.replace('.', '-').replace('_', '-')[:100]  # Sanitize
            
            # Step 2: Check if this is Round 2 (repo should exist)
            if task_request.round == 2:
                logger.info(f"[{nonce}] Round 2 detected - will update existing repo: {repo_name}")
                repo_exists = await self.github_manager.check_repo_exists(repo_name)
                
                if not repo_exists:
                    logger.warning(f"Round 2 but repo doesn't exist. Creating new repo.")
                    # Create repo if it doesn't exist (fallback)
                    repo_result = await self.github_manager.create_repository(
                        repo_name=repo_name,
                        description=f"TDS Task: {task_request.task}"
                    )
                    if not repo_result['success']:
                        raise Exception(f"Repository creation failed: {repo_result.get('error')}")
                    repo_url = repo_result['repo_url']
                else:
                    logger.info(f"Found existing repo for Round 2")
                    repo_url = f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}"
            else:
                # Round 1: Create new repository
                self._update_task_status(nonce, "processing", "Creating GitHub repository...")
                logger.info(f"[{nonce}] Step 2: Creating GitHub repository...")
                
                repo_result = await self.github_manager.create_repository(
                    repo_name=repo_name,
                    description=f"TDS Task: {task_request.task}"
                )
                
                if not repo_result['success']:
                    raise Exception(f"Repository creation failed: {repo_result.get('error')}")
                
                repo_url = repo_result['repo_url']
            
            # Step 3: Commit code (works for both new and existing repos)
            self._update_task_status(nonce, "processing", "Committing code...")
            logger.info(f"[{nonce}] Step 3: Committing code...")
            
            # Prepare files based on round
            if task_request.round == 1:
                files_to_commit = {
                    'index.html': code_result['html_code'],
                    'README.md': self._generate_readme(task_request, repo_url, task_request.round),
                    'LICENSE': self._get_mit_license()
                }
            else:
                # Round 2: Update existing files + add round2 marker
                files_to_commit = {
                    'index.html': code_result['html_code'],
                    'README.md': self._generate_readme(task_request, repo_url, task_request.round),
                    'round2-updates.md': self._generate_round2_notes(task_request)
                }
            
            commit_result = await self.github_manager.commit_or_update_files(
                repo_name=repo_name,
                files=files_to_commit,
                commit_message=f"Round {task_request.round}: {task_request.brief[:50]}"
            )
            
            if not commit_result['success']:
                raise Exception(f"Commit failed: {commit_result.get('error')}")
            
            commit_sha = commit_result['commit_sha']
            
            # Step 4: Enable GitHub Pages (idempotent - safe to call multiple times)
            self._update_task_status(nonce, "processing", "Enabling GitHub Pages...")
            logger.info(f"[{nonce}] Step 4: Enabling GitHub Pages...")
            
            pages_result = await self.github_manager.enable_pages(repo_name)
            pages_url = pages_result.get('pages_url', f"https://{settings.GITHUB_USERNAME}.github.io/{repo_name}/")
            
            # Step 5: Submit to evaluation
            self._update_task_status(nonce, "processing", "Submitting to evaluation...")
            logger.info(f"[{nonce}] Step 5: Submitting to evaluation URL...")
            
            submission_result = await self._submit_to_evaluation(
                evaluation_url=task_request.evaluation_url,
                email=task_request.email,
                task=task_request.task,
                round_num=task_request.round,
                nonce=nonce,
                repo_url=repo_url,
                commit_sha=commit_sha,
                pages_url=pages_url
            )
            
            self._update_task_status(
                nonce, 
                "completed",
                f"Round {task_request.round} completed: {submission_result.get('message', 'Success')}"
            )
            
            logger.info(f"[{nonce}] Task completed successfully!")
            
            return {
                'success': True,
                'repo_url': repo_url,
                'pages_url': pages_url,
                'commit_sha': commit_sha,
                'round': task_request.round,
                'submission_status': submission_result
            }
            
        except Exception as e:
            logger.error(f"[{nonce}] Task processing failed: {e}", exc_info=True)
            self._update_task_status(nonce, "failed", str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _submit_to_evaluation(
        self,
        evaluation_url: str,
        email: str,
        task: str,
        round_num: int,
        nonce: str,
        repo_url: str,
        commit_sha: str,
        pages_url: str
    ) -> Dict[str, Any]:
        """Submit completed task to evaluation URL"""
        try:
            payload = {
                "email": email,
                "task": task,
                "round": round_num,
                "nonce": nonce,
                "repo_url": repo_url,
                "commit_sha": commit_sha,
                "pages_url": pages_url
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(evaluation_url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"Successfully submitted to evaluation: {response.text}")
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'message': 'Submitted successfully'
                    }
                else:
                    logger.warning(f"Evaluation submission returned {response.status_code}: {response.text}")
                    return {
                        'success': False,
                        'status_code': response.status_code,
                        'message': response.text
                    }
                    
        except Exception as e:
            logger.error(f"Failed to submit to evaluation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_readme(self, task_request, repo_url: str, round_num: int) -> str:
        """Generate comprehensive README.md"""
        round_marker = f"(Round {round_num})" if round_num > 1 else ""
        
        return f"""# TDS Project: {task_request.task} {round_marker}

## Task Details

- **Task ID**: {task_request.task}
- **Current Round**: {round_num}
- **Nonce**: {task_request.nonce}

## Round {round_num} Brief

{task_request.brief}

## Implementation

This project was automatically generated using an LLM-powered code generation system.

### Features

- Fully functional HTML/JavaScript solution
- Bootstrap 5 integration for styling
- Responsive design
- Meets all evaluation checks

## Deployment

- **Repository**: {repo_url}
- **GitHub Pages**: Live at the Pages URL

## Development History

{"- **Round 1**: Initial implementation" if round_num == 1 else "- **Round 1**: Initial implementation\n- **Round 2**: Enhanced with additional features"}

## License

MIT License - See LICENSE file

## Generated By

TDS LLM Code Deployment System
Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
    
    def _generate_round2_notes(self, task_request) -> str:
        """Generate Round 2 update notes"""
        return f"""# Round 2 Updates

**Updated on:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Round 2 Task Brief

{task_request.brief}

## Changes in Round 2

This file documents the Round 2 updates to the project. The main `index.html` has been updated with new functionality.

## Task Details

- **Task ID**: {task_request.task}
- **Round**: 2
- **Nonce**: {task_request.nonce}

---

*This is an automated update from the TDS LLM Code Deployment System*
"""
    
    def _get_mit_license(self) -> str:
        """Return MIT License text"""
        year = datetime.utcnow().year
        return f"""MIT License

Copyright (c) {year} 23f3003674

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    
    def _update_task_status(self, nonce: str, status: str, message: str = ""):
        """Update task status in memory"""
        if nonce not in self.tasks:
            self.tasks[nonce] = {
                'nonce': nonce,
                'created_at': datetime.utcnow().isoformat()
            }
        
        self.tasks[nonce].update({
            'status': status,
            'message': message,
            'updated_at': datetime.utcnow().isoformat()
        })
    
    def get_task_status(self, nonce: str) -> Dict[str, Any]:
        """Get status of a specific task"""
        return self.tasks.get(nonce)
    
    def list_all_tasks(self) -> list:
        """List all tasks"""
        return list(self.tasks.values())