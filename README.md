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


```bash
cd ../ai-service-python
pip install fastapi uvicorn
```

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
