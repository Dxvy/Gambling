from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import lottery, notifications, sports
from services.results_resolver import resolve_pending_predictions

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(resolve_pending_predictions, "interval", hours=3, id="resolve_predictions")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="SportPredict API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://gambling-liart-rho.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sports.router, prefix="/api/sports")
app.include_router(lottery.router, prefix="/api/lottery")
app.include_router(notifications.router, prefix="/api/notifications")


@app.get("/")
def root():
    return {"status": "ok", "version": "1.0.0"}

# Run with: uvicorn main:app --reload --port 8000
