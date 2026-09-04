import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import lottery, notifications, sports
from services.fixtures_aggregator import refresh_all_fixtures
from services.results_resolver import resolve_pending_predictions

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(resolve_pending_predictions, "interval", hours=3, id="resolve_predictions")
    scheduler.add_job(refresh_all_fixtures, "interval", minutes=10, id="refresh_all_fixtures")
    scheduler.start()
    asyncio.create_task(refresh_all_fixtures())  # populate the cache immediately, don't block startup
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
