from dotenv import load_dotenv
import logging
import os
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Read environment variables
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Debug logging for credentials
logger.info(f"NEO4J_URI: {NEO4J_URI}")
logger.info(f"NEO4J_USERNAME: {NEO4J_USERNAME}")
logger.info(f"NEO4J_PASSWORD: {'*' * len(NEO4J_PASSWORD) if NEO4J_PASSWORD else 'NOT SET'}")

# Ensure variables are loaded correctly
if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    logger.error("Missing Neo4j credentials in .env file")
    raise ValueError("Missing Neo4j credentials in .env file")

# Optional: Additional network debugging

# try:
#         # Extract host and port from URI
#     from urllib.parse import urlparse
#     parsed_uri = urlparse(NEO4J_URI)
#     host = parsed_uri.hostname
#     port = parsed_uri.port or 7687

#     logger.info(f"Attempting to connect to {host}:{port}")
    
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.settimeout(5)  # 5 second timeout
#     result = sock.connect_ex((host, port))

#     if result == 0:
#         logger.info(f"Successfully connected to {host}:{port}")
   
#     else:
#         logger.error(f"Failed to connect to {host}:{port}. Error code: {result}")
# except Exception as e:
#     logger.error(f"Connection check error: {e}")

