import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import lottery, notifications, sports
from services.fixtures_aggregator import refresh_all_fixtures
from services.prediction_precompute import precompute_predictions
from services.results_resolver import resolve_pending_predictions

scheduler = AsyncIOScheduler()

# Applied to every job: a late tick still runs instead of being dropped
# (misfire_grace_time), a burst of missed ticks collapses into one run
# instead of stacking up (coalesce), and a slow run can't overlap with the
# next tick (max_instances). Previously the defaults (grace=1s, no coalesce,
# unlimited instances) caused APScheduler to silently skip runs that started
# even slightly late — see the "was missed by 0:00:01" log from the incident.
_JOB_DEFAULTS = dict(misfire_grace_time=60, coalesce=True, max_instances=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(resolve_pending_predictions, "interval", hours=3, id="resolve_predictions", **_JOB_DEFAULTS)
    scheduler.add_job(refresh_all_fixtures, "interval", minutes=10, id="refresh_all_fixtures", **_JOB_DEFAULTS)
    scheduler.add_job(precompute_predictions, "interval", minutes=30, id="precompute_predictions", **_JOB_DEFAULTS)
    scheduler.start()
    asyncio.create_task(refresh_all_fixtures())  # populate the cache immediately, don't block startup
    asyncio.create_task(precompute_predictions())  # start filling match_predictions immediately too
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
