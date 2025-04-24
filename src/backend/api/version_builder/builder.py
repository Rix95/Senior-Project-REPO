import json, os, subprocess, shutil, tempfile, logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from git import Repo, InvalidGitRepositoryError, GitCommandError
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

log = logging.getLogger(__name__)
LINGUIST_CMD = os.getenv("LINGUIST_CMD", "github-linguist")
WORKDIR      = Path("/tmp/repocache")      # container local clone cache
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
            repo_url = self._guess_repo_url(p, pdata["ecosystem"])
            if not repo_url:
                log.warning("Could not infer VCS location for %s – skipped", p)
                continue
            for v in pdata["minimal_versions"]:
                tasks.append({
                    "package": p,
                    "repo_name": repo_url.split("/")[-1].removesuffix(".git"),
                    "url": repo_url,
                    "version": v
                })
        log.info("Prepared %d clone/analysis tasks", len(tasks))
        return tasks

    # naive heuristics – adjust / extend per ecosystem ------------------------
    def _guess_repo_url(self, package: str, ecosystem: str) -> str | None:
        if ecosystem.lower() in {"pypi", "python", "crates.io", "npm", "packagist"}:
            # try GitHub owner/repo style if slash present
            if "/" in package:
                return f"https://github.com/{package}.git"
        if ecosystem.lower() == "go":
            return f"https://{package}.git"      # go modules already full path
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
                    log.error("Task %s failed: %s", t, e)

    # individual task ---------------------------------------------------------
    def _handle_task(self, t: Dict):
        repo_path = WORKDIR / t["repo_name"]
        # 1. clone or fetch
        repo = self._ensure_repo(repo_path, t["url"])
        # 2. checkout
        commit = self._checkout(repo, t["version"])
        # 3. linguist
        lg_data = self._run_linguist(repo_path)
        # 4. push to Neo4j
        self._write_neo4j(t["repo_name"], t["package"], t["version"], commit, lg_data)

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
    def _write_neo4j(self, repo_name: str, package: str, version: str,
                     commit: str, lg: Dict):
        full_id = f"{repo_name}|{version}"
        languages = [{
            "uid": f"{k}|{v['bytes']}",
            "language": k, 
            "bytes": v["bytes"], 
            "percent": v["percent"]
            } for k, v in lg.items()]
        size_bytes = sum(v["bytes"] for v in lg.values())

        cypher = """
        MERGE (repo:CodeRepo {name:$repo, url:$url})
        MERGE (rev:Revision {full_id:$fid})
              ON CREATE SET rev.version=$version,
                            rev.commit=$commit,
                            rev.size_bytes=$size
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
            sess.run(cypher, repo=repo_name, url=f"https://github.com/{repo_name}",
                     fid=full_id, version=version, commit=commit,
                     size=size_bytes, langs=languages, package=package)
