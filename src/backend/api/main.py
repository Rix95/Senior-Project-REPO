from routers.items.osv_vulnerabilities import (
    router as osv_vulnerabilities_router,
)
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from osv.download_ecosystem_data import download_and_extract_all_ecosystems
from osv.fetch_osv_ids import extract_vulnerability_ids
from osv.osv_vuln_neo4j_loader import main as load_osv
from osv.neo4j_connection import get_neo4j_driver
from apscheduler.schedulers.background import BackgroundScheduler
from routers.items.vulnerability_timeline import router as timeline_router
from osv.vulnerability_repo_mapper import VulnerabilityRepoMapper
from version_builder.builder import VersionBuilder  
from osv.vulnerability_repo_mapper import main as repo_mapper
from typing import List
from fastapi import BackgroundTasks
from tasks.revision_pipeline import run as run_revision_pipeline    # ← new import


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vue.js frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.include_router(osv_vulnerabilities_router, prefix="/items/osv_vulnerabilities", tags=["OSV_Vulnerabilities"])
app.include_router(timeline_router, prefix="/items", tags=["vulnerability_timeline"])

@app.get("/")
def main():
    return "Hello from FastAPI!"

@app.post("/update_osv_vulnerabilities")
async def update_osv_vulnerabilities():
    """
    1.  Raw OSV → Neo4j
    2.  Export package-centric JSON
    3.  Build minimal hitting sets (same JSON)
    4.  Feed that JSON into VersionBuilder
    """
    # ── step-1 ────────────────────────────────────────────────────────────
    download_and_extract_all_ecosystems()
    extract_vulnerability_ids()
    await load_osv()                       # populates Neo4j raw data

    mapper = VulnerabilityRepoMapper()
    try:
        if not mapper.connect():
            raise RuntimeError("Neo4j unavailable")

        # ── step-2: create JSON snapshot of package ↔ versions ───────────
        mapper.export_to_json_streaming()             # sets package_cve_versions_last
        json_path = mapper.package_cve_versions_last

        # ── step-3: compute minimal hitting sets per package ──────────────
        mapper.build_minimal_hitting_sets_per_package(
            input_file=json_path,
            repo_name="OSV"
        )

    finally:
        mapper.close()

    # ── step-4: build repo / revision metadata via Git + Linguist ─────────
    try:
        vb = VersionBuilder(json_path, workers=4)
        vb.run()
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"VersionBuilder failed: {e}")

    return {"message": "OSV vulnerabilities & revision metadata updated"}


@app.post("/map_vulnerabilities")
async def map_vulnerabilities():
    repo_mapper()
    
    return {"message": "map returned"}

# Add a new endpoint to manually trigger the minimal hitting set computation
@app.post("/compute_minimal_hitting_sets")
async def compute_minimal_hitting_sets():
    mapper = VulnerabilityRepoMapper()
    try:
        if mapper.connect():
            result = mapper.build_minimal_hitting_sets_per_package("OSV")
            return result
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to Neo4j database")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        mapper.close()
        
@app.post("/build_revision_metadata", tags=["maintenance"])
async def build_revision_metadata(background_tasks: BackgroundTasks):
    """
    Triggers the full package→CVE → minimal-set → VersionBuilder pipeline.
    Runs in the background so the request returns immediately.
    """
    background_tasks.add_task(run_revision_pipeline)
    return {"status": "started", "detail": "Revision-metadata pipeline running in background"}


# Run script every week
scheduler = BackgroundScheduler()
scheduler.add_job(update_osv_vulnerabilities, "interval", weeks=1)
scheduler.start()

# Refactor eventually!
# Query function to count Vulnerability nodes
def count_vulnerability_nodes(driver):
    with driver.session() as session:
        result = session.run("MATCH (v:Vulnerability) RETURN count(v) AS total")
        return result.single()["total"]

# FastAPI endpoint to get vulnerability count
@app.get("/count_vulnerabilities")
async def get_vulnerability_count(driver=Depends(get_neo4j_driver)):
    total = count_vulnerability_nodes(driver)
    return {"total_vulnerabilities": total}


# Query function to get the last_updated property
def get_last_updated(driver):
    with driver.session() as session:
        result = session.run(
            "MATCH (repo:VULN_REPO {name: 'OSV'}) RETURN repo.last_updated AS last_updated"
        )
        record = result.single()
        return record["last_updated"] if record else None

# FastAPI endpoint to return last_updated
@app.get("/last_updated")
async def fetch_last_updated(driver=Depends(get_neo4j_driver)):
    last_updated = get_last_updated(driver)
    if last_updated is None:
        return {"error": "Repository not found"}
    return {"last_updated": last_updated}

###
# Query function to query packages by name
def search_packages_by_name(name: str, driver) -> List[dict]:
    query = """
    MATCH (p:Package)
    WHERE toLower(p.name) CONTAINS toLower($name)
    RETURN p.name AS packageName, p.ecosystem AS ecosystem
    ORDER BY packageName, ecosystem
    """
    with driver.session() as session:
        result = session.run(query, name=name)
        return [record.data() for record in result]

# FastAPI endpoint to get packages by name, this returns package and ecosystem.
@app.get("/search_by_name")
async def search_package_by_name(name: str = Query(..., description="Package name to search for"), driver=Depends(get_neo4j_driver)):
    results = search_packages_by_name(name, driver)
    return {"results": results}


###

# New endpoint to get the minimal versions for a repository
@app.get("/minimal_versions/{repo_name}")
async def get_minimal_versions(repo_name: str, driver=Depends(get_neo4j_driver)):
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (repo:VULN_REPO {name: $repo_name}) "
                "RETURN repo.minimal_versions AS minimal_versions, "
                "repo.minimal_versions_count AS count, "
                "repo.minimal_versions_updated AS updated",
                repo_name=repo_name
            )
            record = result.single()
            
            if not record or not record["minimal_versions"]:
                return {
                    "message": f"No minimal versions found for {repo_name}. Try running /compute_minimal_hitting_sets first."
                }
                
            return {
                "repository": repo_name,
                "minimal_versions": record["minimal_versions"],
                "count": record["count"],
                "last_updated": record["updated"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving minimal versions: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("FastAPI server starting with uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
