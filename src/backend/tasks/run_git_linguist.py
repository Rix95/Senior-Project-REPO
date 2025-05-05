# src/backend/api/tasks/run_git_linguist.py

import json, os
from pathlib import Path
from packageurl import PackageURL
from git_integration import git_switch_revision, get_github_linguist_metadata
import requests
from urllib.parse import quote

print("🟢 run_git_linguist.py starting…", flush=True)

IN_JSON  = Path(__file__).parent.parent / "backup" / "package_minimal_sets_OSV_20250503_194452.json"
OUT_JSON = Path(__file__).parent.parent / "backup" / "revision_metadata.json"

def _normalize_git_url(raw_url: str) -> str | None:
    """
    Turn things like
      git+https://github.com/foo/bar.git
      git+ssh://git@github.com/foo/bar.git
      git@github.com:foo/bar.git
    into
      https://github.com/foo/bar.git
    """
    if not raw_url:
        return None

    # strip any leading "git+"
    url = raw_url.removeprefix("git+")

    # git@github.com:owner/repo.git  →  https://github.com/owner/repo.git
    if url.startswith("git@"):
        host, path = url[len("git@"):].split(":", 1)
        return f"https://{host}/{path}"

    # ssh://git@github.com/owner/repo.git  →  https://github.com/owner/repo.git
    if url.startswith("ssh://git@"):
        rest = url[len("ssh://git@"):]
        return f"https://{rest}"

    # git://github.com/foo/bar.git  →  https://github.com/foo/bar.git
    if url.startswith("git://"):
        rest = url[len("git://"):]
        return f"https://{rest}"

    # already http[s]?
    if url.startswith("http://") or url.startswith("https://"):
        # ensure .git on the end
        if not url.endswith(".git"):
            url = url.rstrip("/") + ".git"
        return url

    return None

def _npm_repo_url(purl: PackageURL) -> str | None:
    name = f"{purl.namespace}/{purl.name}" if purl.namespace else purl.name
    encoded = quote(name, safe='')
    try:
        r = requests.get(f"https://registry.npmjs.org/{encoded}", timeout=10)
        r.raise_for_status()
        repo = r.json().get("repository") or {}
        url = repo.get("url", "")
        return _normalize_git_url(url)
    except Exception:
        return None

def _pypi_repo_url(purl: PackageURL) -> str | None:
    try:
        r = requests.get(f"https://pypi.org/pypi/{purl.name}/json", timeout=10)
        r.raise_for_status()
        info = r.json().get("info", {})
        urls = info.get("project_urls") or {}
        raw = urls.get("Source") or urls.get("Homepage") or info.get("home_page", "")
        return _normalize_git_url(raw)
    except Exception:
        return None

def _git_url_from_purl_str(purl_str: str) -> str | None:
    try:
        purl = PackageURL.from_string(purl_str)
    except Exception:
        return None

    # GitHub / GitLab / Bitbucket
    if purl.type in {"github", "gitlab", "bitbucket"} and purl.namespace and purl.name:
        return f"https://{purl.type}.com/{purl.namespace}/{purl.name}.git"

    # npm
    if purl.type == "npm":
        return _npm_repo_url(purl)

    # PyPI
    if purl.type in {"pypi", "python"}:
        return _pypi_repo_url(purl)

    # composer → assume GitHub
    if purl.type == "composer" and purl.namespace and purl.name:
        return f"https://github.com/{purl.namespace}/{purl.name}.git"

    return None

def run_pure_json():
    raw = json.loads(IN_JSON.read_text())
    total = len(raw)
    print(f"ℹ️  Found {total} packages to process", flush=True)

    out = {}
    for idx, (pkg, info) in enumerate(raw.items(), start=1):
        # checkpoint every 100 packages (or at the very end)
        if idx % 100 == 0 or idx == total:
            print(f"   → processed {idx}/{total}: {pkg}", flush=True)

        purl_str = info.get("purl", "")
        git_url  = _git_url_from_purl_str(purl_str)
        if not git_url:
            out.setdefault(pkg, {})["_error"] = f"no git_url for purl '{purl_str}'"
            continue

        # ── only real version strings, skip any "pkg:…" entries ─────────
        versions = [
            v for v in info.get("minimal_versions", [])
            if not v.startswith("pkg:")
        ]

        for ver in versions:
            try:
                repo_path, tmp = git_switch_revision(git_url, ver)
                meta = get_github_linguist_metadata(repo_path)
                tmp.cleanup()
            except Exception as e:
                meta = {"error": str(e)}

            out.setdefault(pkg, {})[ver] = meta

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"✅ Wrote revision metadata → {OUT_JSON}", flush=True)

if __name__ == "__main__":
    run_pure_json()
