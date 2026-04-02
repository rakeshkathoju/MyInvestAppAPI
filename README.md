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