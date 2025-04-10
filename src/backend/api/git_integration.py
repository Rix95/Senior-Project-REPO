# src/backend/api/git_integration.py

import subprocess
import os
from tempfile import TemporaryDirectory

def git_switch_revision(repo_url: str, revision: str):
    """
    Clone the given repository and switch to a specific revision using 'git switch'.
    
    Parameters:
      repo_url (str): The URL of the repository to clone.
      revision (str): The revision (branch, tag, or commit) to switch to.
    
    Returns:
      tuple: (repo_path, temp_dir) where repo_path is the absolute path to the checked-out repository,
             and temp_dir is a TemporaryDirectory object that must be cleaned up by the caller.
    
    Raises:
      Exception: If cloning or switching fails.
    """
    temp_dir = TemporaryDirectory()
    repo_path = os.path.join(temp_dir.name, "repo")
    try:
        print(f"[git_integration] Cloning repository from {repo_url} into {repo_path}...")
        subprocess.run(
            ["git", "clone", repo_url, repo_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"[git_integration] Successfully cloned repository. Switching to revision '{revision}'...")
        subprocess.run(
            ["git", "-C", repo_path, "switch", revision],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"[git_integration] Successfully switched to revision '{revision}'.")
        return repo_path, temp_dir
    except Exception as e:
        temp_dir.cleanup()
        raise Exception(f"Git switch failed: {e}")

def get_github_linguist_metadata(repo_path: str):
    """
    Retrieve language metadata from the repository.
    
    This is a placeholder function. In production, you could integrate with GitHub's Linguist
    (or another language analysis tool) to retrieve real metadata for the repository.
    
    For example, if a command-line tool 'github-linguist' were available, you might run:
      result = subprocess.run(["github-linguist", repo_path], capture_output=True, text=True)
      # Process result.stdout to build your metadata dictionary.
    
    Returns:
      dict: A dictionary with keys such as 'dominant_language' and 'language_percentages'.
    """
    # For demonstration purposes, we return static metadata.
    metadata = {
        "dominant_language": "Python",
        "language_percentages": {
            "Python": 80,
            "JavaScript": 15,
            "Other": 5
        }
    }
    return metadata