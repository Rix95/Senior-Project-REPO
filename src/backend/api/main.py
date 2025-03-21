# from dotenv import load_dotenv
from routers.items import router as osv_vulnerabilities_router
from fastapi import Depends, FastAPI, HTTPException
#from routers.items import vulnerabilities_repositories
from osv.download_ecosystem_data import download_and_extract_all_ecosystems
from osv.fetch_osv_ids import extract_vulnerability_ids
from osv.osv_vuln_neo4j_loader import main as load_osv
from osv.neo4j_connection import get_neo4j_driver

# from osv.download_ecosystem_data import  
# from neo4j import GraphDatabase
# import os
# from datetime import datetime
# from vulnerability_repository import repository_exists_in_neo4j, update_repository_in_neo4j, create_repository_in_neo4j, VulnerabilityRepository
# from neo4j_driver import Neo4jDriver


#download_and_extract_all_ecosystems()
#fetch_osv_ids()

app = FastAPI()
app.include_router(osv_vulnerabilities_router, prefix="/items/osv_vulnerabilities", tags=["OSV_Vulnerabilities"])


@app.get("/")
def main():
    return "Hello from FastAPI!"

@app.post("/update_osv_vulnerabilities")
async def update_osv_vulnerabilities():
    #1 download vulnerabilities
    download_and_extract_all_ecosystems()
    #2 move to id single file json
    extract_vulnerability_ids()
    #3 load vulnerabilities
    await load_osv()
    #query = """
    #QUERY TBDsu
    return {"message": "OSV vulnerabilities updated successfully"}


#Refactor eventually!
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

if __name__ == "__main__":
    import uvicorn
    print("FastAPI server starting with uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)