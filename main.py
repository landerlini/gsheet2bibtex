from fastapi import FastAPI
import os

BASE_URL = os.getenv("BASE_URL", "/")

app = FastAPI(root_path=BASE_URL)

@app.get(f"{BASE_URL}/")
async def read_root():
    return {"message": "Hello World"}