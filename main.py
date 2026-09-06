"""Application entrypoint (``uvicorn main:app``).

Wires the FastAPI app: permissive CORS (dev only), versioned routing
under `/api/v1`, and thin root aliases. Business logic lives in
`app.services`, HTTP wiring lives in `app.api`.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.config import settings
from app.services import health_service
from app.services.llm import LLMConfigError, LLMError
from app.services.observability import (
  initialize_neatlogs,
  shutdown_neatlogs,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
  """Initialize and clean up process-level services."""
  initialize_neatlogs()

  try:
    yield
  finally:
    shutdown_neatlogs()


def create_app() -> FastAPI:
    app = FastAPI(
      title=settings.app_name, 
      version=settings.app_version,
      lifespan=lifespan,
    )

    # Permissive CORS for local development (Nuxt on 8000/8080 or any
    # other origin). Tighten this before production.
    # NOTE: allow_credentials must be False when origins is ["*"].
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router)

    # Map vendor-neutral LLM failures to HTTP: misconfiguration (no key,
    # unknown provider — raised from the `get_llm` dependency) is a 500;
    # upstream provider failures are a 502.
    @app.exception_handler(LLMError)
    async def llm_error_handler(_request: Request, exc: LLMError):
        status = 500 if isinstance(exc, LLMConfigError) else 502
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    @app.get("/", tags=["health"], summary="Root")
    def read_root():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    # Backwards-compatible alias; canonical path is /api/v1/health.
    @app.get("/health", tags=["health"], summary="Liveness (legacy alias)")
    def health_alias():
        return health_service.get_health()

    return app


app = create_app()
