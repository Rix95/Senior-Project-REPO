from neo4j import GraphDatabase

# URI and authentication details
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password")

# Creating connection to Neo4j instance using the URI and authentication details
with GraphDatabase.driver(URI, auth=AUTH) as driver:
    # Checks if the connection is successful and the Neo4j instance is reachable
    driver.verify_connectivity()
    print("Connection Successful!")
    