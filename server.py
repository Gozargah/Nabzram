import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.dependencies import close_global_database
from utils import get_app_root

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events (startup/shutdown)"""
    yield
    close_global_database()
    from app.services.process_service import process_manager

    await process_manager.shutdown_all()


app = FastAPI(
    title="Nabzram",
    description="FastAPI Proxy Subscription Manager with Xray-core",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
def include_routers(app: FastAPI):
    from app.api.routes import logs, servers, subscriptions, system, updates
    from app.api.routes import settings as settings_router

    app.include_router(
        subscriptions.router, prefix="/subscriptions", tags=["subscriptions"]
    )
    app.include_router(servers.router, prefix="/subscriptions", tags=["servers"])
    app.include_router(logs.router, prefix="/logs", tags=["logs"])
    app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(updates.router, prefix="/updates", tags=["updates"])


include_routers(app)

# Serve frontend
UI_DIR = get_app_root() / "ui" / "dist"
app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")


def start_server():
    """Run FastAPI with Uvicorn"""
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


def start_server_thread():
    """Start FastAPI in background thread"""
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()


if __name__ == "__main__":
    start_server()
