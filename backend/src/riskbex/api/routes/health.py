from fastapi import APIRouter

from src.riskbex.api.schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}
