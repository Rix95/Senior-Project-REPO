# src/backend/api/git_integration.py

import subprocess
import os
from tempfile import TemporaryDirectory
import json

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
        subprocess.run(
            ["git", "clone", repo_url, repo_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["git", "-C", repo_path, "switch", revision],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return repo_path, temp_dir

    except Exception as e:
        temp_dir.cleanup()
        raise Exception(f"Git switch failed: {e}")

def get_github_linguist_metadata(repo_path: str):
    """
    Retrieve language metadata from the repository using GitHub Linguist.
    Returns a dict with:
        {
          'dominant_language': <str>,
          'language_percentages': {
              <Language1>: <pct_float>,
              <Language2>: <pct_float>,
              ...
          }
        }
    """
    try:
        # Use --json for stable, parseable output
        cmd = ["github-linguist", repo_path, "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        data = json.loads(result.stdout)
        # Example `data`:
        # {
        #   "JavaScript": {"size": 489643, "percentage": "99.89"},
        #   "Makefile":   {"size": 330,    "percentage": "0.07"},
        #   "Shell":      {"size": 229,    "percentage": "0.05"}
        # }

        language_percentages = {}
        for lang_name, info in data.items():
            # The `percentage` field is a string representing a float
            pct_str = info.get("percentage", "0.0")
            try:
                pct_val = float(pct_str)
            except ValueError:
                pct_val = 0.0
            language_percentages[lang_name] = pct_val

        # Dominant language = highest percentage
        if language_percentages:
            dominant_lang = max(language_percentages, key=language_percentages.get)
        else:
            dominant_lang = "Unknown"

        return {
            "dominant_language": dominant_lang,
            "language_percentages": language_percentages
        }

    except subprocess.CalledProcessError as e:
        # If github-linguist fails for any reason, return a default
        return {
            "dominant_language": "Unknown",
            "language_percentages": {}
        }
