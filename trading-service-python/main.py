from fastapi import FastAPI

app = FastAPI()

@app.get("/stocks")
def get_stocks():
    return [{"stock": "RELIANCE", "price": 2950}]