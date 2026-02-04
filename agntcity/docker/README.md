# Project Setup and Docker Instructions

This project consists of five main components:
1. **FastAPI Exchange Server** (Backend)
2. **React Frontend** (UI)
3. **Brazil Farm Server** (Brazil Farm Agent Backend)
4. **Colombia Farm Server** (Colombia Farm Agent Backend)
5. **Vietnam Farm Server** (Vietnam Farm Agent Backend)

Both components are containerized using Docker for easy deployment.

---

## Prerequisites
- **Ensure you are in the root directory of the repository before running any commands.**
- Install [Docker](https://www.docker.com/) and ensure it is running.
- Install [Docker Compose](https://docs.docker.com/compose/) (optional, if using `docker-compose`).

---

## Docker Files
### Backend: `Dockerfile.exchange`
This Dockerfile sets up the FastAPI Exchange Server.

### Frontend: `Dockerfile.ui`
This Dockerfile sets up the React Frontend.

### Brazil Farm Server: `Dockerfile.brazil-farm`
This Dockerfile sets up the Brazil Farm Agent backend.

### Colombia Farm Server: `Dockerfile.colombia-farm`
This Dockerfile sets up the Brazil Farm Agent backend.

### Vietnam Farm Server: `Dockerfile.vietnam-farm`
This Dockerfile sets up the Vietnam Farm Agent backend.

---

## Build and Run Instructions

### 1. Backend (FastAPI Exchange Server)
#### Build the Docker Image
```bash
docker build -f coffeeAGNTCY/coffee_agents/corto/docker/Dockerfile.exchange -t exchange-server .
```

#### Run the Container
```bash
docker run -d -p 8000:8000 exchange-server
```

The backend will be accessible at `http://localhost:8000`.

---

### 2. Frontend (React UI)
#### Build the Docker Image
```bash
docker build -f coffeeAGNTCY/coffee_agents/corto/docker/Dockerfile.ui -t ui-server .
```

#### Run the Container
```bash
docker run -d -p 3000:3000 ui-server
```

The frontend will be accessible at `http://localhost:3000`.

---