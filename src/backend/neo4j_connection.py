from neo4j import GraphDatabase  # Import the Neo4j driver to interact with the database

# URI and authentication details for connecting to the Neo4j database
URI = "bolt://localhost:7687"  # The connection URI (Bolt protocol, commonly used for local Neo4j connections)
AUTH = ("neo4j", "password")  # The authentication details (username and password) to access Neo4j

def get_neo4j_driver():
    try:
        # Create the Neo4j driver instance, which handles the connection to the database
        driver = GraphDatabase.driver(URI, auth=AUTH)
        
        # Verify the connectivity to the Neo4j instance
        driver.verify_connectivity()  # This checks if the driver can connect to Neo4j
        print("Connection Successful!")  # Print a success message if the connection is verified
        
        return driver  # Return the Neo4j driver instance for further use in interacting with the database
    
    except Exception as e:
        # If any exception occurs (such as failure to connect), print an error message with the exception details
        print(f"Error connecting to Neo4j: {e}")
        return None  # Return None if the connection failed