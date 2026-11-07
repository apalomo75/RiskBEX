from typing import Optional

from fastapi import APIRouter

from src.riskbex.api.schemas import HistoricalRiskPoint, LatestRiskResponse



router = APIRouter()


def load_data():
    from src.riskbex.api.operational import snapshot, risk_points
    return risk_points(snapshot())


@router.get("/latest-risk", response_model=LatestRiskResponse)
def latest_risk():
    from src.riskbex.api.operational import snapshot, risk_points
    data = snapshot()
    return dict(risk_points(data).iloc[-1].to_dict(), signal=data['latest'])


@router.get("/historical-risk", response_model=list[HistoricalRiskPoint])
def historical_risk(limit: Optional[str] = None):
    df = load_data()
    if limit and limit.lower() == 'all':
        return df.to_dict(orient='records')
    try:
        count = max(1, int(limit)) if limit is not None else 250
    except (TypeError, ValueError):
        count = 250
    return df.tail(count).to_dict(orient='records')
