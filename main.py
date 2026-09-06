"""Application entrypoint (``uvicorn main:app``).

Wires the FastAPI app: permissive CORS (dev only), versioned routing
under `/api/v1`, and thin root aliases. Business logic lives in
`app.services`, HTTP wiring lives in `app.api`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.services import health_service


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)

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

    @app.get("/", tags=["health"], summary="Root")
    def read_root():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    # Backwards-compatible alias; canonical path is /api/v1/health.
    @app.get("/health", tags=["health"], summary="Liveness (legacy alias)")
    def health_alias():
        return health_service.get_health()

    return app


app = create_app()
