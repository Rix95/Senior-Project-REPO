"""
Run VersionBuilder once on the fixed JSON that lives in /app/backup/.

Usage (inside the FastAPI container)
$ python -m src.backend.api.tasks.run_version_builder
"""
import os
import time
import logging
import multiprocessing as mp
from pathlib import Path
from version_builder.builder import VersionBuilder

# absolute path *inside* the container
JSON_FILE = Path("/app/backup/package_minimal_sets_OSV_20250503_194452.json")

def run_once() -> str:
    if not JSON_FILE.exists():
        raise FileNotFoundError(f"expected JSON not found → {JSON_FILE}")

    workers = mp.cpu_count() or 4
    log = logging.getLogger(__name__)
    log.info("▶️ VersionBuilder starting on %s with %d workers", JSON_FILE.name, workers)

    start = time.time()
    # pass output_dir="/app/backup" so we only emit JSON, not Neo4j
    vb = VersionBuilder(
        json_path=JSON_FILE,
        workers=workers,
        output_dir=Path("/app/backup")
    )
    output_file = vb.run()
    log.info("✅ VersionBuilder finished in %.1fs, wrote %s", time.time() - start, output_file)
    return output_file

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    run_once()
