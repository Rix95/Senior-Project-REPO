#!/usr/bin/env python3
"""
Concatenation script for VulGPT that complies with all filtering requirements.
Prioritizes the most important files while respecting blocklisted extensions and size limits.

Usage:
    python selective_concat.py --package 101 --output prompt.txt --target-size 5000
"""
import argparse
import json
import tempfile
import subprocess
import tarfile
import mimetypes
import shutil
import sys
import os
import time
from pathlib import Path
from collections import defaultdict

# FILTER: Blocked file extensions
BLOCKLISTED_EXTENSIONS = {
    ".css", ".lock", ".md", ".min.js", ".scss", ".txt", ".rst"
}

# FILTER: Max size limit
MAX_FILE_SIZE = 200_000  # characters

# File priority rules (higher score = more important for vulnerability detection)
FILE_PRIORITIES = {
    'index.js': 100,        # Main entry points are critical
    'main.js': 100,
    'server.js': 95,
    'app.js': 95,
    'config': 90,           # Configuration files
    'secret': 95,           # Potential secrets/credentials
    'auth': 95,             # Authentication critical for security
    'security': 95,         # Security related
    'password': 90,         # Password handling
    'token': 90,            # Token handling
    'session': 90,          # Session management
    'crypto': 90,           # Cryptography
    'encrypt': 90,          # Encryption
    'decrypt': 90,          # Decryption  
    'router': 80,           # Route definitions
    'middleware': 75,       # Middleware files
    'database': 85,         # Database connections
    'db': 85,               # Database
    'sql': 85,              # SQL queries
    'api': 85,              # API endpoints
    'request': 80,          # Request handling
    'response': 80,         # Response handling
    'cache': 75,            # Cache handling
    'logger': 70,           # Logging
    'util': 60,             # Utility functions
    'helper': 60,           # Helper functions
    'test': 0,              # Test files less critical for security analysis
    'spec': 0,              # Test specs
    'mock': 0,              # Mock files
    'fixture': 0,           # Test fixtures
}

def parse_purl(purl: str) -> dict:
    """
    Parse a Package URL (purl) and return its components including qualifiers.
    Returns a dict with keys: type, namespace, name, version, qualifiers.
    """
    core, *qual = purl.split('?')
    if not core.startswith('pkg:'):
        raise ValueError(f"Invalid purl: {purl}")
    body = core[4:]
    parts = body.split('/')
    pkg_type = parts[0]
    name_part = parts[-1]
    if '@' in name_part:
        name, version = name_part.split('@', 1)
    else:
        name, version = name_part, None
    namespace = parts[1:-1]
    qualifiers = {}
    if qual:
        for kv in qual[0].split('&'):
            if '=' in kv:
                k, v = kv.split('=', 1)
                qualifiers[k] = v
    return {'type': pkg_type, 'namespace': namespace, 'name': name, 'version': version, 'qualifiers': qualifiers}

