from fastapi import APIRouter
from fastapi.responses import JSONResponse
from src.riskbex.api.schemas import RunUpdateResponse

router = APIRouter()


@router.post('/run-update', response_model=RunUpdateResponse)
def run_update():
    return JSONResponse(status_code=403, content={
        'status': 'disabled', 'message': 'Updates disabled until authentication and orchestration are configured.',
        'stdout': '', 'stderr': '', 'returncode': None,
    })
