from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.api.middleware.error_handler import (
    handle_generic_error,
    handle_integrity_error,
    handle_statement_processing_error,
    handle_validation_error,
)
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.v1 import router as v1_router
from app.api.v1.health import router as health_router
from app.config import settings
from app.core.exceptions import StatementProcessingError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="CC Rewards Dashboard API",
        description="Secure Credit Card Statement Ingestion & Analysis",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Register exception handlers (order matters - most specific first)
    app.add_exception_handler(StatementProcessingError, handle_statement_processing_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(Exception, handle_generic_error)

    # Register routers
    app.include_router(health_router)
    app.include_router(v1_router)

    return app


app = create_app()
