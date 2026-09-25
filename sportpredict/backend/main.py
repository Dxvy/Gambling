import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import lottery, notifications, sports
from services.fixtures_aggregator import refresh_all_fixtures
from services.prediction_precompute import precompute_predictions
from services.results_resolver import resolve_pending_predictions

# Without this, the root logger stays at Python's default WARNING level and
# every logger.info() call app-wide (fixture/prediction fetch progress,
# rate-limiter waits, the precompute job's "wrote N predictions" summary)
# is silently dropped — only warnings/errors ever reach Railway's log
# stream, which made this app's background jobs impossible to verify.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

scheduler = AsyncIOScheduler()

# Applied to every job: a late tick still runs instead of being dropped
# (misfire_grace_time), a burst of missed ticks collapses into one run
# instead of stacking up (coalesce), and a slow run can't overlap with the
# next tick (max_instances). Previously the defaults (grace=1s, no coalesce,
# unlimited instances) caused APScheduler to silently skip runs that started
# even slightly late — see the "was missed by 0:00:01" log from the incident.
_JOB_DEFAULTS = dict(misfire_grace_time=60, coalesce=True, max_instances=1)


async def _startup_fixtures_then_predictions() -> None:
    """
    precompute_predictions() now reads fixtures from refresh_all_fixtures()'s
    shared cache instead of fetching them again itself (see
    prediction_precompute.py), so on a cold start it must run after the
    cache has been populated at least once — otherwise it finds an empty
    cache and precomputes nothing. Both still run as one background task so
    neither blocks the app from becoming ready for the healthcheck.
    """
    await refresh_all_fixtures()
    await precompute_predictions()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(resolve_pending_predictions, "interval", hours=3, id="resolve_predictions", **_JOB_DEFAULTS)
    scheduler.add_job(refresh_all_fixtures, "interval", minutes=10, id="refresh_all_fixtures", **_JOB_DEFAULTS)
    scheduler.add_job(precompute_predictions, "interval", minutes=30, id="precompute_predictions", **_JOB_DEFAULTS)
    scheduler.start()
    asyncio.create_task(_startup_fixtures_then_predictions())
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
