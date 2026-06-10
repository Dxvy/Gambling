from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import sports, lottery

app = FastAPI(title="SportPredict API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-app.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sports.router, prefix="/api/sports")
app.include_router(lottery.router, prefix="/api/lottery")


@app.get("/")
def root():
    return {"status": "ok", "version": "1.0.0"}

# Run with: uvicorn main:app --reload --port 8000
