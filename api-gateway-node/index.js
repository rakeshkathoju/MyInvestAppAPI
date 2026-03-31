const express = require("express");
const axios = require("axios");

const app = express();

app.get("/stocks", async (req, res) => {
  const response = await axios.get("http://localhost:8001/stocks");
  res.json(response.data);
});

app.listen(3000, () => console.log("Gateway running on 3000"));