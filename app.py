from __future__ import annotations
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from routers import router
from config import settings
from shared import configure_logging, get_logger


# configure logging once at a startup
configure_logging()
logger = get_logger(__name__)

# lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
  logger.info("Vidhya starting", env=settings.APP_ENV)

  # from services import SlackAdapter, set_slack
  # set_slack(await SlackAdapter().initialize())

  yield

  from shared import redis
  if redis is not None:
    await redis.aclose()
  logger.info("Vidhya shutdown complete")


def _add_health_routes(app: FastAPI) -> None:
  @app.get("/health", tags=['ops'])
  async def health_check():
    return {"status": "ok", 'env': settings.APP_ENV}

  @app.get("/health/ready", tags=['ops'])
  async def health_ready():
    checks: defaultdict[str, str] = defaultdict(str)

    from shared import redis
    if redis is None:
      checks['redis'] = 'disabled'
    else:
      try:
        await redis.ping()
        checks['redis'] = 'ok'
      except Exception as e:
        checks['redis'] = f'error: {e}'

    ok = all(status in ('ok', 'disabled') for status in checks.values())
    return JSONResponse(content={"checks": checks}, status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE)


def _add_api_routes(app: FastAPI) -> None:
  app.include_router(router)


# app factory
def create_app() -> FastAPI:
  app = FastAPI(title="Vidhya", version="0.1.0", lifespan=lifespan, root_path='/api', docs_url="/docs" if settings.IS_DEVELOPMENT else None, redoc_url=None)
  _add_health_routes(app)
  _add_api_routes(app)
  return app


app = create_app()
