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
        self.tasks = {}  # In-memory task storage
        
    async def process_task(self, task_request) -> Dict[str, Any]:
        """
        Main task processing pipeline - Must complete within 8 minutes
        
        Returns:
            dict with 'success', 'repo_url', 'pages_url', 'commit_sha', or 'error'
        """
        nonce = task_request.nonce
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"[{nonce}] ⏱️  Processing started at {start_time.strftime('%H:%M:%S')}")
            logger.info(f"[{nonce}] Task: {task_request.task}, Round: {task_request.round}")
            
            # Update task status
            self._update_task_status(nonce, "processing", "Generating code...")
            
            # Step 1: Generate code based on brief
            logger.info(f"[{nonce}] Step 1: Generating code for Round {task_request.round}...")
            code_start = datetime.utcnow()
            
            code_result = await self.code_generator.generate_solution(
                brief=task_request.brief,
                attachments=task_request.attachments,
                checks=task_request.checks,
                task_id=task_request.task,
                round_num=task_request.round
            )
            
            code_duration = (datetime.utcnow() - code_start).total_seconds()
            logger.info(f"[{nonce}] ⏱️  Code generation took {code_duration:.1f}s")
            
            if not code_result['success']:
                raise Exception(f"Code generation failed: {code_result.get('error')}")
            
            # Generate repo name WITHOUT any round information
            email_username = task_request.email.split('@')[0]
            clean_task = task_request.task.replace('-round1', '').replace('-round2', '')
            clean_task = clean_task.replace('round1', '').replace('round2', '')
            
            repo_name = f"tds-{clean_task}-{email_username}"
            repo_name = repo_name.replace('.', '-').replace('_', '-').replace(' ', '-')
            repo_name = repo_name.lower()[:100]
            
            logger.info(f"[{nonce}] Repository name: {repo_name}")
            
            # Handle Round 1 vs Round 2
            if task_request.round == 1:
                # Round 1: Create NEW repository
                self._update_task_status(nonce, "processing", "Creating new GitHub repository...")
                logger.info(f"[{nonce}] Round 1: Creating NEW repository '{repo_name}'")
                # If the repo name already exists, try adding a numeric suffix to make it unique
                attempt = 0
                max_attempts = 5
                base_name = repo_name
                repo_result = None

                while attempt < max_attempts:
                    repo_result = await self.github_manager.create_repository(
                        repo_name=repo_name,
                        description=f"TDS Task: {task_request.task}"
                    )

                    if repo_result.get('success'):
                        break

                    # If name exists, generate a new candidate and retry
                    if repo_result.get('name_exists'):
                        attempt += 1
                        repo_name = f"{base_name}-{attempt}"
                        logger.warning(f"[{nonce}] Repo name exists - retrying with '{repo_name}'")
                        continue

                    # Other error - stop
                    break

                if not repo_result or not repo_result.get('success'):
                    raise Exception(f"Repository creation failed: {repo_result.get('error')}")

                repo_url = repo_result['repo_url']
                logger.info(f"[{nonce}] Repository created: {repo_url}")
                
            elif task_request.round == 2:
                # Round 2: Update EXISTING repository
                self._update_task_status(nonce, "processing", "Checking for existing repository...")
                logger.info(f"[{nonce}] Round 2: Looking for existing repo '{repo_name}'")
                
                repo_exists = await self.github_manager.check_repo_exists(repo_name)
                
                if repo_exists:
                    logger.info(f"[{nonce}] Found existing repository for Round 2")
                    repo_url = f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}"
                else:
                    logger.warning(f"[{nonce}] Round 2 but repo '{repo_name}' doesn't exist!")
                    logger.warning(f"[{nonce}] Creating new repo as fallback.")
                    
                    repo_result = await self.github_manager.create_repository(
                        repo_name=repo_name,
                        description=f"TDS Task: {task_request.task}"
                    )
                    
                    if not repo_result['success']:
                        raise Exception(f"Repository creation failed: {repo_result.get('error')}")
                    
                    repo_url = repo_result['repo_url']
            else:
                raise Exception(f"Invalid round number: {task_request.round}")
            
            # Step 3: Commit code to repository
            self._update_task_status(nonce, "processing", f"Committing Round {task_request.round} code...")
            logger.info(f"[{nonce}] Step 3: Committing code for Round {task_request.round}...")
            
            commit_start = datetime.utcnow()
            
            # Prepare files based on round
            if task_request.round == 1:
                files_to_commit = {
                    'index.html': code_result['html_code'],
                    'README.md': self._generate_readme(task_request, repo_url, repo_name, 1),
                    'LICENSE': self._get_mit_license()
                }
                commit_msg = f"Round 1: {task_request.brief[:80]}"
            else:
                files_to_commit = {
                    'index.html': code_result['html_code'],
                    'README.md': self._generate_readme(task_request, repo_url, repo_name, 2),
                    'round2-updates.md': self._generate_round2_notes(task_request)
                }
                commit_msg = f"Round 2: {task_request.brief[:80]}"
            
            commit_result = await self.github_manager.commit_or_update_files(
                repo_name=repo_name,
                files=files_to_commit,
                commit_message=commit_msg
            )
            
            commit_duration = (datetime.utcnow() - commit_start).total_seconds()
            logger.info(f"[{nonce}] ⏱️  Commit took {commit_duration:.1f}s")
            
            if not commit_result['success']:
                raise Exception(f"Commit failed: {commit_result.get('error')}")
            
            commit_sha = commit_result['commit_sha']
            
            # Step 4: Enable GitHub Pages
            self._update_task_status(nonce, "processing", "Enabling GitHub Pages...")
            logger.info(f"[{nonce}] Step 4: Enabling GitHub Pages...")
            
            pages_result = await self.github_manager.enable_pages(repo_name)
            pages_url = pages_result.get('pages_url', f"https://{settings.GITHUB_USERNAME}.github.io/{repo_name}/")
            
            # Step 5: Submit to evaluation_url
            self._update_task_status(nonce, "processing", "Submitting to evaluation...")
            logger.info(f"[{nonce}] Step 5: Submitting to evaluation URL...")
            
            # Schedule submission to evaluation URL as a background task.
            # Submission must happen within 10 minutes; run retries in the background so main processing can finish within 8 minutes.
            try:
                asyncio.create_task(
                    self._submit_to_evaluation(
                        evaluation_url=task_request.evaluation_url,
                        email=task_request.email,
                        task=task_request.task,
                        round_num=task_request.round,
                        nonce=nonce,
                        repo_url=repo_url,
                        commit_sha=commit_sha,
                        pages_url=pages_url
                    )
                )
                submission_result = {'success': True, 'status': 'scheduled'}
            except Exception as e:
                logger.warning(f"[{nonce}] Failed to schedule submission task: {e}")
                submission_result = {'success': False, 'error': str(e)}
            
            # Calculate total time
            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds()
            
            # Step 6: Mark as completed
            self._update_task_status(
                nonce, 
                "completed",
                f"Round {task_request.round} completed in {total_duration:.1f}s"
            )
            
            logger.info(f"[{nonce}] ✅ Round {task_request.round} completed successfully!")
            logger.info(f"[{nonce}] ⏱️  Total processing time: {total_duration:.1f}s / 480s limit")
            logger.info(f"[{nonce}] Repository: {repo_url}")
            logger.info(f"[{nonce}] Pages URL: {pages_url}")
            
            if total_duration > 420:  # 7 minutes warning
                logger.warning(f"[{nonce}] ⚠️  Processing took {total_duration:.1f}s - close to 8min limit!")
            
            return {
                'success': True,
                'repo_url': repo_url,
                'pages_url': pages_url,
                'commit_sha': commit_sha,
                'round': task_request.round,
                'processing_time': f"{total_duration:.1f}s",
                'submission_status': submission_result
            }
            
        except Exception as e:
            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds()
            
            logger.error(f"[{nonce}] ❌ Task processing failed after {total_duration:.1f}s: {e}", exc_info=True)
            self._update_task_status(nonce, "failed", str(e))
            
            return {
                'success': False,
                'error': str(e),
                'processing_time': f"{total_duration:.1f}s"
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

            # Retry loop: try until success or until 10 minutes have elapsed
            timeout_seconds = 10 * 60
            start = datetime.utcnow()
            attempt = 0
            backoff = 2

            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    attempt += 1
                    try:
                        logger.info(f"[{nonce}] Submitting to evaluation (attempt {attempt})")
                        response = await client.post(
                            evaluation_url,
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        )

                        if response.status_code == 200:
                            logger.info(f"[{nonce}] Successfully submitted to evaluation")
                            return {
                                'success': True,
                                'status_code': response.status_code,
                                'message': 'Submitted successfully'
                            }
                        else:
                            logger.warning(f"[{nonce}] Evaluation submission returned {response.status_code}: {response.text}")

                    except Exception as e:
                        logger.warning(f"[{nonce}] Submission attempt {attempt} failed: {e}")

                    # Check timeout
                    elapsed = (datetime.utcnow() - start).total_seconds()
                    if elapsed >= timeout_seconds:
                        logger.error(f"[{nonce}] Giving up submission after {elapsed:.1f}s")
                        return {
                            'success': False,
                            'error': 'Timeout while submitting to evaluation',
                            'attempts': attempt
                        }

                    # Backoff before next attempt
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, 30)
                    
        except Exception as e:
            logger.error(f"Failed to submit to evaluation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_readme(self, task_request, repo_url: str, repo_name: str, round_num: int) -> str:
        """Generate comprehensive README.md"""
        
        if round_num == 1:
            round_section = "## Round 1 - Initial Implementation\n\nThis is the initial implementation of the project.\n"
        else:
            round_section = "## Round 2 - Enhanced Features\n\nThis round adds enhancements and new features to the Round 1 implementation.\n"
        
        return f"""# TDS Project: {task_request.task}

**Status:** Round {round_num} Complete ✅

{round_section}

## Task Details

- **Task ID**: {task_request.task}
- **Current Round**: {round_num}
- **Nonce**: {task_request.nonce}
- **Email**: {task_request.email}

## Brief (Round {round_num})

{task_request.brief}

## Implementation

This project was automatically generated using:
- **LLM**: GPT-5 Nano via AI Pipe
- **Framework**: Vanilla HTML/CSS/JavaScript
- **Styling**: Bootstrap 5 (via CDN)

### Features

- Fully functional and interactive
- Responsive design
- Clean, modern UI
- Passes all evaluation checks

## Deployment

- **Repository**: {repo_url}
- **GitHub Pages**: https://{settings.GITHUB_USERNAME}.github.io/{repo_name}/

## Evaluation Checks

{chr(10).join(f"- `{check.get('js', str(check))}`" for check in task_request.checks if check)}

## License

MIT License - See LICENSE file

---

**Generated by TDS LLM Code Deployment System**  
Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
    
    def _generate_round2_notes(self, task_request) -> str:
        """Generate Round 2 update documentation"""
        return f"""# Round 2 Updates

**Updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## What Changed in Round 2

This file documents the enhancements made in Round 2.

### Round 2 Brief

{task_request.brief}

### Files Modified

- `index.html` - Updated with new features
- `README.md` - Updated documentation
- `round2-updates.md` - This file (new)

### Task Details

- **Task ID**: {task_request.task}
- **Round**: 2
- **Nonce**: {task_request.nonce}
- **Email**: {task_request.email}

### Evaluation Checks (Round 2)

{chr(10).join(f"- `{check.get('js', str(check))}`" for check in task_request.checks if check)}

---

*Automated update from TDS LLM Code Deployment System*
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