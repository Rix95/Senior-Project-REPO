from fastapi import APIRouter, HTTPException, Query
from  models.vulnerability import Vulnerability
from drivers.neo4j_driver import driver 

router = APIRouter()

@router.post("/", response_model=Vulnerability)
def create_vulnerability(vulnerability: Vulnerability):
    query = """
    QUERY TBDsu
    """
    result = driver.query(query, {"name": vuln.name, "severity": vuln.severity, "description": vuln.description})
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create vulnerability")
    return result[0]["v"]
    
# Get all vulnerabilities
@router.get("/", response_model=list[Vulnerability])
def get_vulnerabilities():
    query = "MATCH (v:Vulnerability) RETURN v"
    result = driver.query(query)
    return [record["v"] for record in result]

# Update a vulnerability by name/id
@router.put("/{vuln_name}", response_model=Vulnerability)
def update_vulnerability(vuln_name: str, vuln_data: Vulnerability):
    query = """
    """
    result = driver.query(query, {
        "vuln_name": vuln_name,
    })
    if not result:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return result[0]["v"]

# Get the total number of vulnerabilities
@router.get("/total", response_model=int)
def get_total_vulnerabilities(repository: str = Query(None)):
    if repository:
        query = """
        MATCH (:VulnerabilityRepository {name: $repository})-[:CONTAINS]->(v:Vulnerability)
        RETURN count(v) AS total
        """
        result = driver.query(query, {"repository": repository})
    else:
        query = "MATCH (v:Vulnerability) RETURN count(v) AS total"
        result = driver.query(query)

    return result[0]["total"] if result else 0