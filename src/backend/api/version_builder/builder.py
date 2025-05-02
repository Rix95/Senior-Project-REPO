import json, os, subprocess, shutil, tempfile, logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from git import Repo, InvalidGitRepositoryError, GitCommandError
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from packageurl import PackageURL

log = logging.getLogger(__name__)
noisy_log = logging.getLogger(__name__ + ".repos")
noisy_log.propagate = False
noisy_log.setLevel(logging.WARNING)
logging.basicConfig(level=os.getenv("PYTHONLOGLEVEL", "INFO"))

LINGUIST_CMD = os.getenv("LINGUIST_CMD", "github-linguist")
WORKDIR = Path("/tmp/repocache")      # container local clone cache
WORKDIR.mkdir(parents=True, exist_ok=True)

class VersionBuilder:
    def __init__(self, json_path: str, workers: int = 4):
        self.json_path = Path(json_path)
        self.workers   = workers
        self.driver    = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    # ---------- public entry -------------------------------------------------
    def run(self) -> None:
        package_map = self._load_json()
        tasks = self._prepare_tasks(package_map)
        self._process_tasks(tasks)
        log.info("Revision pipeline finished — %d repos analysed, %d skipped",
                 sum(fut.done() and not fut.exception() for fut in futures),
                 sum(fut.done() and fut.exception()  for fut in futures))


    # ---------- helpers ------------------------------------------------------
    def _load_json(self) -> Dict:
        with open(self.json_path, "r") as fh:
            data = json.load(fh)
        log.info("Loaded %d packages from %s", len(data), self.json_path.name)
        return data                       # {package: {...minimal_versions...}}

    def _prepare_tasks(self, pkg_map: Dict) -> List[Dict]:
        """
        Turns the JSON into a flat list:
        [{
            repo_name: "pallets/flask",
            vcs_url:   "https://github.com/pallets/flask.git",
            version:   "v2.2.5",               # tag or commit
            package:   "flask"
        }, ...]
        """
        tasks = []
        for p, pdata in pkg_map.items():
            repo_url = (
                self._purl_to_git_url(pdata.get("purl"))
                or self._guess_repo_url(p, pdata["ecosystem"])
            )
            if not repo_url:
                log.warning("Could not infer VCS location for %s – skipped", p)
                continue
            # use .get() so we don't crash on missing key
            for v in pdata.get("minimal_versions", []):
                # skip garbage entries that are actually purls
                if isinstance(v, str) and v.startswith("pkg:"):
                    log.warning("Skip invalid version %s for %s", v, p)
                    continue
                tasks.append({
                    "package": p,
                    "repo_name": repo_url.split("/")[-1].removesuffix(".git"),
                    "url": repo_url,
                    "purl": pdata.get("purl", ""),
                    "version": v
                })
        log.info("Prepared %d clone/analysis tasks", len(tasks))
        return tasks

    def _purl_to_git_url(self, purl_str: str | None) -> str | None:
        """
        Convert a PackageURL to a cloneable Git URL when possible.
        Supports purl types: github, gitlab, bitbucket, pypi (github repo in qualifiers).
        """
        if not purl_str:
            return None
        try:
            purl = PackageURL.from_string(purl_str)
        except ValueError:
            return None
        
        # most ecosystems embed the VCS in qualifiers
        if purl.type in {"github", "gitlab", "bitbucket"}:
            return f"https://{purl.type}.com/{purl.namespace}/{purl.name}.git"
        # fallback – many PyPI / npm packages carry a 'repository_url' qualifier
        repo_q = purl.qualifiers.get("repository_url") if purl.qualifiers else None
        if repo_q and repo_q.startswith("http"):
            return repo_q.rstrip("/") + ".git" if not repo_q.endswith(".git") else repo_q
        
        return None

    def _guess_repo_url(self, package: str, ecosystem: str) -> str | None:
        eco = ecosystem.lower()

        # GitHub-style (pypi, npm, composer, …)
        if eco in {"pypi", "python", "crates.io", "npm", "packagist", "composer"}:
            if "/" in package:
                return f"https://github.com/{package}.git"

        # Go modules often use the import path directly
        if eco == "go" and "/" in package and "." in package.split("/")[0]:
            # e.g.  github.com/user/proj  →  https://github.com/user/proj.git
            return f"https://{package}.git"

        return None


    # main thread pool --------------------------------------------------------
    def _process_tasks(self, tasks: List[Dict]):
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._handle_task, t): t for t in tasks}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    noisy_log.warning("skip %s – %s", t["package"], e)


    # individual task ---------------------------------------------------------
    def _handle_task(self, t: Dict):
        repo_path = WORKDIR / t["repo_name"]
        # 1. clone or fetch
        try:
            repo = self._ensure_repo(repo_path, t["url"])
        except Exception as e:
            noisy_log.warning("clone failed for %s: %s", t["package"], e)
            return
        # 2. checkout
        commit = self._checkout(repo, t["version"])
        # 3. linguist
        lg_data = self._run_linguist(repo_path)
        # 4. push to Neo4j
        self._write_neo4j(
            repo_name=t["repo_name"],
            package=t["package"],
            version=t["version"],
            commit=commit,
            lg=lg_data,
            url=t["url"],
            purl=t.get("purl", "")
        )

    def _ensure_repo(self, path: Path, url: str) -> Repo:
        try:
            repo = Repo(path)
            repo.remote().fetch(tags=True, depth=1)
        except InvalidGitRepositoryError:
            repo = Repo.clone_from(url, path, depth=1, no_single_branch=True)
        return repo

    def _checkout(self, repo: Repo, version: str) -> str:
        try:                               # tag
            repo.git.checkout(version)
        except GitCommandError:
            repo.git.checkout(version, force=True)  # assume commit SHA
        return repo.head.commit.hexsha

    def _run_linguist(self, path: Path) -> Dict[str, int]:
        cmd = [LINGUIST_CMD, "--json", str(path)]
        out = subprocess.check_output(cmd, text=True)
        parsed = json.loads(out)
        total  = sum(parsed.values())
        return {lang: {"bytes": b, "percent": round(b/total*100,2)}
                for lang, b in parsed.items()}

    # ---------------- Neo4j write -------------------------------------------
    def _write_neo4j(self, *, repo_name: str, package: str, version: str,
                     commit: str, lg: Dict, url: str, purl: str):
        full_id = f"{repo_name}|{version}"
        languages = [{
            "uid": f"{k}|{v['bytes']}",
            "language": k, 
            "bytes": v["bytes"], 
            "percent": v["percent"]
            } for k, v in lg.items()]
        size_bytes = sum(v["bytes"] for v in lg.values())

        cypher = """
        MERGE (repo:CodeRepo {name:$repo})
        ON CREATE SET repo.url = $url,
                        repo.purl = $purl
        MERGE (rev:Revision {full_id:$fid})
        ON CREATE SET rev.version    = $version,
                        rev.commit     = $commit,
                        rev.size_bytes = $size
        MERGE (repo)-[:HAS_REVISION]->(rev)

        WITH rev
        UNWIND $langs AS l
        MERGE (lang:LanguageStat {uid:l.uid})
        ON CREATE SET lang.language = l.language,
                      lang.bytes    = l.bytes,
                      lang.percent  = l.percent
        MERGE (rev)-[:LANGUAGE_BREAKDOWN]->(lang)


        MATCH (p:Package {name:$package})
        MERGE (p)-[:MINIMALLY_AFFECTED_BY]->(rev)
        
        
        MATCH (v:Vulnerability)-[:AFFECTS]->(p)
        WHERE $version IN p.versions
        MERGE (v)-[:OBSERVED_IN]->(rev)
        """
        with self.driver.session() as sess:
            sess.run(
                cypher,
                repo=repo_name,
                url=url,
                purl=purl,
                fid=full_id,
                version=version,
                commit=commit,
                size=size_bytes,
                langs=languages,
                package=package,
            )
