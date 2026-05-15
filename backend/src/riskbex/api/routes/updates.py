from pathlib import Path
import subprocess
import sys

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.riskbex.api.schemas import RunUpdateResponse


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@router.post("/run-update", response_model=RunUpdateResponse)
def run_update():
    try:
        result = subprocess.run(
            [sys.executable, "scripts/run_daily_update.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Pipeline update timed out.",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "returncode": None,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(exc),
                "stdout": "",
                "stderr": "",
                "returncode": None,
            },
        )

    response = {
        "status": "success" if result.returncode == 0 else "error",
        "message": "Pipeline update completed successfully."
        if result.returncode == 0
        else "Pipeline update failed.",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }

    if result.returncode != 0:
        return JSONResponse(status_code=500, content=response)

    return response
