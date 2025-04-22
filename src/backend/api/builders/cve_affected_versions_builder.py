import os
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from git import Repo, GitCommandError
from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

# ---------------------------------------------------------------------------
# CVE‑Affected Versions Builder
# ---------------------------------------------------------------------------
#  1.  Groups CVEs by Git repository (using the Package.purl or repo_url).
#  2.  Extracts the explicit list of affected versions per CVE from Neo4j.
#  3.  Iterates over every version tag in every repository, checks out the tag
#      with ``git switch <tag>``, and runs GitHub Linguist to capture the total
#      number of bytes and detailed language breakdown for that snapshot.
#  4.  Persists the language snapshot back to Neo4j and attaches the
#      (Vulnerability)‑[:AFFECTS_VERSION]->(Version) edges so that downstream
#      evaluations can be filtered by language or repo size.
#  5.  Designed to be invoked after *any* vulnerability‑loading ETL finishes
#      (see FastAPI /update_osv_vulnerabilities endpoint or APScheduler job).
# ---------------------------------------------------------------------------


class CVEAffectedVersionsBuilder:
    """Compute repo‑language snapshots for every <repo,version> pair referenced
    by the CVE data already stored in Neo4j.
    """

    def __init__(self, work_dir: str = "/tmp/builder", linguist_cmd: str = "github-linguist"):
        self.work_dir = Path(work_dir)
        self.linguist_cmd = linguist_cmd
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public orchestrator
    # ------------------------------------------------------------------
    def run(self) -> None:
        repos = self._fetch_repos_and_versions()
        for repo_url, data in repos.items():
            try:
                self._process_repo(repo_url, data)
            except Exception as exc:
                print(f"[Builder] ⚠️  Skipped {repo_url}: {exc}")

    # ------------------------------------------------------------------
    # Step 1 – Retrieve mapping {repo_url: {version_tag: [cve_ids...]}}
    # ------------------------------------------------------------------
    def _fetch_repos_and_versions(self) -> Dict[str, Dict[str, List[str]]]:
        query = """
        MATCH (v:Vulnerability)-[:AFFECTS]->(p:Package)
        WHERE size(p.versions) > 0 AND p.purl IS NOT NULL
        WITH v.id AS cve, p.purl AS purl, p.versions AS vers
        UNWIND vers AS ver
        WITH cve, purl, ver
        RETURN purl AS repo_url, collect(DISTINCT {ver: ver, cve: cve}) AS tuples
        """
        mapping: Dict[str, Dict[str, List[str]]] = {}
        with self.driver.session() as session:
            for rec in session.run(query):
                repo_url = rec["repo_url"]
                tuples = rec["tuples"]  # list of {ver, cve}
                for t in tuples:
                    ver = t["ver"]
                    cve = t["cve"]
                    mapping.setdefault(repo_url, {}).setdefault(ver, []).append(cve)
        print(f"[Builder] Collected {len(mapping)} distinct repositories from Neo4j")
        return mapping

    # ------------------------------------------------------------------
    # Step 2 – Clone / update repo locally; checkout tags; run Linguist.
    # ------------------------------------------------------------------
    def _process_repo(self, repo_url: str, version_map: Dict[str, List[str]]):
        repo_path = self.work_dir / self._repo_dirname(repo_url)
        repo = self._ensure_repo(repo_url, repo_path)

        for tag, cves in version_map.items():
            if not self._needs_analysis(repo_url, tag):
                continue  # snapshot already exists in Neo4j

            try:
                repo.git.switch("--detach", tag)
            except GitCommandError:
                print(f"[Builder] Tag {tag} not found in {repo_url}; skipping")
                continue

            lang_stats = self._run_linguist(repo_path)
            self._upsert_version_snapshot(repo_url, tag, lang_stats, cves, repo)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _repo_dirname(repo_url: str) -> str:
        return repo_url.rstrip("/").split("/")[-1].replace(".git", "")

    def _ensure_repo(self, repo_url: str, repo_path: Path) -> Repo:
        if repo_path.exists():
            repo = Repo(repo_path)
            repo.git.fetch("--tags", "--force")
        else:
            print(f"[Builder] Cloning {repo_url} → {repo_path}")
            repo = Repo.clone_from(repo_url, repo_path, multi_options=["--mirror"])
            # For linguist we need a working tree – convert mirror to bare clone
            shutil.rmtree(repo_path)
            repo = Repo.clone_from(repo_url, repo_path)
        return repo

    def _run_linguist(self, repo_path: Path) -> Dict[str, int]:
        """Returns {language: bytes} plus total_size key."""
        try:
            output = subprocess.check_output([
                self.linguist_cmd,
                "--breakdown",
                "--json",
                str(repo_path)
            ], text=True)
            raw = json.loads(output)
            langs = {k: v for k, v in raw["languages"].items()}
            langs["total_size"] = raw["size"]
            return langs
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Linguist failed: {exc}")

    # ------------------------------------------------------------------
    # Neo4j persistence helpers
    # ------------------------------------------------------------------
    def _needs_analysis(self, repo_url: str, tag: str) -> bool:
        query = """
        MATCH (r:CodeRepo {url: $url})-[:HAS_VERSION]->(v:Version {tag: $tag})
        RETURN v.tag LIMIT 1
        """
        with self.driver.session() as session:
            record = session.run(query, url=repo_url, tag=tag).single()
            return record is None

    def _upsert_version_snapshot(
        self,
        repo_url: str,
        tag: str,
        lang_stats: Dict[str, int],
        cves: List[str],
        repo: Repo,
    ) -> None:
        commit_hash = repo.head.commit.hexsha
        timestamp = datetime.utcnow().isoformat()
        query = """
        MERGE (r:CodeRepo {url: $url})
        ON CREATE SET r.created = $now
        MERGE (v:Version {tag: $tag, commit: $commit})
        SET v.size_bytes = $size,
            v.languages = $langs,
            v.last_scanned = $now
        MERGE (r)-[:HAS_VERSION]->(v)
        WITH v
        UNWIND $cves AS cve_id
        MATCH (vuln:Vulnerability {id: cve_id})
        MERGE (vuln)-[:AFFECTS_VERSION]->(v)
        """
        params = {
            "url": repo_url,
            "tag": tag,
            "commit": commit_hash,
            "size": lang_stats.pop("total_size"),
            "langs": lang_stats,
            "now": timestamp,
            "cves": cves,
        }
        with self.driver.session() as session:
            session.run(query, params)
        print(f"[Builder]  · Persisted {repo_url}@{tag} (languages={len(lang_stats)})")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self):
        self.driver.close()


# ---------------------------------------------------------------------------
# Entry‑point utility (so we can `python -m cve_affected_versions_builder`)
# ---------------------------------------------------------------------------

def main():
    builder = CVEAffectedVersionsBuilder()
    try:
        builder.run()
    finally:
        builder.close()


if __name__ == "__main__":
    main()
