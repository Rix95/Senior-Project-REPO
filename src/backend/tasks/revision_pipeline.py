import logging
from .run_version_builder import run_once

log = logging.getLogger(__name__)

def run_revision_pipeline() -> str:
    """
    Read the precomputed minimal-sets JSON from /app/backup/,
    run VersionBuilder (linguist), and return the path of the output JSON.
    """
    log.info("Starting revision pipeline (background)...")
    out = run_once()
    log.info("Revision pipeline complete, output saved to %s", out)
    return out
