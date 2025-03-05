from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD  # Import credentials

class Neo4jDriver:
    """Singleton class to manage a persistent Neo4j driver."""
    
    _driver = None

    @classmethod
    def get_driver(cls):
        """Returns a single instance of the Neo4j driver."""
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        return cls._driver

    @classmethod
    def close_driver(cls):
        """Closes the Neo4j driver connection."""
        if cls._driver:
            cls._driver.close()
            cls._driver = None



# Initialize the driver at module load (optional, for eager loading)
driver = Neo4jDriver.get_driver()

# Testing the driver:
if __name__ == "__main__":
    try:
        with driver.session() as session:
            print(NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME, "HEYHEYHEY")
            # Run a simple query to test the connection.
            result = session.run("RETURN 'Hello, Neo4j!' AS message")
            record = result.single()
            print("Query result:", record["message"])  # Expect to see 'Hello, Neo4j!'
        print("Driver test: Connection successful.")
    except Exception as e:
        print("Driver test: Error connecting to Neo4j:", e)
    finally:
        Neo4jDriver.close_driver()
