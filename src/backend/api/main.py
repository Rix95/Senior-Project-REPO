# from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from routers.items import vulnerabilities, vulnerabilities_repositories
# from neo4j import GraphDatabase
# import os
# from datetime import datetime
# from vulnerability_repository import repository_exists_in_neo4j, update_repository_in_neo4j, create_repository_in_neo4j, VulnerabilityRepository
# from neo4j_driver import Neo4jDriver


app = FastAPI()
app.include_router(vulnerabilities.router, prefix="/items/vulnerabilities", tags=["Vulnerabilities"])


@app.get("/")
def main():
    return "Hello from FastAPI!"



# @app.post("/update_repository/{repository_name}")
# def update_repository(repository_name):
#     #First create Vuln repo object instance
#         #check if it exists
#         #if not create it
#     return "Repo succesfuly created in neo4j"

# @app.post("/repositories/")
# def create_repository_in_neo4j(repo: VulnerabilityRepository):
#     """
#     Create a repository node in Neo4j.
    
#     Args:
#         repo (VulnerabilityRepository): Repository to create
    
#     Returns:
#         The created repository node or None if creation fails
#     """
#     try:
#         # Check if repository exists
#         if repository_exists_in_neo4j(repo):
#             # Update the repository if it exists
#             update_repository_in_neo4j(repo)
#             return {"message": "Repository updated", "repository": repo}
#         else:
              
#             with Neo4jDriver.get_driver().session() as session:

#                 # Cypher query to create a repository node
#                 query = """
#                 CREATE (r:VulnerabilityRepository {
#                     name: $name, 
#                     last_updated: $last_updated
#                 })
#                 RETURN r
#                 """
                
#                 # Prepare parameters
#                 params = {
#                     "name": repo.name,
#                     "last_updated": repo.last_updated.isoformat(),
                    
#                 }
                
#                 # Execute the query
#                 result = session.run(query, params)
                
#                 # Fetch the first (and only) record
#                 record = result.single()
                
#                 if record:
#                     print(f"Repository created: {record['r']}")
#                     return record['r']
#                 else:
#                     print("No repository node was created")
#                     return None
                
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/get_repositories/")
# async def get_all_vulnerability_repos():
#     """
#     Retrieves all nodes with the label VulnerabilityRepository from Neo4j.
#     """
#     try:
#         # Open a session using the Neo4jDriver method
#         with Neo4jDriver.get_driver().session() as session:
#             # Cypher query to match all nodes labeled VulnerabilityRepository
#             query = "MATCH (r:VulnerabilityRepository) RETURN r"
#             result = session.run(query)
            
#             # Convert each node to a more comprehensive dictionary
#             vulnerability_repos = []
#             for record in result:
#                 node = record["r"]
#                 # Convert node to a dictionary and add element_id
#                 repo_dict = dict(node)
#                 repo_dict['element_id'] = node.element_id
                
#                 vulnerability_repos.append(repo_dict)
            
#             return {
#                 "count": len(vulnerability_repos),
#                 "vulnerability_repos": vulnerability_repos
#             }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("add_vulnerability")
# def add_vulnerability(vulnerability, repository: str=None):
#     return None

# @app.get("get_vulnerability")
# def get_vulnerability(vulnerability):
#     return None

# @app.get("get_total_vulnerabilities")
# def get_vulnerability(repository: str="all"): #default behavior should retrieve total number of all repositories in all repos.
#     return None

if __name__ == "__main__":
    main()
