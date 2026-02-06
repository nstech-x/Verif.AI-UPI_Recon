from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["utility"])


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "UPI Reconciliation API",
        "version": "1.v1.0",
        "status": "running",
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
