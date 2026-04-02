const express = require("express");
const axios = require("axios");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

// Python service URL
const TRADING_SERVICE_URL = "http://localhost:8001";

// Route: Get stocks
app.get("/stocks", async (req, res) => {
  try {
    const response = await axios.get(`${TRADING_SERVICE_URL}/stocks`);
    res.json(response.data);
  } catch (error) {
    console.error("Error fetching stocks:", error.message);
    res.status(500).json({ error: "Failed to fetch stocks" });
  }
});

app.listen(3000, () => {
  console.log("🚀 API Gateway running on http://localhost:3000");
});

app.get("/health", (req, res) => {
  res.json({ status: "Gateway is running" });
});