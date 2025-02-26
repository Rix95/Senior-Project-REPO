# Senior-Project-TAMUSA
Senior Project TAMUSA

# Dockerized Vulnerability Detection Tool

This repository contains a Python backend (with Neo4j integration) and a Vue/Vite frontend. The following instructions describe how to build and run both services using Docker Compose.

---

## Prerequisites

- **Docker**: Install [Docker](https://docs.docker.com/get-docker/).
- **Docker Compose**: Comes bundled with Docker Desktop on Windows/Mac. On Linux, install separately if needed.

---


**Key Files:**

- **docker-compose.yml**: Defines the `backend` and `frontend` services.
- **.env**: Contains environment variables like `NEO4J_IP`, `NEO4J_USER`, `NEO4J_PASS`.
- **src/backend/Dockerfile**: Builds the Python backend image.
- **src/frontend/Dockerfile**: Builds the Vue (Vite) frontend image.

---

## Environment Variables

Create a `.env` file in the project root with your Neo4j credentials:

```env
NEO4J_IP=your.neo4j.external.ip
NEO4J_USER=neo4j
NEO4J_PASS=your_password
```
---

# Running the Containers

## 1. Clone this Repository
If you haven’t already, clone this repository.  

## 2. Navigate to the Project Root
Ensure you are in the directory where `docker-compose.yml` is located.  

## 3. Build and Start the Containers
Run the following command:  

```bash
docker-compose up --build
```
## This Will
- Build the **Python backend** image.  
- Build the **Vue (Vite) frontend** image.  
- Start both containers on a Docker network (`app-network`).  

---

## 4. Check Logs
- The backend runs `neo4j_connection.py`, which prints **"Connection Successful!"** upon successfully connecting to Neo4j, then exits.  
- The frontend starts a **Vite dev server** at [http://localhost:5173](http://localhost:5173).

---

## 5. Access the Frontend
Open your browser and go to:  
🔗 [http://localhost:5173](http://localhost:5173)

---

## Notes on the Backend

### ✅ Current Behavior
- The backend script (`neo4j_connection.py`) **verifies connectivity** to Neo4j and then **exits** with code `0`.  
- This is fine for **testing** but not suitable for a **long-running API**.

---

### 🔄 Future Implementation
To keep the backend running persistently (e.g., as an API), consider:

1. **Replacing** `neo4j_connection.py` with a **web framework** such as **Flask** or **FastAPI**.  
2. **Changing** the `CMD` in `src/backend/Dockerfile` to run your server:

#### Example (Flask)
```dockerfile
CMD ["python", "app.py"]
```
## Example (FastAPI with Uvicorn)
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```
## Neo4j Configuration
- We are referencing an **external Neo4j instance** (e.g., on GCP).  
- Ensure your **firewall rules** allow inbound traffic on **port 7687**.  
- The `.env` file should have the correct **`NEO4J_IP`**.  

---

## Additional Tips

### ⚡ Live Reloading (Frontend)
- The frontend is mapped to **port 5173**.  
- If you want live reloading, make sure you haven’t overridden `/app` with a volume that omits `node_modules`.  

### 📁 Docker Volumes (For Local Development)
- If you want **immediate code changes**, you can **uncomment** the volume mappings in `docker-compose.yml` under the frontend service.  
- However, be mindful of handling `node_modules`.  

---

# Git Hook Setup
To enforce commit message conventions, run the following command after cloning the repository:

```bash
./setup-hooks.sh