def check_npm_installed():
    """Check if npm is installed and available in PATH"""
    try:
        # On Windows
        if sys.platform == 'win32':
            # Use 'where' command on Windows to find npm in PATH
            result = subprocess.run('where npm', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.returncode == 0
        else:
            # On Unix
            result = subprocess.run(['which', 'npm'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
    except Exception:
        return False

def download_npm_package(name: str, version: str, dest: Path, debug=False) -> Path:
    """
    Use `npm pack` to download a .tgz for the given package@version into dest and extract it.
    Returns the path to the extracted directory.
    """
    if not check_npm_installed():
        raise RuntimeError("npm is not installed or not in your PATH. Please install Node.js and npm.")
    
    pkg_id = f"{name}@{version}" if version else name
    try:
        # Use shell=True on Windows
        if debug:
            print(f"Running npm pack for {pkg_id} in directory {dest}")
            
        if sys.platform == 'win32':
            cmd = f'npm pack {pkg_id}'
            if debug:
                print(f"Command: {cmd}")
            result = subprocess.run(cmd, 
                                   cwd=str(dest), 
                                   capture_output=True, 
                                   text=True, 
                                   shell=True)
        else:
            cmd = ['npm', 'pack', pkg_id]
            if debug:
                print(f"Command: {cmd}")
            result = subprocess.run(cmd, 
                                   cwd=dest, 
                                   capture_output=True, 
                                   text=True)
        
        if debug:
            print(f"Command stdout: {result.stdout}")
            print(f"Command stderr: {result.stderr}")
            print(f"Return code: {result.returncode}")
        
        if result.returncode != 0:
            raise RuntimeError(f"npm pack failed: {result.stderr}")
        
        # Parse the output to find the tarball name
        tarball = result.stdout.strip().splitlines()[-1]
        if debug:
            print(f"Tarball name: {tarball}")
            
        tar_path = dest / tarball
        
        # List directory to confirm tarball was created
        if debug:
            print(f"Directory contents of {dest}:")
            for file in dest.iterdir():
                print(f"  {file}")
        
        # Make sure the tarball was actually created
        if not tar_path.exists():
            raise RuntimeError(f"npm pack did not create expected tarball: {tar_path}")
        
        if debug:
            print(f"Extracting {tar_path} to {dest / 'package'}")
            
        extract_dir = dest / 'package'
        with tarfile.open(tar_path, 'r:gz') as tf:
            tf.extractall(path=extract_dir)
        
        if debug:
            print(f"Extracted contents:")
            for file in extract_dir.iterdir():
                print(f"  {file}")
        
        return extract_dir
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        raise RuntimeError(f"Error downloading npm package: {e}")

def download_deb_source(name: str, version: str, qualifiers: dict, dest: Path, debug=False) -> Path:
    """
    Use `apt-get source` to fetch and extract the Debian/Ubuntu source package.
    Requires apt sources list to include source entries.
    Returns the path to the extracted directory.
    """
    if sys.platform == 'win32':
        raise RuntimeError("Debian package download is not supported on Windows. This feature requires apt-get on Linux.")
    
    # Ensure apt-get source entries are enabled
    subprocess.run(['apt-get', 'update'], check=True, cwd=dest)
    pkg_spec = f"{name}={version}" if version else name
    result = subprocess.run(['apt-get', 'source', pkg_spec], cwd=dest, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"apt-get source failed: {result.stderr}")
    # Look for extracted directory
    for entry in dest.iterdir():
        if entry.is_dir() and entry.name.startswith(f"{name}-"):
            return entry
    raise RuntimeError(f"Extracted source directory not found for {name}")

class SmartCompliantSelector:
    def __init__(self, target_size=5000, debug=False):
        self.target_size = target_size
        self.debug = debug
        self.selected_files = []
        self.total_size = 0
        self.exclusion_reasons = defaultdict(int)
        
    def score_file(self, file_path, relative_path):
        """Score a file based on importance for vulnerability detection"""
        score = 0
        
        # Check filename for security-relevant keywords
        filename_lower = file_path.name.lower()
        for keyword, points in FILE_PRIORITIES.items():
            if keyword in filename_lower:
                score += points
                
        # Boost score for files in security-related directories
        path_lower = str(relative_path).lower()
        if any(folder in path_lower for folder in ['auth', 'security', 'crypto', 'session', 'api']):
            score += 50
        
        # Penalize files in test directories (less relevant for vulnerability analysis)
        if any(folder in path_lower for folder in ['test', '__test__', 'spec', 'fixtures', 'mocks']):
            score -= 30
        
        # Penalize deeply nested files (often less important)
        nested_penalty = len(relative_path.parts) - 3  # Files > 3 levels deep get penalized
        if nested_penalty > 0:
            score -= nested_penalty * 10
        
        return max(0, score)  # Don't allow negative scores
    
    def select_files(self, repo_dir):
        """Select the most important files that fit within target size"""
        candidates = []
        
        # First pass: find and score all eligible files
        for root, dirs, files in os.walk(repo_dir):
            # COMPLIANCE: Skip hidden directories (starting with .)
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            
            for filename in files:
                file_path = Path(root) / filename
                relative_path = file_path.relative_to(repo_dir)
                
                # COMPLIANCE: Skip hidden files or paths with hidden folders
                if any(part.startswith(".") for part in relative_path.parts):
                    self.exclusion_reasons["dot_path"] += 1
                    continue
                
                # COMPLIANCE: Skip blocklisted extensions
                if file_path.suffix.lower() in BLOCKLISTED_EXTENSIONS:
                    self.exclusion_reasons["blocklisted_extension"] += 1
                    continue
                
                try:
                    # COMPLIANCE: Check MIME type
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if not mime_type or not mime_type.startswith("text/"):
                        # Check for common code extensions that might not have text MIME type
                        valid_extensions = {'.js', '.ts', '.py', '.java', '.rb', '.c', '.cpp', '.h', '.php'}
                        if file_path.suffix.lower() not in valid_extensions:
                            self.exclusion_reasons["not_text_mime"] += 1
                            continue
                    
                    # Read file content
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # COMPLIANCE: Check file size in characters
                    if len(content) > MAX_FILE_SIZE:
                        self.exclusion_reasons["too_large"] += 1
                        continue
                    
                    # File passes all filters - score it
                    score = self.score_file(file_path, relative_path)
                    
                    candidates.append({
                        'path': file_path,
                        'relative_path': relative_path,
                        'content': content,
                        'size': len(content),
                        'score': score
                    })
                    
                except Exception as e:
                    self.exclusion_reasons["read_error"] += 1
                    if self.debug:
                        print(f"Error reading {relative_path}: {e}")
                    continue
        
        # Sort by score (descending)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Second pass: select files that fit within target size
        selected = []
        current_size = 0
        
        for candidate in candidates:
            # Include file if it fits within target
            if current_size + candidate['size'] <= self.target_size:
                selected.append(candidate)
                current_size += candidate['size']
                
                if self.debug:
                    print(f"Selected: {candidate['relative_path']} (score: {candidate['score']}, size: {candidate['size']})")
            else:
                if self.debug:
                    print(f"Skipped: {candidate['relative_path']} (would exceed target size)")
        
        return selected
    
    def generate_concatenated_string(self, selected_files):
        """Generate the final concatenated string"""
        result = []
        
        # Add file contents
        for file in selected_files:
            result.append(f"// FILE: {file['relative_path']}")
            result.append(file['content'])
            result.append("")  # Empty line between files
        
        return "\n".join(result)

def main():
    parser = argparse.ArgumentParser(description="Smart selective file concatenation for LLM prompts")
    parser.add_argument('--package', required=True, help='Package name')
    parser.add_argument('--json', default='minimal_version_sets.json', help='Path to JSON file')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--target-size', type=int, default=5000, help='Target output size in characters')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Load package info
    try:
        with open(args.json) as f:
            version_data = json.load(f)
    except Exception as e:
        print(f"Error reading {args.json}: {e}")
        return

    if args.package not in version_data:
        print(f"Error: package '{args.package}' not found in {args.json}")
        return
        
    entry = version_data[args.package]
    purl = entry.get('purl')
    if not purl:
        print(f"Error: no purl for package '{args.package}'")
        return

    info = parse_purl(purl)
    
    # Download package
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if info['type'] == 'npm':
                extract_dir = download_npm_package(info['name'], info['version'], Path(tmpdir), args.debug)
            elif info['type'] == 'deb':
                extract_dir = download_deb_source(info['name'], info['version'], info['qualifiers'], Path(tmpdir), args.debug)
            else:
                print(f"Error: ecosystem '{info['type']}' not supported yet.")
                return
            
            # Select and concatenate files
            selector = SmartCompliantSelector(target_size=args.target_size, debug=args.debug)
            selected_files = selector.select_files(extract_dir)
            result = selector.generate_concatenated_string(selected_files)
            
            # Output result
            if args.output:
                Path(args.output).write_text(result)
                print(f"Smart concatenation complete. Output written to {args.output}")
                print(f"Selected {len(selected_files)} files, total size: {len(result)} characters")
                
                if args.debug:
                    print("\nExclusion reasons:")
                    for reason, count in selector.exclusion_reasons.items():
                        print(f"  {reason}: {count} files")
            else:
                print(result)
                
    except Exception as e:
        print(f"Error processing package: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()