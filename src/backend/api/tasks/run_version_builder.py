"""
Run VersionBuilder once on the fixed JSON that lives in /app/backup/.

Usage (inside the FastAPI container)
$ python -m src.backend.api.tasks.run_version_builder
"""
import os, time, logging, multiprocessing as mp
from pathlib import Path
from version_builder.builder import VersionBuilder

# ❶ absolute path *inside* the container
JSON_FILE = Path("/app/backup/package_minimal_sets_OSV_20250503_194452.json")

def run_once() -> None:
    if not JSON_FILE.exists():
        raise FileNotFoundError(f"expected JSON not found → {JSON_FILE}")

    workers = mp.cpu_count() or 4
    log = logging.getLogger(__name__)
    log.info("▶️  VersionBuilder starting on %s with %d workers", JSON_FILE.name, workers)

    start = time.time()
    vb = VersionBuilder(JSON_FILE, workers=workers)
    vb.run()
    log.info("✅ VersionBuilder finished in %.1fs", time.time() - start)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    run_once()
