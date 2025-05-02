import os, logging
from osv.vulnerability_repo_mapper import VulnerabilityRepoMapper
from version_builder.builder       import VersionBuilder

log = logging.getLogger(__name__)

def run(batch_size: int = 10_000, repo_name: str = "OSV") -> str:
    """
    End-to-end job:
    1. export package→CVE json
    2. compute minimal hitting sets
    3. build linguist + revision metadata
    Returns the path of the minimal-set JSON we just created.
    """
    mapper = VulnerabilityRepoMapper(batch_size=batch_size)
    try:
        if not mapper.connect():
            raise RuntimeError("Neo4j connection failed")

        json_pkg = mapper.export_to_json_streaming()
        mapper.build_minimal_hitting_sets_per_package(input_file=json_pkg,
                                                      repo_name=repo_name)

        min_sets_file = mapper.minimal_sets_last
        log.info("🟢 minimal-set file: %s", min_sets_file)

        vb = VersionBuilder(min_sets_file, workers=os.cpu_count() or 4)
        vb.run()
        return min_sets_file

    finally:
        mapper.close()
