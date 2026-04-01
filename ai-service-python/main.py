from fastapi import FastAPI

app = FastAPI()

@app.post("/predict")
def predict(data: dict):
    return {"signal": "BUY"}