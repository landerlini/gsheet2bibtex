from fastapi import FastAPI
import os

app = FastAPI(root_path=os.getenv("BASE_URL", "/"))

@app.get("/")
async def read_root():
    return {"message": "Hello World"}