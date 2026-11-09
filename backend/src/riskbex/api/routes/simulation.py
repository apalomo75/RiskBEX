"""One read-only endpoint; no providers, inference or publication mutation."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from src.riskbex.api.operational import snapshot, performance_snapshot
from src.riskbex.backtesting.simulation import (
    Basis, Strategy, MAX_CAPITAL_EUR, SimulationDataError, SimulationInputError,
    simulate_investment,
)

router = APIRouter()


@router.get('/investment-simulation')
def investment_simulation(
    initial_capital: Annotated[float, Query(gt=0, le=MAX_CAPITAL_EUR, allow_inf_nan=False)],
    start_date: date,
    end_date: date,
    strategy: Strategy,
    basis: Basis = 'net',
):
    """Replay a published path from the start close (excluded) to end close (included)."""
    if start_date > end_date:
        raise HTTPException(status_code=422, detail='Start date must be on or before end date.')
    data = snapshot()  # Resolve exactly once, before validating the complete comparison.
    comparison = performance_snapshot(data)
    try:
        return simulate_investment(comparison, initial_session=str(data['history'].date.iloc[0]),
                                   initial_capital=initial_capital, start_date=start_date.isoformat(),
                                   end_date=end_date.isoformat(), strategy=strategy, basis=basis)
    except SimulationInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SimulationDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
