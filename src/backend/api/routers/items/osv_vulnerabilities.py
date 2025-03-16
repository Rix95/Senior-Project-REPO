from fastapi import APIRouter, HTTPException, Query
from  models.vulnerability import Vulnerability
from drivers.neo4j_driver import driver 
from osv.download_ecosystem_data import download_and_extract_all_ecosystems
#from osv.fetch_osv_ids import 
router = APIRouter()

@router.post("/")
def update_osv_vulnerabilities():
    #1 download vulnerabilities
    download_and_extract_all_ecosystems()
    #2 move to id

    #3 load vulnerabilities
    #query = """
    #QUERY TBDsu
  