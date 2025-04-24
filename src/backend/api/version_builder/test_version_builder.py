from version_builder.builder import VersionBuilder
import json, os

def test_builder_single_repo(tmp_path):
    # minimal sample json with one repo+version
    data = {
        "pallets/flask": {
            "ecosystem":"Packagist",
            "minimal_versions":["2.2.5"]
        }
    }
    sample = tmp_path/"sample.json"
    sample.write_text(json.dumps(data))

    vb = VersionBuilder(str(sample), workers=1)
    vb.run()

    # quick Neo4j assertion
    with vb.driver.session() as s:
        rec = s.run("MATCH (:Revision {full_id:'flask|2.2.5'}) RETURN count(*) AS n").single()
        assert rec["n"] == 1
