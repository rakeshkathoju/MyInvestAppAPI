# Trading MyInvestAppAPI Project

This project demonstrates a microservices architecture for trading applications.  
It includes services written in Node.js, Java, and Python, along with an AI service.

## Project Structure

trading-microservices/  
│  
├── api-gateway-node/  
├── user-service-java/  
├── trading-service-python/  
├── ai-service-python/  
├── docker-compose.yml  
└── README.md  


Each folder represents a separate microservice or configuration file.

## Setup Instructions

To create the project folder and navigate into it, run the following commands:

```bash
cd Desktop
mkdir trading-microservices
cd trading-microservices  

mkdir api-gateway-node
mkdir user-service-java
mkdir trading-service-python
mkdir ai-service-python
```
## Now your folder looks like:

POSTGRES_DB_URL=postgresql://user:pass@host/db?sslmode=require

Desktop/  
└── trading-microservices/  
    ├── api-gateway-node/  
    ├── user-service-java/  
    ├── trading-service-python/  
    └── ai-service-python/  

## SETUP NODE API GATEWAY  
install Node and npm
```bash
cd api-gateway-node
npm init -y
npm install express axios dotenv
```
create index.js file  

trading-microservices/  
├── api-gateway-node/  
│   ├── package.json  
│   ├── node_modules/  
│   └── index.js   ← create here

to run in terminal 
```bash
node index.js
```
👉 Open: http://localhost:3000/stocks  

## Create Spring Boot project
EASIEST way:  
Open browser  
Go to: https://start.spring.io  
Select:  
Project: Maven  
Language: Java  
Dependencies:  
Spring Web  
Spring Data JPA  
PostgreSQL  
Click Generate  
Extract ZIP into user-service-java

user-service-java/  
├── mvnw  
├── mvnw.cmd  
├── pom.xml  
├── src/  
│   ├── main/  
│   │   ├── java/  
│   │   │   └── com/example/userservice/  
│   │   │       └── UserServiceApplication.java  
│   │   └── resources/  
│   │       ├── application.properties  
│   │       └── static/  
│   └── test/  
│       └── java/  
│           └── com/example/userservice/  
│               └── UserServiceApplicationTests.java  

👉 Step 3: Run project  
Step 1: Download and Install JDK 17 as project uses Spring Boot 3.x requires    
- Go to the official Oracle JDK downloads (oracle.com in Bing) or Adoptium Temurin (a popular free distribution).
- Choose Java 17 (LTS) — it’s the stable version required by Spring Boot 3.x.
- Download the Windows x64 Installer and run it.
- By default, it installs under:  

by terminal  
Invoke-WebRequest -Uri "https://github.com/adoptium/temurin17-binaries/releases/latest/download/OpenJDK17U-jdk_x64_windows_hotspot.msi" -OutFile "$env:USERPROFILE\Downloads\jdk17.msi"  

Start-Process msiexec.exe -Wait -ArgumentList '/i', "$env:USERPROFILE\Downloads\jdk17.msi", '/qn', '/norestart'  

