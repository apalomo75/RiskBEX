"""Streamlit API presentation only; capital paths and risk metrics stay in the API."""
import math

import altair as alt
import pandas as pd
import requests
import streamlit as st

STRATEGIES = {'Buy & Hold': 'benchmark', 'Regime-Based': 'regime_based',
              'ML Hard': 'ml_hard', 'ML Probability-Weighted': 'ml_proba'}
BASES = {'Gross': 'gross', 'Net of modeled transaction costs': 'net'}
MAX_CAPITAL_EUR = 1_000_000_000_000.


def money(value):
    return f'€{value:,.2f}' if isinstance(value, (int, float)) and math.isfinite(value) else 'Unavailable'


def percentage(value):
    return f'{value:.2%}' if isinstance(value, (int, float)) and math.isfinite(value) else 'Unavailable'


def series_chart(series, fields, ylabel, percent=False):
    """Reshape API observations for plotting; never derive financial series."""
    frame = pd.DataFrame(series)[['date', *fields]].rename(columns=fields)
    frame['date'] = pd.to_datetime(frame.date)
    data = frame.melt('date', var_name='Series', value_name='Value').dropna(subset=['Value'])
    chart = alt.Chart(data).encode(
        x=alt.X('date:T', title='Historical Session', axis=alt.Axis(format='%b %Y', labelFontSize=12)),
        y=alt.Y('Value:Q', title=ylabel, scale=alt.Scale(zero=False),
                axis=alt.Axis(format='.0%' if percent else ',.0f', labelFontSize=12)),
        color=alt.Color('Series:N', legend=alt.Legend(orient='bottom', title=None)),
        tooltip=[alt.Tooltip('date:T', title='Session', format='%d %b %Y'),
                 alt.Tooltip('Series:N'), alt.Tooltip('Value:Q', title=ylabel, format='.2%' if percent else ',.2f')])
    return (chart.mark_line() + chart.mark_circle(size=45, opacity=0)).properties(height=300).interactive()


def validate_response(result, parameters):
    """Reject incomplete/misaligned responses instead of estimating missing values."""
    if not isinstance(result, dict) or not isinstance(result.get('publication'), dict):
        raise ValueError('Incomplete simulation response.')
    if result.get('inputs') != parameters:
        raise ValueError('Simulation inputs do not match the request.')
    series = result.get('series')
    if not isinstance(series, list) or not series or len(series) > 10_001:
        raise ValueError('Invalid simulation series.')
    dates = [row['date'] for row in series]
    if dates != sorted(set(dates)) or dates[0] != parameters['start_date'] or dates[-1] != parameters['end_date']:
        raise ValueError('Simulation dates do not match the request.')
    for row in series:
        for key in ['portfolio_value_eur', 'buy_hold_value_eur']:
            if not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) or row[key] <= 0:
                raise ValueError('Incomplete capital series.')
    if (series[0]['portfolio_value_eur'] != parameters['initial_capital'] or
            series[0]['buy_hold_value_eur'] != parameters['initial_capital']):
        raise ValueError('Capital anchors do not match.')
    for key in ['portfolio', 'buy_hold', 'comparison_minus_buy_hold', 'costs_and_turnover', 'effective_dates']:
        if not isinstance(result.get(key), dict):
            raise ValueError('Incomplete simulation summary.')
    metric_keys = ['final_capital_eur', 'profit_loss_eur', 'cumulative_return',
                   'maximum_drawdown', 'annualized_volatility', 'daily_cvar_95']
    for section in ['portfolio', 'buy_hold', 'comparison_minus_buy_hold']:
        for key in metric_keys:
            value = result[section].get(key)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Invalid simulation metric.')
    for row in series:
        for key in ['portfolio_drawdown', 'buy_hold_drawdown', 'applied_exposure', 'cash_exposure']:
            value = row.get(key)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Invalid optional chart observation.')
    for key in ['portfolio', 'buy_hold']:
        if result[key].get('final_capital_eur') != series[-1]['portfolio_value_eur' if key == 'portfolio' else 'buy_hold_value_eur']:
            raise ValueError('Capital summary and series differ.')
    return result


