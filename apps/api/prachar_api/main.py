from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import TenantMiddleware
from .routers import admin, attribution, auth, audits, brands, campaigns, chat, connections, misc, reports, video_gen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("prachar.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PRACHAR API",
        version="0.1.0",
        description="AI-driven global ad agency platform.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantMiddleware)
    app.include_router(misc.router)
    app.include_router(auth.router)
    app.include_router(brands.router)
    app.include_router(audits.router)
    app.include_router(connections.router)
    app.include_router(campaigns.router)
    app.include_router(reports.router)
    app.include_router(attribution.router)
    app.include_router(admin.router)
    app.include_router(chat.router)
    app.include_router(video_gen.router)
    return app


app = create_app()
