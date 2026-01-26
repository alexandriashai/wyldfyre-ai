"""
FastAPI application entry point.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ai_core import configure_cost_tracker, configure_logging, get_logger, get_settings
from ai_messaging import get_redis_client

from .config import get_api_config
from .database import close_db, get_session_factory, init_db
from .middleware import LoggingMiddleware, RateLimitMiddleware
from .routes import (
    agents_router,
    auth_router,
    chat_router,
    containers_router,
    conversations_router,
    domains_router,
    files_router,
    github_router,
    grafana_router,
    health_router,
    integrations_router,
    memory_router,
    notifications_router,
    plans_router,
    projects_router,
    settings_router,
    tasks_router,
    telos_router,
    usage_router,
    workspace_router,
)
from .websocket.handlers import AgentResponseHandler
from .websocket.manager import get_connection_manager
from .websocket.terminal import router as terminal_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Manages startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting API server...")

    # Configure logging
    settings = get_settings()
    configure_logging(
        log_level=settings.logging.level,
        log_format=settings.logging.format,
    )

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")

        # Configure cost tracker with database session factory
        configure_cost_tracker(get_session_factory())
        logger.info("Cost tracker configured")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        # Continue without database for now

    # Initialize Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))

    # Start agent response handler
    agent_handler = None
    try:
        redis = await get_redis_client()
        manager = get_connection_manager()
        agent_handler = AgentResponseHandler(manager, redis)
        asyncio.create_task(agent_handler.start())
        logger.info("Agent response handler started")
    except Exception as e:
        logger.error("Failed to start agent response handler", error=str(e))

    logger.info("API server started")

    yield

    # Shutdown
    logger.info("Shutting down API server...")

    # Stop agent response handler
    if agent_handler:
        await agent_handler.stop()

    # Close database
    await close_db()

    logger.info("API server stopped")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    config = get_api_config()

    if config.jwt_secret_key == "change-me-in-production-use-secrets-manager":
        logger.critical("SECURITY: Using insecure default JWT secret! Set JWT_SECRET env var.")

    app = FastAPI(
        title="Wyld Fyre AI API",
        description="Backend API for Wyld Fyre AI - Multi-Agent AI Infrastructure powered by Claude",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
    )

    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    app.include_router(tasks_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")  # Project organization
    app.include_router(conversations_router, prefix="/api")
    app.include_router(domains_router, prefix="/api")
    app.include_router(files_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(grafana_router, prefix="/api")  # Grafana SSO proxy
    app.include_router(usage_router, prefix="/api")  # Usage analytics
    app.include_router(workspace_router, prefix="/api")  # Workspace file/git/deploy
    app.include_router(integrations_router, prefix="/api")  # Visual builder integrations
    app.include_router(containers_router, prefix="/api")  # Docker container management
    app.include_router(github_router, prefix="/api")  # GitHub integration
    app.include_router(plans_router, prefix="/api")  # Plan CRUD management
    app.include_router(telos_router, prefix="/api")  # TELOS mission/beliefs/wizard
    app.include_router(chat_router)  # WebSocket at root level
    app.include_router(terminal_router)  # Terminal WebSocket

    # Prometheus metrics endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle uncaught exceptions."""
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if config.debug else None,
            },
        )

    return app


# Create application instance
app = create_app()


def main() -> None:
    """Run the API server."""
    import uvicorn

    config = get_api_config()

    uvicorn.run(
        "api.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info" if not config.debug else "debug",
    )


if __name__ == "__main__":
    main()
