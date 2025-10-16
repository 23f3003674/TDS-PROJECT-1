"""
GitHub Manager - Handles GitHub repository operations
"""
import logging
from typing import Dict, Any
import httpx
from datetime import datetime
import base64

from config import settings

logger = logging.getLogger(__name__)

class GitHubManager:
    """Manages GitHub repository operations via API"""
    
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.username = settings.GITHUB_USERNAME
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    async def create_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False
    ) -> Dict[str, Any]:
        """Create a new GitHub repository"""
        try:
            logger.info(f"Creating repository: {repo_name}")
            
            payload = {
                "name": repo_name,
                "description": description,
                "private": private,
                "auto_init": False,
                "has_issues": True,
                "has_projects": False,
                "has_wiki": False
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/user/repos",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    data = response.json()
                    logger.info(f"Repository created: {data['html_url']}")
                    return {
                        'success': True,
                        'repo_url': data['html_url'],
                        'clone_url': data['clone_url'],
                        'full_name': data['full_name']
                    }
                else:
                    error_msg = response.text
                    logger.error(f"Failed to create repository: {error_msg}")
                    # Detect name already exists
                    if response.status_code == 422 and 'name already exists' in error_msg.lower():
                        return {
                            'success': False,
                            'error': f"GitHub API error: {response.status_code} - {error_msg}",
                            'name_exists': True
                        }
                    return {
                        'success': False,
                        'error': f"GitHub API error: {response.status_code} - {error_msg}"
                    }
                    
        except Exception as e:
            logger.error(f"Exception creating repository: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
        
    async def check_repo_exists(self, repo_name: str) -> bool:
        """Check if a repository exists"""
        try:
            full_repo_name = f"{self.username}/{repo_name}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{full_repo_name}",
                    headers=self.headers
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error checking repo existence: {e}")
            return False
    
    async def commit_or_update_files(
        self,
        repo_name: str,
        files: Dict[str, str],
        commit_message: str = "Update files",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Commit new files or update existing files in repository.
        Works for both new and existing repos.
        """
        try:
            logger.info(f"Committing/updating {len(files)} files in {repo_name}")
            
            full_repo_name = f"{self.username}/{repo_name}"
            
            # Check if repo is empty or has files
            branch_ref = await self._get_or_create_branch(full_repo_name, branch)
            
            if not branch_ref:
                return {'success': False, 'error': 'Failed to get/create branch'}
            
            # If repo is empty, use simple file creation
            if branch_ref.get('empty_repo'):
                logger.info("Empty repo detected, using direct file creation")
                return await self._commit_to_empty_repo(full_repo_name, files, commit_message, branch)
            
            # Repo has files - update them individually
            logger.info("Updating files in existing repo")
            return await self._update_existing_files(full_repo_name, files, commit_message, branch)
            
        except Exception as e:
            logger.error(f"Exception in commit_or_update_files: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _update_existing_files(
        self,
        full_repo_name: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> Dict[str, Any]:
        """Update files in an existing repository"""
        try:
            logger.info(f"Updating {len(files)} files in existing repo")
            
            commit_sha = None
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for filename, content in files.items():
                    logger.info(f"Updating file: {filename}")
                    
                    # First, get the file to get its SHA (required for updates)
                    get_response = await client.get(
                        f"{self.base_url}/repos/{full_repo_name}/contents/{filename}",
                        headers=self.headers,
                        params={"ref": branch}
                    )
                    
                    payload = {
                        "message": f"{commit_message} - {filename}",
                        "content": base64.b64encode(content.encode()).decode(),
                        "branch": branch
                    }
                    
                    # If file exists, include its SHA for update
                    if get_response.status_code == 200:
                        existing_file = get_response.json()
                        payload["sha"] = existing_file["sha"]
                        logger.info(f"  File exists, updating...")
                    else:
                        logger.info(f"  File doesn't exist, creating...")
                    
                    # Create or update file
                    response = await client.put(
                        f"{self.base_url}/repos/{full_repo_name}/contents/{filename}",
                        headers=self.headers,
                        json=payload
                    )
                    
                    if response.status_code in [200, 201]:
                        commit_sha = response.json()['commit']['sha']
                        logger.info(f"  ✅ {filename} updated successfully")
                    else:
                        logger.warning(f"  ⚠️ Failed to update {filename}: {response.text}")
            
            if commit_sha:
                logger.info(f"All files updated. Latest commit SHA: {commit_sha}")
                return {
                    'success': True,
                    'commit_sha': commit_sha,
                    'files_committed': list(files.keys())
                }
            else:
                return {
                    'success': False,
                    'error': 'No files were successfully updated'
                }
                
        except Exception as e:
            logger.error(f"Exception updating files: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def commit_files(
        self,
        repo_name: str,
        files: Dict[str, str],
        commit_message: str = "Initial commit",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Legacy method - redirects to commit_or_update_files
        """
        return await self.commit_or_update_files(repo_name, files, commit_message, branch)
    
    async def _commit_to_empty_repo(
        self,
        full_repo_name: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> Dict[str, Any]:
        """
        Commit files to an empty repository using GitHub's file creation API
        """
        try:
            logger.info(f"Committing {len(files)} files to empty repo")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # For empty repos, we need to create files one by one
                # Start with the first file to initialize the repo
                first_file = list(files.keys())[0]
                first_content = files[first_file]
                
                logger.info(f"Creating initial file: {first_file}")
                
                # Create first file to initialize repo
                response = await client.put(
                    f"{self.base_url}/repos/{full_repo_name}/contents/{first_file}",
                    headers=self.headers,
                    json={
                        "message": commit_message,
                        "content": base64.b64encode(first_content.encode()).decode(),
                        "branch": branch
                    }
                )
                
                if response.status_code not in [200, 201]:
                    logger.error(f"Failed to create first file: {response.text}")
                    return {'success': False, 'error': f'Failed to create {first_file}'}
                
                first_commit_data = response.json()
                commit_sha = first_commit_data['commit']['sha']
                
                # Now add remaining files
                for filename, content in files.items():
                    if filename == first_file:
                        continue
                    
                    logger.info(f"Adding file: {filename}")
                    
                    response = await client.put(
                        f"{self.base_url}/repos/{full_repo_name}/contents/{filename}",
                        headers=self.headers,
                        json={
                            "message": f"Add {filename}",
                            "content": base64.b64encode(content.encode()).decode(),
                            "branch": branch
                        }
                    )
                    
                    if response.status_code in [200, 201]:
                        commit_sha = response.json()['commit']['sha']
                    else:
                        logger.warning(f"Failed to add {filename}: {response.text}")
                
                logger.info(f"Successfully committed all files. Final commit SHA: {commit_sha}")
                
                return {
                    'success': True,
                    'commit_sha': commit_sha,
                    'files_committed': list(files.keys())
                }
                
        except Exception as e:
            logger.error(f"Exception in _commit_to_empty_repo: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_or_create_branch(self, full_repo_name: str, branch: str) -> Dict:
        """Get existing branch or create new one"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try to get existing branch
                response = await client.get(
                    f"{self.base_url}/repos/{full_repo_name}/git/ref/heads/{branch}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Get commit details
                    commit_response = await client.get(
                        data['object']['url'],
                        headers=self.headers
                    )
                    commit_data = commit_response.json()
                    
                    return {
                        'ref': data['ref'],
                        'sha': data['object']['sha'],
                        'commit_sha': data['object']['sha'],
                        'tree_sha': commit_data.get('tree', {}).get('sha')
                    }
                
                # Branch doesn't exist - repo is empty
                logger.info(f"Branch {branch} doesn't exist, will create with first commit")
                
                # For empty repos, return marker to signal we need to use PUT method
                return {
                    'empty_repo': True,
                    'branch': branch
                }
                
        except Exception as e:
            logger.error(f"Error in get_or_create_branch: {e}")
            return None
    
    async def _create_blob(self, full_repo_name: str, content: str) -> str:
        """Create a blob (file content) in repository"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{full_repo_name}/git/blobs",
                    headers=self.headers,
                    json={
                        "content": content,
                        "encoding": "utf-8"
                    }
                )
                
                if response.status_code == 201:
                    return response.json()['sha']
                else:
                    logger.error(f"Failed to create blob: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Exception creating blob: {e}")
            return None
    
    async def _create_tree(
        self,
        full_repo_name: str,
        blobs: Dict[str, str],
        base_tree: str = None
    ) -> str:
        """Create a tree (directory structure) in repository"""
        try:
            tree_items = []
            for filename, blob_sha in blobs.items():
                tree_items.append({
                    "path": filename,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })
            
            payload = {"tree": tree_items}
            if base_tree:
                payload["base_tree"] = base_tree
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{full_repo_name}/git/trees",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    return response.json()['sha']
                else:
                    logger.error(f"Failed to create tree: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Exception creating tree: {e}")
            return None
    
    async def _create_commit(
        self,
        full_repo_name: str,
        tree_sha: str,
        parent_sha: str,
        message: str
    ) -> str:
        """Create a commit in repository"""
        try:
            payload = {
                "message": message,
                "tree": tree_sha,
                "parents": [parent_sha] if parent_sha else []
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{full_repo_name}/git/commits",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    return response.json()['sha']
                else:
                    logger.error(f"Failed to create commit: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Exception creating commit: {e}")
            return None
    
    async def _update_ref(
        self,
        full_repo_name: str,
        branch: str,
        commit_sha: str
    ) -> bool:
        """Update branch reference to point to new commit"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{self.base_url}/repos/{full_repo_name}/git/refs/heads/{branch}",
                    headers=self.headers,
                    json={"sha": commit_sha, "force": False}
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Exception updating ref: {e}")
            return False
    
    async def enable_pages(self, repo_name: str, branch: str = "main") -> Dict[str, Any]:
        """Enable GitHub Pages for repository"""
        try:
            logger.info(f"Enabling GitHub Pages for {repo_name}")
            
            full_repo_name = f"{self.username}/{repo_name}"
            
            payload = {
                "source": {
                    "branch": branch,
                    "path": "/"
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{full_repo_name}/pages",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code in [201, 409]:
                    pages_url = f"https://{self.username}.github.io/{repo_name}/"
                    logger.info(f"GitHub Pages enabled: {pages_url}")
                    return {
                        'success': True,
                        'pages_url': pages_url
                    }
                else:
                    logger.warning(f"Pages enable returned {response.status_code}: {response.text}")
                    return {
                        'success': True,
                        'pages_url': f"https://{self.username}.github.io/{repo_name}/"
                    }
                    
        except Exception as e:
            logger.error(f"Exception enabling pages: {e}", exc_info=True)
            return {
                'success': True,
                'pages_url': f"https://{self.username}.github.io/{repo_name}/"
            }