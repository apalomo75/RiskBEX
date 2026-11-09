"""Read-only capital replay of a validated MAIN comparison publication."""
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from src.riskbex.backtesting.metrics import historical_cvar, TRADING_DAYS_PER_YEAR

MAX_RETURN_SESSIONS = 10_000
MAX_CAPITAL_EUR = 1_000_000_000_000
Strategy = Literal['benchmark', 'regime_based', 'ml_hard', 'ml_proba']
Basis = Literal['gross', 'net']


class SimulationInputs(BaseModel):
    initial_capital: float = Field(gt=0, le=MAX_CAPITAL_EUR, allow_inf_nan=False)
    start_date: date
    end_date: date
    strategy: Strategy
    basis: Basis = 'net'

    @field_validator('initial_capital', mode='before')
    @classmethod
    def reject_boolean_capital(cls, value):
        if isinstance(value, bool):
            raise ValueError('Initial capital must be a positive EUR amount.')
        return value

    @model_validator(mode='after')
    def ordered_dates(self):
        if self.start_date > self.end_date:
            raise ValueError('Start date must be on or before end date.')
        return self


class SimulationInputError(ValueError):
    """Invalid dates or an excessive requested window."""


class SimulationDataError(ValueError):
    """The supplied historical publication is incomplete or inconsistent."""


def _metrics(returns, values, capital):
    return {
        'final_capital_eur': float(values[-1]),
        'profit_loss_eur': float(values[-1] - capital),
        'cumulative_return': float(values[-1] / capital - 1),
        'maximum_drawdown': float(np.min(values / np.maximum.accumulate(values) - 1)),
        'annualized_volatility': float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) >= 2 else None,
        'daily_cvar_95': historical_cvar(returns) if len(returns) else None,
        'return_observations': len(returns),
    }


