"""API version 1 routes."""

from fastapi import APIRouter

from app.api.v1 import auth, cards, statements, transactions

router = APIRouter(prefix="/api/v1")

# Include routers
router.include_router(auth.router)
router.include_router(statements.router)
router.include_router(cards.router)
router.include_router(transactions.router)
