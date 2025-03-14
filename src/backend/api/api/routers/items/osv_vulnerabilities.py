from fastapi import APIRouter, HTTPException, Query
from api.models.vulnerability import Vulnerability
from api.drivers.neo4j_driver import driver 
from api.osv.download_ecosystem_data import download_and_extract_all_ecosystems
#from osv.fetch_osv_ids import 
router = APIRouter()

@router.post("/")
def update_osv_vulnerabilities():
    try:
        #1 download vulnerabilities 
            download_and_extract_all_ecosystems()
        # Further steps (e.g., processing and loading into Neo4j) should be invoked here
            return {"message": "OSV vulnerabilities update initiated"}  
        #2 move to id
        #3 load vulnerabilities
        #query = """
        #QUERY TBDsu
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))