def simulate_investment(comparison: dict, *, initial_session: str, initial_capital: float,
                        start_date: str, end_date: str, strategy: Strategy, basis: Basis = 'net') -> dict:
    """Replay (start close, end close] from performance_snapshot(snapshot()).

    initial_session is the first signal session of that SAME snapshot, preceding
    its first realised return. Stored returns already contain prior-close exposure.
    This function neither shifts exposures nor constructs fresh-entry portfolios.
    """
    inputs = SimulationInputs(initial_capital=initial_capital, start_date=start_date,
                              end_date=end_date, strategy=strategy, basis=basis)
    start, end = inputs.start_date.isoformat(), inputs.end_date.isoformat()
    try:
        frame = pd.DataFrame(comparison['results'])
        publication = comparison['publication']
        rate = float(comparison['conventions']['cost_rate'])
        if not publication.get('version') or not publication.get('model_version') or not np.isclose(rate, .001, rtol=0, atol=1e-15):
            raise ValueError('Missing provenance or unsupported cost convention.')
        dates = [initial_session, *frame['date'].tolist()]
        if any(not isinstance(d, str) or date.fromisoformat(d).isoformat() != d for d in dates):
            raise ValueError('Noncanonical session dates.')
        if dates != sorted(set(dates)):
            raise ValueError('Session dates must be unique and increasing.')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SimulationDataError('A complete validated MAIN comparison and its first signal session are required.') from exc
    if start not in dates or end not in dates:
        raise SimulationInputError('Start and end dates must be published trading sessions; dates are never interpolated.')
    window = frame.loc[(frame.date > start) & (frame.date <= end)].copy()
    if len(window) > MAX_RETURN_SESSIONS:
        raise SimulationInputError(f'A simulation may include at most {MAX_RETURN_SESSIONS:,} return sessions.')
    key = inputs.strategy
    benchmark = key == 'benchmark'
    return_column = 'benchmark_return' if benchmark else f'{key}_return' + ('_net' if inputs.basis == 'net' else '')
    required = ['benchmark_return', return_column]
    if not benchmark:
        required += [f'{key}_return', f'{key}_return_net', f'transaction_cost_{key}',
                     f'exposure_change_{key}', f'strategy_exposure_{key}']
    try:
        if not np.isfinite(window[required].to_numpy(dtype=float)).all():
            raise ValueError('Nonfinite observations.')
        if not benchmark:
            costs, changes = window[f'transaction_cost_{key}'], window[f'exposure_change_{key}']
            if (not window[f'strategy_exposure_{key}'].between(0, 1).all() or (changes < 0).any()
                    or not np.allclose(costs, rate * changes, rtol=1e-10, atol=1e-12)
                    or not np.allclose(window[f'{key}_return_net'], window[f'{key}_return'] - costs, rtol=1e-10, atol=1e-12)):
                raise ValueError('Stored cost or exposure conventions differ.')
        returns = window[return_column].astype(float).reset_index(drop=True)
        benchmark_returns = window.benchmark_return.astype(float).reset_index(drop=True)
        capital = inputs.initial_capital
        with np.errstate(over='raise', invalid='raise', under='ignore'):
            values = capital * np.exp(np.r_[0., returns.cumsum().to_numpy()])
            benchmark_values = capital * np.exp(np.r_[0., benchmark_returns.cumsum().to_numpy()])
        if (not np.isfinite(values).all() or not np.isfinite(benchmark_values).all()
                or (values <= 0).any() or (benchmark_values <= 0).any()):
            raise ValueError('Capital path exceeds numerical limits.')
    except (KeyError, TypeError, ValueError, FloatingPointError) as exc:
        raise SimulationDataError('Complete finite aligned returns and consistent stored costs are required.') from exc
    portfolio_metrics = _metrics(returns, values, capital)
    benchmark_metrics = _metrics(benchmark_returns, benchmark_values, capital)
    differences = {name: (portfolio_metrics[name] - benchmark_metrics[name]
                          if portfolio_metrics[name] is not None and benchmark_metrics[name] is not None else None)
                   for name in ['final_capital_eur', 'profit_loss_eur', 'cumulative_return',
                                'maximum_drawdown', 'annualized_volatility', 'daily_cvar_95']}
    changes = pd.Series(0., index=window.index) if benchmark else window[f'exposure_change_{key}']
    costs = pd.Series(0., index=window.index) if benchmark else window[f'transaction_cost_{key}']
    total_cost = float(costs.sum())
    drawdowns = values / np.maximum.accumulate(values) - 1
    benchmark_drawdowns = benchmark_values / np.maximum.accumulate(benchmark_values) - 1
    exposures = np.ones(len(window)) if benchmark else window[f'strategy_exposure_{key}'].to_numpy(dtype=float)
    participation = {}
    for label, mask in [('down_market', benchmark_returns < 0), ('up_market', benchmark_returns > 0)]:
        count = int(mask.sum())
        participation[label] = {
            'sessions': count,
            'average_applied_exposure': float(exposures[mask].mean()) if count else None,
            'log_return_difference_vs_buy_hold': float((returns[mask] - benchmark_returns[mask]).sum()) if count else None,
        }
    return {
        'inputs': inputs.model_dump(mode='json'),
        'publication': dict(publication),
        'effective_dates': {'capital_anchor_session': start, 'first_return_session': window.date.iloc[0] if len(window) else None,
                            'last_return_session': window.date.iloc[-1] if len(window) else None,
                            'end_session': end, 'return_sessions': len(window)},
        'series': [{'date': d, 'portfolio_value_eur': float(v), 'buy_hold_value_eur': float(b),
                    'is_capital_anchor': i == 0,
                    'portfolio_drawdown': float(drawdowns[i]), 'buy_hold_drawdown': float(benchmark_drawdowns[i]),
                    'applied_exposure': float(exposures[i - 1]) if i else None,
                    'cash_exposure': float(1 - exposures[i - 1]) if i else None}
                   for i, (d, v, b) in enumerate(zip([start, *window.date], values, benchmark_values))],
        'participation': participation,
        'portfolio': portfolio_metrics,
        'buy_hold': benchmark_metrics,
        'comparison_minus_buy_hold': differences,
        'costs_and_turnover': {
            'path': 'published_historical_path', 'cost_rate': 0. if benchmark else rate,
            'total_turnover_exposure_units': float(changes.sum()),
            'annualized_turnover_exposure_units': float(changes.mean() * TRADING_DAYS_PER_YEAR) if len(window) else None,
            'published_cost_log_return': total_cost,
            'deducted_cost_log_return': total_cost if inputs.basis == 'net' else 0.,
            'entry_cost_included': False, 'liquidation_cost_included': False,
            'buy_hold_turnover': 0., 'buy_hold_cost_log_return': 0.,
        },
        'assumptions': [
            'Historical simulation, not an executable portfolio or investment recommendation; no future performance guarantee.',
            'Capital is invested at the start-session close; its return is excluded. Subsequent published returns through the end-session close are included.',
            'Stored returns already apply prior-close exposure once. No new exposure shift or model inference is performed.',
            'Uninvested cash earns zero. Exposure-scaled index log returns follow the published convention.',
            'Net replay retains published rebalancing costs, including the first included return\'s cost; it is not a fresh-entry cost reconstruction.',
            'Gross replay excludes costs. Net replay uses stored net returns without subtracting costs again.',
            'Entry and final liquidation costs are omitted. Buy & Hold has no modelled trading costs.',
            'ETF fees, broker charges, spreads, slippage, financing and taxes are not modelled. Cost sums are log-return deductions, not EUR invoices.',
            'Drawdown includes the initial capital anchor. Annualized volatility uses sample daily standard deviation and 252 sessions; it is unavailable below two returns.',
            'Daily CVaR is the mean signed daily log return at or below the empirical fifth percentile; it is unavailable without returns.',
        ],
    }
