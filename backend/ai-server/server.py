from fastapi import FastAPI

app = FastAPI(title="AI Server Infrastructure Base")

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "AI Server is running"}

@app.get("/v1/test")
def test_connection():
    return {"message": "Connection to AI Server successful"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
