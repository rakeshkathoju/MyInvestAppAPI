const express = require("express");
const axios = require("axios");
const cors = require("cors");
require("dotenv").config();

const app = express();
app.use(cors());
app.use(express.json());

// Service URLs from environment or defaults
const TRADING_SERVICE_URL = process.env.TRADING_SERVICE_URL || "http://trading-service:8001";
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://ai-service:8000";
const USER_SERVICE_URL = process.env.USER_SERVICE_URL || "http://user-service:8080";

const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false
  }
});

// Route: Get stocks
app.get("/stocks", async (req, res) => {
  try {
    console.log(`📡 Fetching stocks from: ${TRADING_SERVICE_URL}/stocks`);
    const response = await axios.get(`${TRADING_SERVICE_URL}/stocks`, {
      timeout: 5000
    });
    res.json(response.data);
  } catch (error) {
    console.error("❌ Error fetching stocks:", {
      message: error.message,
      code: error.code,
      url: `${TRADING_SERVICE_URL}/stocks`
    });
    res.status(500).json({ 
      error: "Failed to fetch stocks",
      details: error.message,
      tradingServiceUrl: TRADING_SERVICE_URL
    });
  }
});

// INSERT trade
app.post("/trade", async (req, res) => {
  try {
    const response = await axios.post(`${TRADING_SERVICE_URL}/trade`, req.body);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: "Error placing trade" });
  }
});

// ---------- AI Service routes ----------

app.post("/ai/train", async (req, res) => {
  try {
    const response = await axios.post(`${AI_SERVICE_URL}/train`, req.body, { timeout: 120000 });
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: "Error training model", details: err.message });
  }
});

app.post("/ai/predict", async (req, res) => {
  try {
    const response = await axios.post(`${AI_SERVICE_URL}/predict`, req.body, { timeout: 15000 });
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: "Error getting prediction", details: err.message });
  }
});

// ---------- User Service routes ----------

app.post("/users/register", async (req, res) => {
  try {
    const response = await axios.post(`${USER_SERVICE_URL}/users/register`, req.body);
    res.status(response.status).json(response.data);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json(err.response?.data || { error: "Error registering user" });
  }
});

app.post("/users/login", async (req, res) => {
  try {
    const response = await axios.post(`${USER_SERVICE_URL}/users/login`, req.body);
    res.json(response.data);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json(err.response?.data || { error: "Error logging in" });
  }
});

app.get("/users/:id", async (req, res) => {
  try {
    const response = await axios.get(`${USER_SERVICE_URL}/users/${req.params.id}`);
    res.json(response.data);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json(err.response?.data || { error: "User not found" });
  }
});

app.get("/users/:id/portfolio", async (req, res) => {
  try {
    const response = await axios.get(`${USER_SERVICE_URL}/users/${req.params.id}/portfolio`);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: "Error fetching portfolio", details: err.message });
  }
});

app.listen(3000, () => {
  console.log("🚀 API Gateway running on http://localhost:3000");
  console.log(`   Trading Service: ${TRADING_SERVICE_URL}`);
  console.log(`   AI Service: ${AI_SERVICE_URL}`);
  console.log(`   User Service: ${USER_SERVICE_URL}`);
});

app.get("/health", async (req, res) => {
  const health = {
    status: "Gateway is running",
    timestamp: new Date().toISOString(),
    services: {
      trading: "unknown",
      ai: "unknown",
      user: "unknown"
    }
  };

  try {
    await axios.get(`${TRADING_SERVICE_URL}/health`, { timeout: 2000 });
    health.services.trading = "✅ connected";
  } catch {
    health.services.trading = "❌ disconnected";
  }

  try {
    await axios.get(`${AI_SERVICE_URL}/health`, { timeout: 2000 });
    health.services.ai = "✅ connected";
  } catch {
    health.services.ai = "❌ disconnected";
  }

  try {
    await axios.get(`${USER_SERVICE_URL}/users/health`, { timeout: 2000 });
    health.services.user = "✅ connected";
  } catch {
    health.services.user = "❌ disconnected";
  }

  res.json(health);
});