def render_interpretation(result):
    st.subheader('Understanding Your Simulation')
    differences = result['comparison_minus_buy_hold']
    delta = differences.get('final_capital_eur')
    if delta is None:
        st.write('The comparison with Buy & Hold is unavailable.')
    elif abs(delta) < .005:
        st.write('The selected strategy finished at the same value as Buy & Hold at displayed precision.')
    else:
        st.write(f"The selected strategy finished {money(abs(delta))} {'above' if delta > 0 else 'below'} Buy & Hold.")
    for key, label, lower_is_better in [('annualized_volatility', 'Annualized volatility', True),
                                       ('daily_cvar_95', 'Historical daily CVaR loss severity', False),
                                       ('maximum_drawdown', 'Maximum drawdown severity', False)]:
        delta = differences.get(key)
        if delta is None:
            st.write(f'{label}: unavailable for this sample.')
        elif key == 'daily_cvar_95' and result['portfolio'].get(key, -1) >= 0 and result['buy_hold'].get(key, -1) >= 0:
            st.write(f"Daily CVaR is {percentage(result['portfolio'][key])} versus {percentage(result['buy_hold'][key])} for Buy & Hold. Both tail means are non-negative; neither tail mean represents a loss.")
        elif abs(delta) < .00005:
            st.write(f'{label}: unchanged at displayed precision versus Buy & Hold.')
        else:
            reduced = delta < 0 if lower_is_better else delta > 0
            st.write(f"{label}: {'lower' if reduced else 'higher'} than Buy & Hold by {abs(delta) * 100:.2f} percentage points.")
    for key, label in [('down_market', 'declining'), ('up_market', 'rising')]:
        group = result.get('participation', {}).get(key)
        if not group or not group.get('sessions') or group.get('log_return_difference_vs_buy_hold') is None:
            st.write(f'No supported assessment is available for {label} market sessions in this sample.')
            continue
        delta = group['log_return_difference_vs_buy_hold']
        meaning = ('less loss' if delta > 0 else 'more loss') if key == 'down_market' else ('more gain' if delta > 0 else 'less gain')
        if abs(delta) < .00005:
            meaning = 'no difference at displayed precision'
        st.write(f"Across {group['sessions']:,} {label} market sessions, average equity exposure was "
                 f"{percentage(group.get('average_applied_exposure'))}. The selected strategy recorded {meaning} than Buy & Hold "
                 f"({delta * 100:+.2f} log-return points).")
    st.caption('Session groups sum daily log-return differences on the selected gross/net basis. They are not continuous-period returns or drawdown reductions. Flat sessions remain in overall results. Costs may offset exposure benefits.')
    st.write('Lower market exposure can soften some market losses and sacrifice gains when equities rise. XGBoost forecasts next-session risk regimes, not market prices or the timing of crashes.')


def render_result(result):
    inputs, portfolio, benchmark = result['inputs'], result['portfolio'], result['buy_hold']
    name = next(label for label, key in STRATEGIES.items() if key == inputs['strategy'])
    basis = next(label for label, key in BASES.items() if key == inputs['basis'])
    st.subheader('Your Historical Simulation')
    st.caption(f"{name} · {basis} · {inputs['start_date']} to {inputs['end_date']}. Results describe the submitted configuration; submit again to apply changes.")
    for col, label, value in zip(st.columns(3), ['Initial Investment', 'Final Portfolio Value', 'Profit / Loss'],
                                 [inputs['initial_capital'], portfolio.get('final_capital_eur'), portfolio.get('profit_loss_eur')]):
        col.metric(label, money(value))
    for col, label, value in zip(st.columns(3), ['Cumulative Return', 'Buy & Hold Final Value', 'Difference vs Buy & Hold'],
                                 [percentage(portfolio.get('cumulative_return')), money(benchmark.get('final_capital_eur')),
                                  money(result['comparison_minus_buy_hold'].get('final_capital_eur'))]):
        col.metric(label, value)
    st.subheader('Portfolio Value')
    st.altair_chart(series_chart(result['series'], {'portfolio_value_eur': 'Selected Strategy', 'buy_hold_value_eur': 'Buy & Hold'}, 'Portfolio Value (EUR)'), use_container_width=True)
    st.caption('Both series start at the same initial capital. Hover for values; scroll to zoom and drag to pan.')
    st.subheader('Drawdown')
    if all(row.get('portfolio_drawdown') is not None and row.get('buy_hold_drawdown') is not None for row in result['series']):
        st.altair_chart(series_chart(result['series'], {'portfolio_drawdown': 'Selected Strategy', 'buy_hold_drawdown': 'Buy & Hold'}, 'Drawdown', True), use_container_width=True)
    else:
        st.info('Drawdown series is unavailable from this API version.')
    st.subheader('Historical Exposure')
    exposures = [row for row in result['series'] if row.get('applied_exposure') is not None and row.get('cash_exposure') is not None]
    if exposures:
        st.altair_chart(series_chart(exposures, {'applied_exposure': 'Equity Exposure', 'cash_exposure': 'Uninvested Cash'}, 'Allocation', True), use_container_width=True)
    else:
        st.info('Applied exposure is unavailable for this sample.')
    st.caption('Applied equity exposure belongs to each return session. The remainder is hypothetical uninvested cash earning zero. The capital anchor has no realised exposure observation. These are historical model allocations, not executed trades.')
    st.subheader('Risk and Trading Costs')
    rows = []
    for label, key in [('Annualized Volatility', 'annualized_volatility'), ('Daily Expected Shortfall / CVaR (95%)', 'daily_cvar_95'), ('Maximum Drawdown', 'maximum_drawdown')]:
        rows.append({'Metric': label, 'Selected Strategy': percentage(portfolio.get(key)), 'Buy & Hold': percentage(benchmark.get(key))})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    costs = result['costs_and_turnover']
    turnover = costs.get('total_turnover_exposure_units')
    st.write(f"Total turnover: {turnover:.2f} exposure units." if turnover is not None else 'Total turnover: unavailable.')
    deducted = costs.get('deducted_cost_log_return')
    st.write(f"Modeled cost deduction: {deducted:.6f} log return." if deducted is not None else 'Modeled cost deduction: unavailable.')
    st.caption('One turnover exposure unit is a 100 percentage-point allocation change. Cost totals are log-return deductions, not EUR invoices. Gross mode deducts no costs; Buy & Hold has no modeled trading costs. Daily CVaR is a signed log return; values nearer zero represent less severe losses. Risk metrics remain unavailable when there is insufficient history.')
    render_interpretation(result)
    with st.expander('Simulation Assumptions and Methodology'):
        st.write('Investment starts at the selected session close: its return is excluded; returns through the final session close are included. Drawdown includes the initial capital anchor. Published exposures already apply prior-close information once, without look-ahead.')
        st.write('Net mode replays stored net returns without a second charge. It omits fresh entry/exit charges, ETF tracking costs, financing, spreads, slippage, taxes and real broker commissions. Published boundary rebalancing costs are retained; this is not a new trade execution model.')
        st.write('The IBEX index is not directly tradable. This simulation does not represent an investment in an executable IBEX instrument. Historical simulations are not investment advice and do not guarantee capital preservation or future outcomes.')
        for assumption in result.get('assumptions', []):
            st.caption(assumption)


