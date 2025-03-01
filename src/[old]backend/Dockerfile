FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file to install dependencies
COPY requirements.txt .

# Install the Python dependencies (no need for a virtual environment)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code into the container, including the ecosystem data scripts
COPY . /app

# Ensure that the 'ecosystem_data' folder will be created when running the backend scripts
RUN mkdir -p /app/ecosystem_data

# Expose the backend port (adjust as needed)
EXPOSE 5000

# Set the default command for the container to run the backend (adjust if needed) # Adjust this if you need a different entry point (e.g., parse_osv.py)
CMD ["python", "neo4j_connection.py"] 