set environment variables
[System.Environment]::SetEnvironmentVariable('JAVA_HOME', 'C:\Program Files\Eclipse Adoptium\jdk-17', [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\Program Files\Eclipse Adoptium\jdk-17\bin', [System.EnvironmentVariableTarget]::Machine)



```bash
mvn spring-boot:run
or 
.\mvnw.cmd spring-boot:run
```
👉 Runs on: http://localhost:8080

## Python Setup
User Request  
    ↓  
api-gateway-node (Port 8000)  
    ↓  
    ├→ user-service-java (Auth, users) :8081  
    ├→ trading-service-python (Stocks) :8001  
    │   ├→ Calls ai-service-python  
    │   └→ Returns: stocks + predictions  
    └→ ai-service-python (ML Predict) :8002  
        ├→ Analyzes stock data  
        └→ Returns: BUY/SELL signals  


```bash
cd ../ai-service-python
pip install fastapi uvicorn
```
pip freeze > requirements.txt  

create main.py and run    
```bash
uvicorn main:app --reload --port 8002
```

```bash
cd ../trading-service-python
pip install fastapi uvicorn psycopg2-binary
```
Create main.py and Run
```bash
uvicorn main:app --reload --port 8001
````
👉 http://localhost:8001/stocks

```bash
# Clone repo
git clone <repo>

# Create venv from scratch
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install from requirements.txt
pip install -r requirements.txt
.\venv\Scripts\Activate.ps1; 
pip install -r requirements.txt
```


Why Separate?  
1. Separation of Concerns  
Trading service = data provider  
AI service = intelligence/analysis  
Each does one thing well  
2. Independent Scaling  
Heavy prediction load? Scale ai-service-python  
High traffic for stock data? Scale trading-service-python  
3. Different Dependencies  
Trading: FastAPI, DB drivers  
AI: FastAPI, ML libraries (scikit-learn, TensorFlow, pandas)  
4. Independent Deployment  
Update AI model without affecting stock data service  
Deploy trading service separately  
5. Reusability  
AI service consumed by: trading-service, mobile app, web app, etc.  
Trading service consumed by: AI service, dashboard, etc.    

API Gateway receives request  
Trading Service fetches RELIANCE stock price (2950)  
Trading Service calls AI Service → "Predict for RELIANCE"  
AI Service returns → {"signal": "BUY"}  
Trading Service responds → {"stock": "RELIANCE", "price": 2950, "signal": "BUY"}  


services:  
  api-gateway:        # Uses api-gateway-node/Dockerfile  
  trading-service:    # Uses trading-service-python/Dockerfile  
  ai-service:         # Uses ai-service-python/Dockerfile  
  user-service:       # Uses user-service-java/Dockerfile  

  Here’s a clean **Markdown documentation** you can use to keep track of the Docker setup we’ve built, including installation steps and the Docker files we implemented:

---

# 🚀 MyInvestAppAPI – Docker Setup Documentation

## 📦 Installation Process

### 1. Install Docker Desktop
- Download Docker Desktop for Windows (AMD64 for most PCs, ARM64 only for ARM-based devices).
- Enable **WSL2** during installation.
- Ensure virtualization is enabled in BIOS (Intel VT-x / AMD-V).
- Verify installation:
  ```powershell
  docker --version
  docker compose version
  ```

### 2. Project Setup
- Navigate to your project folder:
  ```powershell
  cd E:\POCS\MyInvest\MyInvestAppAPI\MyInvestAppAPI
  ```
- Ensure you have `docker-compose.yml` and Dockerfiles for each service.

---

## 🐳 Dockerfile Examples

### API Gateway (Node.js)
`api-gateway-node/Dockerfile`
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000
CMD ["node", "index.js"]
```

---

### FastAPI Trading Service (Python)
`trading-service/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### User Service (Spring Boot)
`user-service-java/Dockerfile`
```dockerfile
FROM openjdk:17-jdk-slim

WORKDIR /app

COPY target/user-service.jar user-service.jar

EXPOSE 8081
ENTRYPOINT ["java", "-jar", "user-service.jar"]
```

---

## ⚙️ Docker Compose File

`docker-compose.yml`
```yaml
services:
  api-gateway:
    build: ./api-gateway-node
    ports:
      - "3000:3000"
    depends_on:
      - trading-service
      - user-service

  trading-service:
    build: ./trading-service
    ports:
      - "8000:8000"

  user-service:
    build: ./user-service-java
    ports:
      - "8081:8081"
```

---

## ▶️ Running the Services

1. Build and start all containers:
   ```powershell
   docker compose up --build
   ```

2. Verify services:
   - API Gateway → [http://localhost:3000/stocks](http://localhost:3000/stocks)  
   - Trading Service → `http://localhost:8000/` [(localhost in Bing)](https://www.bing.com/search?q="http%3A%2F%2Flocalhost%3A8000%2F")  
   - User Service → `http://localhost:8081/` [(localhost in Bing)](https://www.bing.com/search?q="http%3A%2F%2Flocalhost%3A8081%2F")  

3. Stop containers:
   ```powershell
   docker compose down
   ```

---

## ✅ Notes
- Remove `version:` from `docker-compose.yml` (deprecated in Docker Compose v2).
- Ensure Docker Desktop is running before executing commands.
- Use `.env` files to store sensitive credentials (like Neon DB connection details).

---
docker --version  
docker compose version  
docker compose up --build  
docker compose down