def render_investment_simulator(api_url, load_sessions, technical_publications):
    st.subheader('Investment Simulator')
    st.write('Explore the historical trade-off between equity returns and downside risk with your hypothetical investment.')
    st.caption('Investment starts at the selected session close. That session return is excluded; returns through the ending session close are included.')
    result = st.session_state.get('investment_simulation_result')
    try:
        payload = load_sessions()
        dates = [row['date'] for row in payload['sessions']]
        if not dates or dates != sorted(set(dates)):
            raise ValueError('No valid published trading sessions.')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        st.warning('Published trading sessions are unavailable. Check the API and publication before running a simulation.')
        dates = []
    if dates:
        st.caption(f"Available published trading sessions: {dates[0]} to {dates[-1]}.")
        if result is None and not payload.get('publication', {}).get('is_current'):
            st.warning('Available history is stale or non-current. Simulations replay historical data, not current market conditions.')
        with st.form('investment_simulation_form'):
            col1, col2 = st.columns(2)
            capital = col1.number_input('Initial Investment (EUR)', min_value=0., max_value=MAX_CAPITAL_EUR,
                                       value=10_000., step=100., key='sim_capital')
            strategy = col2.selectbox('Investment Strategy', list(STRATEGIES), index=1, key='sim_strategy')
            col1, col2 = st.columns(2)
            start = col1.selectbox('Starting Trading Session', dates, index=0, key='sim_start')
            end = col2.selectbox('Ending Trading Session', dates, index=len(dates) - 1, key='sim_end')
            basis = st.radio('Simulation Performance Basis', list(BASES), index=1, horizontal=True, key='sim_basis')
            submitted = st.form_submit_button('Run Historical Simulation', key='sim_submit')
        if submitted:
            result = None
            st.session_state.pop('investment_simulation_result', None)
            if not math.isfinite(capital) or capital <= 0:
                st.error('Initial investment must be strictly positive and finite.')
            elif start > end:
                st.error('Starting session must be on or before the ending session.')
            else:
                parameters = dict(initial_capital=capital, start_date=start, end_date=end,
                                  strategy=STRATEGIES[strategy], basis=BASES[basis])
                try:
                    with st.spinner('Running historical simulation…'):
                        response = requests.get(f'{api_url}/investment-simulation', params=parameters, timeout=30)
                        response.raise_for_status()
                        result = validate_response(response.json(), parameters)
                    st.session_state['investment_simulation_result'] = result
                except requests.HTTPError as exc:
                    code = exc.response.status_code if exc.response is not None else None
                    message = {422: 'The simulation inputs or selected window were rejected. Review the investment amount and published dates.',
                               503: 'A complete validated publication is unavailable. Try again when the API publication is available.'}
                    st.error(message.get(code, 'The simulation API could not complete this request. Please try again.'))
                    result = None
                except (requests.RequestException, ValueError, KeyError, TypeError):
                    st.error('The simulation response is unavailable or incomplete. No results have been estimated.')
                    result = None
    if result is not None:
        publication = result['publication']
        technical_publications['Investment Simulator'] = publication
        latest_publication = payload.get('publication', {}) if dates else {}
        freshness = latest_publication if latest_publication.get('version') == publication.get('version') else publication
        if not freshness.get('is_current'):
            st.warning('This simulation uses a stale or non-current historical publication; it does not represent current market conditions.')
        st.caption(f"Published history freshness: {str(freshness.get('freshness', 'unverified')).replace('_', ' ').title()} · Last published market session: {publication.get('data_date') or 'Unavailable'}.")
        if dates and payload.get('publication', {}).get('version') != publication.get('version'):
            st.info('The publication changed between date selection and simulation, or since these results were saved. Results retain their own historical snapshot; reload for the latest date choices.')
        render_result(result)
