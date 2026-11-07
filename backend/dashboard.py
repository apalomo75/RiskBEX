import inspect
import altair as alt
import streamlit as st
import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
from pathlib import Path

API_URL = os.getenv("RISKBEX_API_URL", "http://127.0.0.1:8000").rstrip("/")
BASE_DIR = Path(__file__).resolve().parent
FIGURES_DIR = BASE_DIR / "figures" / "chapter2"

st.set_page_config(
    page_title="RISKBEX",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --sand: #d6c2a8;
        --sand-soft: #e7d8c5;
        --sand-light: #f3ece3;
        --sand-dark: #b79a77;
        --black: #0f0f0f;
        --charcoal: #171717;
        --panel: rgba(214, 194, 168, 0.06);
        --panel-strong: rgba(214, 194, 168, 0.10);
        --white-soft: #f8f6f2;
        --muted: #a39a8f;
        --border: rgba(214, 194, 168, 0.20);
        --shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
    }

    .stApp {
        background: linear-gradient(180deg, #0f0f0f 0%, #171717 55%, #111111 100%);
        color: var(--white-soft);
    }

    [data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0);
    }

    .block-container {
        max-width: 1320px;
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3, h4, h5, h6, p, label, div, span {
        color: var(--white-soft);
    }

    @keyframes fadeSlideUp {
        from {
            opacity: 0;
            transform: translateY(14px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes softAppear {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }

    .hero-link {
        text-decoration: none !important;
        color: inherit !important;
        display: block;
    }

    .landing-wrapper {
        min-height: 92vh;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: softAppear 0.5s ease-out;
    }

    .landing-box {
        width: 100%;
        min-height: 84vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background:
            radial-gradient(circle at top left, rgba(214, 194, 168, 0.18), transparent 35%),
            linear-gradient(135deg, rgba(214, 194, 168, 0.17), rgba(214, 194, 168, 0.04));
        border: 1px solid var(--border);
        border-radius: 32px;
        box-shadow: var(--shadow);
        padding: 3.2rem;
        cursor: pointer;
        transition: transform 0.22s ease, box-shadow 0.22s ease, border 0.22s ease;
        overflow: hidden;
        position: relative;
    }

    .landing-box:hover {
        transform: translateY(-3px);
        box-shadow: 0 20px 42px rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(214, 194, 168, 0.34);
    }

    .landing-box::after {
        content: "";
        position: absolute;
        right: -80px;
        bottom: -80px;
        width: 260px;
        height: 260px;
        background: radial-gradient(circle, rgba(214, 194, 168, 0.10), transparent 70%);
        border-radius: 50%;
        pointer-events: none;
    }

    .landing-content {
        max-width: 980px;
        animation: fadeSlideUp 0.7s ease-out;
        position: relative;
        z-index: 2;
    }

    .landing-kicker {
        display: inline-block;
        background: rgba(214, 194, 168, 0.14);
        color: var(--sand-soft);
        border: 1px solid rgba(214, 194, 168, 0.25);
        border-radius: 999px;
        padding: 0.45rem 0.95rem;
        font-size: 0.84rem;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }

    .landing-title {
        font-size: 4.3rem;
        font-weight: 800;
        line-height: 1.01;
        margin-bottom: 0.7rem;
        color: var(--sand-light);
    }

    .landing-subline {
        font-size: 1rem;
        color: var(--sand-dark);
        margin-bottom: 1rem;
        letter-spacing: 0.03em;
    }

    .landing-author {
        font-size: 0.98rem;
        color: var(--muted);
        margin-bottom: 1.1rem;
    }

    .landing-subtitle {
        font-size: 1.14rem;
        line-height: 1.78;
        color: #ebe3d9;
        max-width: 900px;
    }

    .landing-badges {
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
        margin-top: 1.5rem;
    }

    .landing-badge {
        display: inline-block;
        background: rgba(214, 194, 168, 0.08);
        border: 1px solid rgba(214, 194, 168, 0.22);
        color: var(--sand-light);
        border-radius: 999px;
        padding: 0.48rem 0.85rem;
        font-size: 0.9rem;
    }

    .landing-hint {
        margin-top: 1.8rem;
        color: var(--muted);
        font-size: 0.95rem;
    }

    .topbar {
        background: linear-gradient(135deg, rgba(214, 194, 168, 0.14), rgba(214, 194, 168, 0.05));
        border: 1px solid var(--border);
        border-radius: 24px;
        box-shadow: var(--shadow);
        padding: 1.25rem 1.4rem;
        margin-bottom: 1.1rem;
        animation: fadeSlideUp 0.45s ease-out;
    }

    .topbar-title {
        font-size: 1.75rem;
        font-weight: 800;
        color: var(--sand-light);
        margin-bottom: 0.15rem;
    }

    .topbar-subtitle {
        font-size: 0.95rem;
        color: var(--muted);
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--sand-soft);
        margin-top: 0.1rem;
        margin-bottom: 0.9rem;
    }

    .status-box {
        border-radius: 18px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
        animation: fadeSlideUp 0.45s ease-out;
    }

    .status-calm {
        background: linear-gradient(90deg, rgba(104, 92, 74, 0.22), rgba(71, 68, 57, 0.16));
    }

    .status-turbulence {
        background: linear-gradient(90deg, rgba(126, 100, 63, 0.22), rgba(90, 74, 49, 0.16));
    }

    .status-stress {
        background: linear-gradient(90deg, rgba(96, 70, 64, 0.24), rgba(71, 53, 49, 0.18));
    }

    .status-title {
        font-weight: 800;
        font-size: 1.05rem;
        margin-bottom: 0.2rem;
        color: var(--sand-light);
    }

    .status-text {
        color: #ece4da;
        font-size: 0.97rem;
        line-height: 1.55;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(214,194,168,0.06));
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 1rem 1rem 0.95rem 1rem;
        box-shadow: var(--shadow);
        min-height: 132px;
        animation: fadeSlideUp 0.5s ease-out;
    }

    .metric-label {
        font-size: 0.82rem;
        color: var(--muted);
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .metric-value {
        font-size: 1.95rem;
        font-weight: 800;
        color: var(--sand-light);
        margin-bottom: 0.2rem;
    }

    .metric-note {
        font-size: 0.92rem;
        color: #ddd4c9;
    }

    .panel-box {
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(214,194,168,0.04));
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 1.15rem 1.15rem 0.85rem 1.15rem;
        box-shadow: var(--shadow);
        margin-bottom: 1rem;
        animation: fadeSlideUp 0.45s ease-out;
    }

    .regime-card {
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: var(--shadow);
        min-height: 178px;
        margin-bottom: 1rem;
        animation: fadeSlideUp 0.45s ease-out;
    }

    .regime-card.low {
        background: linear-gradient(180deg, rgba(102, 170, 120, 0.18), rgba(102, 170, 120, 0.07));
    }

    .regime-card.medium {
        background: linear-gradient(180deg, rgba(210, 164, 80, 0.20), rgba(210, 164, 80, 0.07));
    }

    .regime-card.high {
        background: linear-gradient(180deg, rgba(190, 90, 84, 0.20), rgba(190, 90, 84, 0.07));
    }

    .regime-card-title {
        color: var(--muted);
        font-size: 0.82rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }

    .regime-card-label {
        color: var(--sand-light);
        font-size: 1.65rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
    }

    .regime-card-detail {
        color: #ddd4c9;
        font-size: 0.92rem;
        line-height: 1.55;
    }

    .split-badge {
        display: inline-block;
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.38rem 0.75rem;
        background: rgba(214, 194, 168, 0.10);
        color: var(--sand-light);
        font-size: 0.86rem;
        margin-bottom: 0.75rem;
    }

    .uncertainty-note {
        color: #ddd4c9;
        font-size: 0.92rem;
        line-height: 1.55;
        margin-top: 0.4rem;
    }

    .soft-caption {
        color: var(--muted);
        font-size: 0.92rem;
    }

    .tab-panel {
        animation: fadeSlideUp 0.35s ease-out;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.6rem;
        margin-top: 0.35rem;
        margin-bottom: 1rem;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(214, 194, 168, 0.08);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.52rem 1rem;
        color: var(--sand-light);
        transition: all 0.18s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(214, 194, 168, 0.14);
        transform: translateY(-1px);
    }

    .stTabs [aria-selected="true"] {
        background: rgba(214, 194, 168, 0.18) !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--sand) 0%, #b79a77 100%);
        color: #111111;
        border: none;
        border-radius: 999px;
        padding: 0.65rem 1.1rem;
        font-weight: 700;
        box-shadow: var(--shadow);
    }

    .stRadio > div {
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(214,194,168,0.04));
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.55rem 0.75rem;
        margin-bottom: 0.85rem;
    }

    .stRadio [role="radiogroup"] {
        gap: 0.35rem;
    }

    .stRadio [role="radio"] {
        background: rgba(214, 194, 168, 0.08);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.4rem 0.9rem;
    }

    .stRadio [role="radio"] * {
        color: #f5efe6 !important;
    }

    .footer-note {
        margin-top: 1rem;
        font-size: 0.9rem;
        color: var(--muted);
    }

    div[data-testid="stPopover"] > div {
        background: #161616 !important;
        border: 1px solid rgba(214, 194, 168, 0.22) !important;
        border-radius: 18px !important;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35) !important;
    }

    div[data-testid="stPopoverContent"] {
        background: #161616 !important;
        border: 1px solid rgba(214, 194, 168, 0.22) !important;
    }

    div[data-testid="stPopover"] * {
        color: #f3ece3 !important;
    }

    div[data-testid="stPopover"] h1,
    div[data-testid="stPopover"] h2,
    div[data-testid="stPopover"] h3,
    div[data-testid="stPopover"] h4,
    div[data-testid="stPopover"] p,
    div[data-testid="stPopover"] div,
    div[data-testid="stPopover"] span,
    div[data-testid="stPopover"] li {
        color: #f3ece3 !important;
    }

    .popover-title {
        font-size: 1rem;
        font-weight: 800;
        color: #f3ece3 !important;
        margin-bottom: 0.45rem;
    }

    .popover-text {
        font-size: 0.95rem;
        line-height: 1.65;
        color: #e7d8c5 !important;
    }

    .stPopover button {
        border-radius: 999px !important;
        background: rgba(214, 194, 168, 0.10) !important;
        border: 1px solid rgba(214, 194, 168, 0.22) !important;
        color: #f3ece3 !important;
        min-height: 2rem !important;
        min-width: 2rem !important;
        padding: 0.1rem 0.45rem !important;
        font-weight: 700 !important;
    }

    .stPopover button:hover {
        background: rgba(214, 194, 168, 0.18) !important;
        border: 1px solid rgba(214, 194, 168, 0.34) !important;
    }

    div[data-testid="stAlert"] {
        background: linear-gradient(90deg, rgba(88, 79, 64, 0.22), rgba(60, 56, 48, 0.14)) !important;
        border: 1px solid rgba(214, 194, 168, 0.16) !important;
        color: #f3ece3 !important;
        border-radius: 14px !important;
    }

    div[data-testid="stAlert"] * {
        color: #f3ece3 !important;
    }

    div[data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, rgba(183, 154, 119, 0.95), rgba(214, 194, 168, 0.78)) !important;
    }

    div[data-testid="stProgressBar"] {
        background: rgba(214, 194, 168, 0.12) !important;
        border-radius: 999px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_landing():
    st.markdown("""
    <div class="topbar">
        <div class="landing-kicker">IBEX 35 · Quantitative Risk Intelligence</div>
        <h1 class="landing-title">RISKBEX</h1>
        <h2>Understand risk. Adapt exposure.</h2>
        <p class="landing-subtitle">Monitor IBEX 35 risk through market regimes,
        Machine Learning and Conditional Value at Risk. Explore quantitative signals,
        compare strategies and analyse their historical performance.</p>
        <p class="landing-author">Alejandro Palomo Morales</p>
    </div>
    """, unsafe_allow_html=True)
    for col, page, description in zip(st.columns(3),
            ["Monitor", "Explore", "Models"],
            ["Market conditions and operational signals.",
             "Interactive risk history and portfolio exposure.",
             "Understand Markov regimes, XGBoost and CVaR."]):
        with col:
            st.markdown(f"### {page}")
            st.write(description)
            st.link_button(f"Open {page}", f"?enter=1&view={page}")


def metric_card(label: str, value: str, note: str):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_box(regime_label: str, risk_score: float):
    regime = (regime_label or "").lower()

    if regime == "stress":
        css_class = "status-box status-stress"
        title = "High Risk"
        text = (
            "Market conditions indicate elevated instability, stronger downside pressure "
            "and less favourable conditions for risk exposure."
        )
    elif regime == "turbulence":
        css_class = "status-box status-turbulence"
        title = "Medium Risk"
        text = (
            "The market is in a medium risk phase. Conditions are "
            "not extreme, but signs of stress are emerging."
        )
    else:
        css_class = "status-box status-calm"
        title = "Low Risk"
        text = (
            "The market is relatively stable, with more contained downside risk "
            "and lower overall pressure."
        )

    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="status-title">{title}</div>
            <div class="status-text">
                Detected Regime: <b>{regime_label.upper()}</b><br>
                Aggregate Relative Risk: <b>{int(risk_score)} / 100</b>
            </div>
            <div class="status-text" style="margin-top: 0.5rem;">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=30)
def load_latest_data():
    response = requests.get(f"{API_URL}/latest-risk", timeout=10)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("publication") or not data.get("signal"):
        raise ValueError("The API did not return a validated operational publication.")
    return data


def risk_label(value):
    return {"low_risk": "Low Risk", "medium_risk": "Medium Risk",
            "high_risk": "High Risk", "calm": "Low Risk",
            "turbulence": "Medium Risk", "stress": "High Risk"}.get(
                str(value).lower(), str(value or "N/A"))


def presentation_frame(frame):
    display = frame.copy()
    for column in ["economic_label", "regime_label"]:
        if column in display:
            display[column] = display[column].map(risk_label)
    return display.rename(columns={column: column.replace("_", " ").title() for column in display.columns})


def select_period(frame, key):
    if frame.empty:
        return frame
    period = st.selectbox("Observation Period", ["Last 3 Months", "Last Year", "All Available"], key=key)
    days = {"Last 3 Months": 92, "Last Year": 366}.get(period)
    st.caption(f"Available history ends on {frame.date.max():%Y-%m-%d}; periods are measured from that session.")
    return frame if days is None else frame[frame.date >= frame.date.max() - pd.Timedelta(days=days)]


def render_price_regimes(frame):
    required = {"date", "ibex_close", "regime_label"}
    if frame.empty or not required.issubset(frame.columns):
        st.caption("IBEX 35 price and regime chart unavailable: aligned price history is not published.")
        return
    chart_data = frame.dropna(subset=list(required)).copy()
    if chart_data.empty:
        st.caption("No aligned prices and regimes are available for this period.")
        return
    chart_data["Market Regime"] = chart_data.regime_label.map(risk_label)
    chart_data = chart_data.rename(columns={"ibex_close": "IBEX 35 Close", "date": "Session"})
    base = alt.Chart(chart_data).encode(x=alt.X("Session:T", title="Market Session"),
        y=alt.Y("IBEX 35 Close:Q", scale=alt.Scale(zero=False)))
    chart = base.mark_line(color="#d6c2a8").encode() + base.mark_circle(size=28).encode(
        color=alt.Color("Market Regime:N", scale=alt.Scale(
            domain=["Low Risk", "Medium Risk", "High Risk"], range=["#7fb58a", "#d2a450", "#be5a54"])),
        tooltip=[alt.Tooltip("Session:T"), alt.Tooltip("IBEX 35 Close:Q", format=",.2f"), "Market Regime:N"])
    st.subheader("IBEX 35 and Market Regimes")
    st.altair_chart(chart.interactive(), use_container_width=True)


def render_operational_overview(data):
    st.subheader("MAIN Operational Monitor")
    publication = data.get("publication") or {}
    signal = data.get("signal") or {}
    if not publication or not signal:
        st.warning("No verifiable operational publication is available. Legacy data must not be treated as current.")
        return
    freshness = publication.get("freshness")
    labels = {"current": "Current", "stale": "Stale Market Data",
              "simulated": "Simulated Data", "historical": "Historical Data"}
    status = labels.get(freshness, "Unverified Freshness")
    if freshness == "current" and publication.get("is_current") is True:
        st.success(f"Data Freshness: {status}")
    else:
        st.warning(f"Data Freshness: {status}. This publication does not represent current market conditions. "
                   f"Expected Session: {publication.get('expected_data_date') or 'N/A'}.")

    def value(item, percentage=False):
        if item is None:
            return "N/A"
        return f"{item:.2%}" if percentage else str(item)

    cols = st.columns(3)
    close = (signal.get("market") or {}).get("ibex_close")
    cols[0].metric("Last Market Close · IBEX 35", f"{close:,.2f}" if close is not None else "N/A")
    cols[1].metric("Last Market Data Date", value(publication.get("data_date") or signal.get("last_valid_session")))
    cols[2].metric("Forecast Target Session", value(publication.get("target_session_date")))
    for col, key, title, regime_key in zip(st.columns(2), ["markov", "xgboost"],
            ["Current Market Regime · Markov", "Next-Session Regime Forecast · XGBoost"],
            ["regime", "regime_pred"]):
        model = signal.get(key) or {}
        with col:
            st.markdown(f"**{title}**")
            st.write(f"Regime: {value(model.get(regime_key))} · {risk_label(model.get('economic_label'))}")
            probabilities = model.get("probabilities") or {}
            for regime in range(3):
                st.write(f"P(Regime {regime}): {value(probabilities.get(str(regime)), True)}")
    st.caption("Target exposures from simulated quantitative strategies; these are not personalised investment recommendations.")
    targets = signal.get("target_exposures") or {}
    for col, key, label in zip(st.columns(3),
            ["regime_based", "ml_hard", "ml_probability_weighted"],
            ["Regime-Based Strategy", "ML Hard Strategy", "Probability-Weighted Strategy"]):
        col.metric(f"Target Portfolio Exposure {label}", value(targets.get(key), True))
    st.markdown("**How the decision is formed.** The Regime-Based Strategy uses the filtered Markov state. "
                "ML Hard Strategy uses the most likely XGBoost next-session state. "
                "Probability-Weighted Strategy combines regime exposures using forecast probabilities. "
                "Targets are for the next market session; applied historical exposure may differ.")
    update = publication.get("update_status") or {}
    st.caption(f"Update Status: {str(update.get('status', 'Not reported')).replace('_', ' ').title()} · "
               f"Publication Generated: {publication.get('generated_at') or 'N/A'}")
    st.caption(f"Last Successful Update: {publication.get('last_successful_update') or 'N/A'}")
    st.caption(f"Frozen Model Package: {value(publication.get('model_version'))} · "
               f"Source: {value(publication.get('source_mode'))}")


@st.cache_data(ttl=30)
def load_historical_data():
    response = requests.get(f"{API_URL}/historical-risk?limit=all", timeout=10)
    response.raise_for_status()
    hist_data = response.json()
    df = pd.DataFrame(hist_data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df


@st.cache_data(ttl=30)
def fetch_regime_endpoint(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_regime_endpoint_safe(path: str, fallback, label: str):
    try:
        return fetch_regime_endpoint(path)
    except Exception as e:
        st.warning(f"Unable to load {label}.")
        st.caption("Check API availability and the selected publication.")
        return fallback


@st.cache_data(ttl=30)
def fetch_backtesting_endpoint(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_backtesting_endpoint_safe(path: str, fallback, label: str):
    try:
        return fetch_backtesting_endpoint(path)
    except Exception as e:
        st.warning(
            f"Unable to load {label}. The requested backtesting outputs are unavailable."
        )
        st.caption("Check API availability and the selected publication.")
        return fallback


@st.cache_data(ttl=30)
def fetch_tail_endpoint(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_tail_endpoint_safe(path: str, fallback, label: str):
    try:
        return fetch_tail_endpoint(path)
    except Exception as e:
        st.warning(
            f"Unable to load {label}. Tail risk outputs are unavailable. "
            "Run scripts/run_tail_analysis.py."
        )
        st.caption("Check API availability and the selected publication.")
        return fallback


def regime_card_class(economic_label: str):
    label = (economic_label or "").lower()
    if "low" in label:
        return "low"
    if "high" in label:
        return "high"
    return "medium"


def split_description(split: str):
    if split == "ROBUST":
        return "Temporal Robustness Evaluation"
    return "Primary Split"


def render_split_badge(split: str):
    st.markdown(
        f'<span class="split-badge">{split} · {split_description(split)}</span>',
        unsafe_allow_html=True,
    )


def render_regime_card(title: str, payload: dict):
    if not payload:
        st.info("No evaluated state is available.")
        return
    probability = float(payload.get("dominant_probability", 0.0))
    card_class = regime_card_class(payload.get("economic_label", ""))
    st.markdown(
        f"""
        <div class="regime-card {card_class}">
            <div class="regime-card-title">{title}</div>
            <div class="regime-card-label">{risk_label(payload.get("economic_label"))}</div>
            <div class="regime-card-detail">
                Dominant Probability<br>
                <b>{probability:.1%}</b><br>
                Risk Order: <b>{int(payload.get("risk_order", 0))}</b><br>
                Date: <b>{payload.get("date", "N/A")}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def regime_probabilities(record):
    return [
        float(record.get("p_regime_0", 0.0)),
        float(record.get("p_regime_1", 0.0)),
        float(record.get("p_regime_2", 0.0)),
    ]


def confidence_label(dominant_probability):
    if dominant_probability >= 0.80:
        return "High Confidence"
    if dominant_probability >= 0.60:
        return "Moderate Confidence"
    return "Transition Zone"


def uncertainty_metrics(record):
    probabilities = sorted(regime_probabilities(record), reverse=True)
    dominant_probability = probabilities[0]
    second_probability = probabilities[1]
    probability_gap = dominant_probability - second_probability
    return {
        "dominant_probability": dominant_probability,
        "second_probability": second_probability,
        "probability_gap": probability_gap,
        "confidence_label": confidence_label(dominant_probability),
    }


def render_uncertainty_card(split: str, latest_payload: dict):
    if not latest_payload:
        st.info("Insufficient data to assess probability uncertainty.")
        return
    metrics = uncertainty_metrics(latest_payload)
    gap_note = (
        "The narrow probability gap indicates substantial uncertainty between risk states."
        if metrics["probability_gap"] < 0.20
        else "The dominant regime has a clear probability lead over the second state."
    )
    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Model Confidence · {split}</div>
            <div class="regime-card-label">{metrics["confidence_label"]}</div>
            <div class="regime-card-detail">
                Dominant Probability: <b>{metrics["dominant_probability"]:.1%}</b><br>
                Second-Highest Probability: <b>{metrics["second_probability"]:.1%}</b><br>
                Probability Gap: <b>{metrics["probability_gap"]:.1%}</b>
            </div>
            <div class="uncertainty-note">
                {gap_note}<br>
                Filtered probabilities describe gradual transitions between risk states.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def add_uncertainty_columns(history_df):
    working_df = history_df.copy()
    probability_columns = ["p_regime_0", "p_regime_1", "p_regime_2"]
    sorted_probabilities = working_df[probability_columns].apply(
        lambda row: sorted([float(value) for value in row], reverse=True),
        axis=1,
    )
    working_df["dominant_probability"] = sorted_probabilities.apply(lambda values: values[0])
    working_df["second_probability"] = sorted_probabilities.apply(lambda values: values[1])
    working_df["probability_gap"] = (
        working_df["dominant_probability"] - working_df["second_probability"]
    )
    return working_df


def render_uncertainty_chart(history_df):
    if history_df.empty:
        st.info("Insufficient history to display model uncertainty.")
        return
    uncertainty_df = add_uncertainty_columns(history_df)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(
        uncertainty_df["date"],
        uncertainty_df["dominant_probability"],
        color="#d6c2a8",
        linewidth=2.0,
        label="Dominant Probability",
    )
    ax.plot(
        uncertainty_df["date"],
        uncertainty_df["probability_gap"],
        color="#7f8f7a",
        linewidth=1.8,
        label="Dominant–Second Probability Gap",
    )
    ax.axhline(0.80, color="#7fb58a", linewidth=1.0, linestyle="--", alpha=0.55)
    ax.axhline(0.60, color="#d2a450", linewidth=1.0, linestyle="--", alpha=0.55)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Probability")
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def prepare_regime_history(records):
    regime_df = pd.DataFrame(records)
    if regime_df.empty:
        return regime_df
    regime_df["date"] = pd.to_datetime(regime_df["date"])
    return regime_df.sort_values("date").reset_index(drop=True)


def style_regime_axis(ax):
    ax.set_facecolor("#171717")
    ax.figure.set_facecolor("#171717")
    ax.tick_params(colors="#ddd4c9")
    ax.xaxis.label.set_color("#ddd4c9")
    ax.yaxis.label.set_color("#ddd4c9")
    ax.title.set_color("#f3ece3")
    for spine in ax.spines.values():
        spine.set_color("#4a4035")
    ax.grid(color="#3a332d", alpha=0.35)


def render_regime_timeline(history_df):
    color_map = {
        1: "#7fb58a",
        2: "#d2a450",
        3: "#be5a54",
    }
    fig, ax = plt.subplots(figsize=(10, 2.8))
    colors = history_df["risk_order"].map(color_map).fillna("#d6c2a8")
    ax.scatter(
        history_df["date"],
        history_df["risk_order"],
        c=colors,
        s=22,
        alpha=0.9,
        linewidths=0,
    )
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(["Low Risk", "Medium Risk", "High Risk"])
    ax.set_xlabel("")
    ax.set_ylabel("")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_transition_heatmap(transition_records):
    transition_df = pd.DataFrame(transition_records)
    if transition_df.empty:
        st.info("No transition matrix is available.")
        return

    labels_df = (
        transition_df[["from_label", "from_risk_order"]]
        .drop_duplicates()
        .sort_values("from_risk_order")
    )
    labels = labels_df["from_label"].tolist()
    matrix = transition_df.pivot(
        index="from_label",
        columns="to_label",
        values="transition_probability",
    ).reindex(index=labels, columns=labels)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    image = ax.imshow(matrix, cmap="YlOrBr", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels([risk_label(label) for label in labels], rotation=25, ha="right")
    ax.set_yticklabels([risk_label(label) for label in labels])
    ax.set_xlabel("Destination")
    ax.set_ylabel("Source")
    for row_idx in range(len(labels)):
        for col_idx in range(len(labels)):
            value = matrix.iloc[row_idx, col_idx]
            ax.text(
                col_idx,
                row_idx,
                f"{value:.1%}",
                ha="center",
                va="center",
                color="#f8f6f2" if value < 0.55 else "#171717",
                fontsize=9,
                fontweight="bold",
            )
    style_regime_axis(ax)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.ax.tick_params(colors="#ddd4c9")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_duration_bars(duration_records):
    duration_df = pd.DataFrame(duration_records)
    if duration_df.empty:
        st.info("No regime duration data is available.")
        return
    duration_df = duration_df.sort_values("risk_order")
    labels = duration_df["economic_label"].tolist()
    x_positions = range(len(labels))
    width = 0.34

    fig, ax = plt.subplots(figsize=(8.8, 3.4))
    mean_positions = [pos - width / 2 for pos in x_positions]
    median_positions = [pos + width / 2 for pos in x_positions]
    ax.bar(
        mean_positions,
        duration_df["mean_duration_trading_days"],
        width=width,
        label="Mean",
        color="#d6c2a8",
    )
    ax.bar(
        median_positions,
        duration_df["median_duration_trading_days"],
        width=width,
        label="Median",
        color="#7f8f7a",
    )
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels([risk_label(label) for label in labels])
    ax.set_ylabel("Trading Sessions")
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def info_popover(title: str, text: str):
    with st.popover("ℹ"):
        st.markdown(
            f"""
            <div class="popover-title">{title}</div>
            <div class="popover-text">{text}</div>
            """,
            unsafe_allow_html=True,
        )


def panel_header(title: str, info_title: str, info_text: str):
    col1, col2 = st.columns([20, 1])
    with col1:
        st.subheader(title)
    with col2:
        info_popover(info_title, info_text)


def prepare_backtest_results(records):
    backtest_df = pd.DataFrame(records)
    if backtest_df.empty:
        return backtest_df
    backtest_df["date"] = pd.to_datetime(backtest_df["date"])
    return backtest_df.sort_values("date").reset_index(drop=True)


def prepare_backtest_metrics(records, sample: str):
    metrics_df = pd.DataFrame(records)
    if metrics_df.empty:
        return metrics_df
    return metrics_df[metrics_df["sample"] == sample].reset_index(drop=True)


def format_pct(value):
    return f"{float(value):.2%}"


def strategy_metric_value(metrics_df, strategy, column):
    row = metrics_df[metrics_df["strategy"] == strategy]
    if row.empty:
        return None
    return float(row.iloc[0][column])


def metric_delta_note(buy_hold_value, strategy_value, metric_name, negative_is_better=False):
    if buy_hold_value is None or strategy_value is None:
        return "Comparison unavailable."
    delta = strategy_value - buy_hold_value
    if metric_name in {"VaR 95", "CVaR 95", "Maximum Drawdown"}:
        if delta > 0:
            return f"Less severe than Buy & Hold by {abs(delta):.2%}."
        if delta < 0:
            return f"More severe than Buy & Hold by {abs(delta):.2%}."
        return "No difference from Buy & Hold."
    if negative_is_better:
        if delta < 0:
            return f"Reduction relative to Buy & Hold of {abs(delta):.2%}."
        if delta > 0:
            return f"Increase relative to Buy & Hold of {abs(delta):.2%}."
        return "No difference from Buy & Hold."
    if delta > 0:
        return f"Higher than Buy & Hold by {abs(delta):.2%}."
    if delta < 0:
        return f"Lower than Buy & Hold by {abs(delta):.2%}."
    return "No difference from Buy & Hold."


def render_backtest_metric_cards(metrics_df):
    if metrics_df.empty:
        st.info("No backtesting metrics are available.")
        return

    metrics = [
        ("Total return", "total_return", False),
        ("Annualized volatility", "annualized_volatility", True),
        ("VaR 95", "VaR_95", False),
        ("CVaR 95", "CVaR_95", False),
        ("Maximum Drawdown", "max_drawdown", False),
    ]
    cols = st.columns(len(metrics))
    for col, (label, column, negative_is_better) in zip(cols, metrics):
        buy_hold_value = strategy_metric_value(metrics_df, "Buy & Hold", column)
        strategy_value = strategy_metric_value(metrics_df, "Regime Strategy", column)
        with col:
            metric_card(
                label,
                format_pct(strategy_value) if strategy_value is not None else "N/A",
                metric_delta_note(
                    buy_hold_value,
                    strategy_value,
                    label,
                    negative_is_better=negative_is_better,
                ),
            )


def render_defensive_reading(metrics_df):
    if metrics_df.empty:
        return
    buy_hold = metrics_df[metrics_df["strategy"] == "Buy & Hold"]
    strategy = metrics_df[metrics_df["strategy"] == "Regime Strategy"]
    if buy_hold.empty or strategy.empty:
        return

    buy_hold = buy_hold.iloc[0]
    strategy = strategy.iloc[0]
    vol_delta = float(strategy["annualized_volatility"] - buy_hold["annualized_volatility"])
    cvar_delta = float(strategy["CVaR_95"] - buy_hold["CVaR_95"])
    drawdown_delta = float(strategy["max_drawdown"] - buy_hold["max_drawdown"])
    return_delta = float(strategy["total_return"] - buy_hold["total_return"])

    vol_text = (
        f"reduces annualised volatility by {abs(vol_delta):.2%}"
        if vol_delta < 0
        else f"increases annualised volatility by {abs(vol_delta):.2%}"
    )
    cvar_text = (
        f"makes CVaR less severe by {abs(cvar_delta):.2%}"
        if cvar_delta > 0
        else f"makes CVaR more severe by {abs(cvar_delta):.2%}"
    )
    drawdown_text = (
        f"makes maximum drawdown less severe by {abs(drawdown_delta):.2%}"
        if drawdown_delta > 0
        else f"makes maximum drawdown more severe by {abs(drawdown_delta):.2%}"
    )
    return_text = (
        f"with a higher cumulative return of {abs(return_delta):.2%}"
        if return_delta > 0
        else f"with a cumulative return reduction of {abs(return_delta):.2%}"
    )

    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Defensive Interpretation</div>
            <div class="regime-card-detail">
                The adaptive strategy {vol_text}, {cvar_text} and {drawdown_text},
                {return_text}. This is a defensive exposure rule for vulnerable regimes,
                rather than a market timing signal.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_backtest_line_chart(backtest_df, columns, labels, title, ylabel):
    if backtest_df.empty:
        st.info(f"No data is available to display {title.lower()}.")
        return
    fig, ax = plt.subplots(figsize=(10, 3.4))
    colors = ["#d6c2a8", "#7f8f7a", "#be5a54"]
    for column, label, color in zip(columns, labels, colors):
        ax.plot(backtest_df["date"], backtest_df[column], linewidth=2.0, label=label, color=color)
    ax.set_ylabel(ylabel)
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_backtest_exposure(backtest_df):
    if backtest_df.empty:
        st.info("No adaptive exposure data is available.")
        return
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.step(
        backtest_df["date"],
        backtest_df["strategy_exposure"],
        where="post",
        linewidth=2.0,
        color="#d6c2a8",
        label="Regime Strategy exposure",
    )
    ax.set_yticks([0.25, 0.75, 1.0])
    ax.set_ylim(0.15, 1.05)
    ax.set_ylabel("Exposure")
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_backtest_latest(latest_payload):
    if not latest_payload:
        st.info("No evaluated backtest session is available.")
        return
    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Last Evaluated Backtest Session</div>
            <div class="regime-card-label">{risk_label(latest_payload.get("regime_label"))}</div>
            <div class="regime-card-detail">
                Date: <b>{latest_payload.get("date", "N/A")}</b><br>
                Applied Exposure: <b>{float(latest_payload.get("strategy_exposure", 0.0)):.2f}</b><br>
                Target Portfolio Exposure: <b>{float(latest_payload.get("target_exposure", 0.0)):.2f}</b><br>
                Buy & Hold Cumulative Growth: <b>{float(latest_payload.get("benchmark_cum", 0.0)):.2f}x</b><br>
                Strategy Cumulative Growth: <b>{float(latest_payload.get("strategy_cum", 0.0)):.2f}x</b><br>
                Strategy Drawdown: <b>{float(latest_payload.get("strategy_drawdown", 0.0)):.2%}</b>
            </div>
            <div class="uncertainty-note">
                {latest_payload.get("methodology", "")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def prepare_tail_events(records):
    tail_df = pd.DataFrame(records)
    if tail_df.empty:
        return tail_df
    tail_df["date"] = pd.to_datetime(tail_df["date"])
    tail_df["stress_tail_event"] = tail_df["stress_tail_event"].astype(bool)
    return tail_df.sort_values("date").reset_index(drop=True)


def prepare_tail_metrics(records, sample: str):
    metrics_df = pd.DataFrame(records)
    if metrics_df.empty:
        return metrics_df
    return metrics_df[metrics_df["sample"] == sample].reset_index(drop=True)


def prepare_tail_threshold(records, sample: str):
    thresholds_df = pd.DataFrame(records)
    if thresholds_df.empty:
        return {}
    sample_rows = thresholds_df[thresholds_df["sample"] == sample]
    if sample_rows.empty:
        return {}
    return sample_rows.iloc[0].to_dict()


def tail_metric_value(metrics_df, strategy, column):
    row = metrics_df[metrics_df["strategy"] == strategy]
    if row.empty:
        return None
    return float(row.iloc[0][column])


def tail_severity_note(buy_hold_value, strategy_value, label, lower_is_better=False):
    if buy_hold_value is None or strategy_value is None:
        return "Comparison unavailable."
    delta = strategy_value - buy_hold_value
    if lower_is_better:
        if delta < 0:
            return f"Lower than Buy & Hold by {abs(delta):.2%}."
        if delta > 0:
            return f"Higher than Buy & Hold by {abs(delta):.2%}."
        return "No difference from Buy & Hold."
    if delta > 0:
        return f"Less severe than Buy & Hold by {abs(delta):.2%}."
    if delta < 0:
        return f"More severe than Buy & Hold by {abs(delta):.2%}."
    return "No difference from Buy & Hold."


def render_tail_metric_cards(threshold_payload, metrics_df):
    if not threshold_payload or metrics_df.empty:
        st.info("No tail risk metrics are available.")
        return
    cvar_buy_hold = tail_metric_value(metrics_df, "Buy & Hold", "tail_CVaR_95")
    cvar_strategy = tail_metric_value(metrics_df, "Regime Strategy", "tail_CVaR_95")

    cards = [
        (
            "Tail threshold",
            format_pct(threshold_payload.get("tail_threshold", 0.0)),
            "Threshold for the worst 5% of Out-of-Sample sessions.",
        ),
        (
            "Extreme Events",
            str(int(threshold_payload.get("n_tail_events", 0))),
            "Sessions classified as left tail events.",
        ),
        (
            "Tail share",
            format_pct(threshold_payload.get("tail_share", 0.0)),
            "Out-of-Sample share below the threshold.",
        ),
        (
            "Worst market return",
            format_pct(threshold_payload.get("worst_market_return", 0.0)),
            "Worst daily market return.",
        ),
        (
            "Tail CVaR Buy & Hold",
            format_pct(cvar_buy_hold) if cvar_buy_hold is not None else "N/A",
            "Average tail loss severity.",
        ),
        (
            "Tail CVaR Regime Strategy",
            format_pct(cvar_strategy) if cvar_strategy is not None else "N/A",
            tail_severity_note(cvar_buy_hold, cvar_strategy, "Tail CVaR"),
        ),
    ]
    cols = st.columns(3)
    for index, (label, value, note) in enumerate(cards):
        with cols[index % 3]:
            metric_card(label, value, note)


def render_tail_defensive_reading(metrics_df):
    if metrics_df.empty:
        return
    comparisons = [
        ("mean_tail_return", "Mean Tail Return", False),
        ("tail_volatility", "Tail Volatility", True),
        ("tail_CVaR_95", "Tail CVaR", False),
        ("tail_total_return", "Cumulative Return on Tail Sessions", False),
        ("max_backtest_drawdown_on_tail_days", "Drawdown Observed on Tail Sessions", False),
    ]
    fragments = []
    for column, label, lower_is_better in comparisons:
        buy_hold_value = tail_metric_value(metrics_df, "Buy & Hold", column)
        strategy_value = tail_metric_value(metrics_df, "Regime Strategy", column)
        fragments.append(
            f"{label}: {tail_severity_note(buy_hold_value, strategy_value, label, lower_is_better).lower()}"
        )

    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Defensive Tail Risk Comparison</div>
            <div class="regime-card-detail">
                Both strategies are compared on the same extreme market sessions.
                Differences between strategies show how reduced exposure
                affects loss severity during left tail events.<br><br>
                {'<br>'.join(fragments)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tail_event_timeline(tail_df, threshold):
    if tail_df.empty:
        st.info("No tail events are available.")
        return
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.plot(
        tail_df["date"],
        tail_df["ret_1d"],
        linewidth=1.0,
        color="#8d8479",
        alpha=0.65,
        label="Daily Market Return",
    )
    tail_days = tail_df[tail_df["stress_tail_event"]]
    ax.scatter(
        tail_days["date"],
        tail_days["ret_1d"],
        color="#be5a54",
        s=28,
        alpha=0.95,
        label="Extreme Event",
        zorder=3,
    )
    ax.axhline(float(threshold), color="#d6c2a8", linestyle="--", linewidth=1.2, label="Tail threshold")
    ax.set_ylabel("Log return")
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_tail_cumulative_chart(tail_df):
    if tail_df.empty:
        st.info("No cumulative tail return data is available.")
        return
    tail_only_df = tail_df[tail_df["stress_tail_event"]].copy()
    if tail_only_df.empty:
        st.info("No tail sessions are available for cumulative returns.")
        return
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.plot(
        tail_only_df["date"],
        tail_only_df["benchmark_tail_cum"],
        linewidth=2.0,
        color="#d6c2a8",
        label="Buy & Hold",
    )
    ax.plot(
        tail_only_df["date"],
        tail_only_df["strategy_tail_cum"],
        linewidth=2.0,
        color="#7f8f7a",
        label="Regime Strategy",
    )
    ax.set_ylabel("Tail cumulative")
    ax.legend(facecolor="#171717", edgecolor="#4a4035", labelcolor="#ddd4c9")
    style_regime_axis(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_tail_cvar_bars(metrics_df):
    if metrics_df.empty:
        st.info("No tail CVaR data is available.")
        return
    labels = ["Buy & Hold", "Regime Strategy"]
    values = [
        tail_metric_value(metrics_df, "Buy & Hold", "tail_CVaR_95"),
        tail_metric_value(metrics_df, "Regime Strategy", "tail_CVaR_95"),
    ]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar(labels, values, color=["#d6c2a8", "#7f8f7a"])
    ax.set_ylabel("Tail CVaR 95")
    style_regime_axis(ax)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_tail_regime_composition(tail_df):
    if tail_df.empty:
        st.info("No regime composition data is available.")
        return
    tail_only_df = tail_df[tail_df["stress_tail_event"]]
    if tail_only_df.empty:
        st.info("No tail sessions are available for regime counts.")
        return
    counts = tail_only_df["regime_label"].value_counts()
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar([risk_label(label) for label in counts.index], counts.values.tolist(), color="#d6c2a8")
    ax.set_ylabel("Number of Sessions")
    style_regime_axis(ax)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_tail_latest(latest_payload):
    if not latest_payload:
        st.info("No evaluated tail risk session is available.")
        return
    is_tail = bool(latest_payload.get("stress_tail_event", False))
    tail_message = (
        "The last evaluated session is an extreme event."
        if is_tail
        else "The last evaluated session is outside the worst 5% of Out-of-Sample sessions."
    )
    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Last Evaluated Session</div>
            <div class="regime-card-label">{risk_label(latest_payload.get("regime_label"))}</div>
            <div class="regime-card-detail">
                Date: <b>{latest_payload.get("date", "N/A")}</b><br>
                Market Return: <b>{float(latest_payload.get("ret_1d", 0.0)):.2%}</b><br>
                Tail threshold: <b>{float(latest_payload.get("tail_threshold", 0.0)):.2%}</b><br>
                Applied Exposure: <b>{float(latest_payload.get("strategy_exposure", 0.0)):.2f}</b><br>
                Buy & Hold return: <b>{float(latest_payload.get("benchmark_return", 0.0)):.2%}</b><br>
                Regime Strategy return: <b>{float(latest_payload.get("strategy_return", 0.0)):.2%}</b><br>
                <b>{tail_message}</b>
            </div>
            <div class="uncertainty-note">
                {latest_payload.get("methodology", "")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=30)
def load_decision_history():
    response = requests.get(f'{API_URL}/decision-explorer', timeout=10)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get('sessions') or not payload.get('mapping') or not payload.get('publication'):
        raise ValueError('Incomplete decision history.')
    return payload


def render_decision_explorer():
    st.subheader('Decision Explorer')
    st.info('Historical Backtest — Not Live Trading Records.')
    try:
        payload = load_decision_history()
    except (requests.RequestException, ValueError):
        st.warning('Verified decision history is unavailable. Check FastAPI and the operational publication.')
        return
    publication = payload['publication']
    if not publication.get('is_current'):
        st.warning('The publication is stale or non-current. Selected decisions are retrospective model targets.')
    st.caption(f"Model Package: {publication.get('model_version', 'N/A')} · Publication: {publication.get('version', 'N/A')} · "
               f"Freshness: {publication.get('freshness', 'unverified').title()}")
    history = pd.DataFrame(payload['sessions'])
    dates = history.date.tolist()
    selected = st.selectbox('Historical Trading Session', dates, index=len(dates) - 1,
                            key='decision_session')
    row = history.loc[history.date == selected].iloc[0]
    cols = st.columns(3)
    cols[0].metric('Market Information Date', selected)
    cols[1].metric('Next Eligible Trading Session', row.next_session_date)
    cols[2].metric('Selected IBEX Close', f'{row.ibex_close:,.2f}' if pd.notna(row.ibex_close) else 'N/A')
    st.caption('Earlier target dates use the next observed market session in this publication. The final target uses its verified exchange calendar.')
    mapping = pd.DataFrame(payload['mapping'])
    label_by_id = mapping.set_index('regime').economic_label
    col_markov, col_ml = st.columns(2)
    col_markov.markdown(f"**Filtered Current State · Markov:** Regime {int(row.regime)} · {risk_label(label_by_id[row.regime])}")
    col_ml.markdown(f"**Predicted Next State · XGBoost:** Regime {int(row.regime_pred)} · {risk_label(label_by_id[row.regime_pred])}")
    probabilities = pd.DataFrame([{'Regime ID': int(item.regime), 'Economic Label': risk_label(item.economic_label),
        'Markov · Filtered Current State': f"{row[f'p_regime_{int(item.regime)}']:.2%}",
        'XGBoost · Predicted Next State': f"{row[f'proba_{int(item.regime)}']:.2%}"} for item in mapping.itertuples()])
    st.dataframe(probabilities, use_container_width=True, hide_index=True)
    st.markdown('**Verified CVaR Exposure Mapping**')
    mapping_display = pd.DataFrame([{'Regime ID': int(item.regime), 'Economic Label': risk_label(item.economic_label),
                                    'CVaR Target': f'{item.target_exposure:.2%}'} for item in mapping.itertuples()])
    st.dataframe(mapping_display, use_container_width=True, hide_index=True)
    exposures = mapping.set_index('regime').target_exposure
    st.markdown(f"**Regime-Based:** filtered Markov Regime {int(row.regime)} → {exposures[row.regime]:.2%}. "
                f"**ML Hard:** predicted next-session Regime {int(row.regime_pred)} → {exposures[row.regime_pred]:.2%}.")
    terms = [f"{row[f'proba_{int(item.regime)}']:.6f} × {item.target_exposure:.6f}" for item in mapping.itertuples()]
    st.markdown('**ML Probability-Weighted:** Σ P(next-session state) × CVaR target = ' +
                ' + '.join(terms) + f' = {row.target_exposure_ml_proba:.2%}.')
    st.caption('Mapping and probabilities come from the verified model version. Formula terms are rounded for display; targets use full precision.')
    strategies = {'Regime-Based': 'regime_based', 'ML Hard': 'ml_hard', 'ML Probability-Weighted': 'ml_proba'}
    comparison = []
    for label, key in strategies.items():
        previous = row[f'previous_target_{key}']
        change = row[f'change_pp_{key}']
        comparison.append({'Strategy': label, 'Previous Target': f'{previous:.2%}' if pd.notna(previous) else 'N/A',
                           'Selected Target': f"{row[f'target_exposure_{key}']:.2%}",
                           'Change (Percentage Points)': f'{change:+.2f}' if pd.notna(change) else 'N/A',
                           'Direction': row[f'direction_{key}']})
    st.markdown('**Previous Available Session Comparison**')
    st.caption(f"Previous Information Date: {row.previous_session_date if pd.notna(row.previous_session_date) else 'N/A'}")
    st.dataframe(pd.DataFrame(comparison), use_container_width=True, hide_index=True)
    st.caption('Targets are hypothetical model allocations, not executed orders. Changes compare consecutive available signal sessions.')
    strategy = st.selectbox('Decision Chart Strategy', list(strategies), key='decision_chart_strategy')
    chart_data = history[['date', 'next_session_date', 'regime', 'economic_label',
                          f'target_exposure_{strategies[strategy]}']].copy()
    chart_data.columns = ['Signal Date', 'Target Session', 'Regime ID', 'Market Regime', 'Target Exposure']
    chart_data['Market Regime'] = chart_data['Market Regime'].map(risk_label)
    chart_data['Signal Date'] = pd.to_datetime(chart_data['Signal Date'])
    transition = chart_data['Regime ID'].ne(chart_data['Regime ID'].shift())
    transition.iloc[0] = False
    base = alt.Chart(chart_data).encode(x=alt.X('Signal Date:T', title='Signal Information Date'),
        y=alt.Y('Target Exposure:Q', axis=alt.Axis(format='.0%'), scale=alt.Scale(domain=[0, 1])),
        tooltip=['Signal Date:T', 'Target Session:N', 'Regime ID:O', 'Market Regime:N',
                 alt.Tooltip('Target Exposure:Q', format='.2%')])
    line = base.mark_line(interpolate='step-after', color='#d6c2a8')
    transitions = alt.Chart(chart_data.loc[transition]).mark_point(size=65, shape='diamond', filled=True).encode(
        x='Signal Date:T', y='Target Exposure:Q', color=alt.Color('Market Regime:N',
        scale=alt.Scale(domain=['Low Risk', 'Medium Risk', 'High Risk'], range=['#7fb58a', '#d2a450', '#be5a54'])),
        tooltip=['Signal Date:T', 'Target Session:N', 'Regime ID:O', 'Market Regime:N'])
    marker = alt.Chart(chart_data.loc[chart_data['Signal Date'] == pd.Timestamp(selected)]).mark_point(
        size=180, shape='circle', filled=True, color='#67c7e5').encode(x='Signal Date:T', y='Target Exposure:Q')
    st.altair_chart((line + transitions + marker).interactive(), use_container_width=True)
    st.caption('Diamonds mark filtered Markov regime transitions; the blue circle marks the selected signal date. '
               'Targets are plotted at the information close, not at an inferred execution time. Hover for target-session dates; zoom and pan to inspect history.')


def render_strategy_results():
    st.subheader("MAIN v1 Strategy Performance")
    payload = fetch_backtesting_endpoint_safe('/backtesting/comparison', {}, 'versioned strategy performance')
    if not isinstance(payload, dict) or not payload.get('results') or not payload.get('metrics'):
        st.info("A complete validated operational strategy comparison is unavailable. Academic references remain in Research.")
        return
    publication = payload.get('publication') or {}
    frame = pd.DataFrame(payload['results']).set_index('date')
    frame.index = pd.to_datetime(frame.index)
    metrics = pd.DataFrame(payload['metrics'])
    st.caption(f"Frozen Engine: {publication.get('model_version', 'N/A')} · "
               f"Publication Version: {publication.get('version', 'N/A')}")
    st.caption(f"Common Evaluation Period: {frame.index.min():%Y-%m-%d} to {frame.index.max():%Y-%m-%d} · "
               f"{len(frame):,} Market Sessions · Data Freshness: {publication.get('freshness', 'unverified').title()}")
    if not publication.get('is_current'):
        st.warning("Historical performance from a stale or non-current publication; this is not a current trading signal.")
    st.caption("Frozen MAIN Markov parameters, causal-v1 XGBoost and training-only CVaR exposure mapping. "
               "Prior-close targets apply once to the next available market return; the first signal date has no realised result.")
    options = {'Buy & Hold': ('benchmark', 'Buy & Hold'), 'Regime-Based': ('regime_based', 'Regime-based'),
               'ML Hard': ('ml_hard', 'ML Hard'), 'ML Probability-Weighted': ('ml_proba', 'ML Probability-Weighted')}
    selected = st.multiselect('Strategies', list(options), default=list(options), key='performance_strategies')
    basis = st.radio('Performance Basis', ['Gross', 'Net of Transaction Costs'], horizontal=True,
                     key='performance_basis')
    rate = payload.get('conventions', {}).get('cost_rate')
    rate_label = f"{rate * 10000:g} bp" if isinstance(rate, (int, float)) else 'Unreported rate'
    st.caption(f"Costs: {rate_label} × absolute change in applied exposure, deducted from daily log returns. "
               "Initial entry and final liquidation are excluded. Buy & Hold has no modelled trading costs. "
               "Cash earns zero; financing, slippage and taxes are excluded. Gross performance excludes transaction costs.")
    st.caption("Growth uses exp(cumulative log returns); exposed log return = exposure × index log return. "
               "Volatility uses sample daily standard deviation × √252. Expected Shortfall is the mean daily log return "
               "at or below the empirical 5th percentile. Drawdown uses observed running peaks, excluding an initial capital anchor.")
    if not selected:
        st.info('Select at least one strategy to display performance.')
        return
    growth, drawdown, exposure, rows = {}, {}, {}, []
    net = basis == 'Net of Transaction Costs'
    for label in selected:
        key, stored_label = options[label]
        is_benchmark = key == 'benchmark'
        column = f'{key}_cum' + ('_net' if net and not is_benchmark else '')
        curve = frame[column]
        legend = label + (' · No Modelled Costs' if net and is_benchmark else '')
        growth[legend] = curve
        drawdown[legend] = curve / curve.cummax() - 1
        exposure[label] = pd.Series(1., index=frame.index) if is_benchmark else frame[f'strategy_exposure_{key}']
        metric_label = stored_label if is_benchmark else stored_label + (' net of costs' if net else ' gross')
        row = metrics.loc[metrics.strategy == metric_label].iloc[0]
        rows.append({'Strategy': legend, 'Total Return': row.total_return,
                     'Annualized Volatility': row.annualized_volatility, 'Expected Shortfall (95%)': row.CVaR_95,
                     'Maximum Drawdown': row.max_drawdown, 'Total Transaction Costs (Log Return)': row.total_transaction_cost})
    st.markdown(f'**Cumulative Growth · {basis}**')
    st.line_chart(pd.DataFrame(growth), use_container_width=True)
    st.markdown(f'**Drawdown Comparison · {basis}**')
    st.line_chart(pd.DataFrame(drawdown), use_container_width=True)
    st.markdown('**Historical Applied Exposure**')
    st.line_chart(pd.DataFrame(exposure), use_container_width=True)
    display = pd.DataFrame(rows)
    for column in display.columns[1:]:
        display[column] = display[column].map(lambda value: f'{value:.2%}')
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption('Transaction costs are summed log-return deductions, not a cash invoice or compounded performance drag.')
    turnover = pd.DataFrame(payload.get('turnover', []))
    if not turnover.empty:
        labels = {'Regime-based': 'Regime-Based', 'ML Hard Classification': 'ML Hard',
                  'ML Probability-Weighted': 'ML Probability-Weighted'}
        turnover['strategy'] = turnover.strategy.map(labels)
        turnover = turnover[turnover.strategy.isin(selected)]
        st.markdown('**Turnover · Absolute Exposure Units**')
        st.dataframe(presentation_frame(turnover[['strategy', 'total_turnover', 'annualized_turnover',
                                                  'raw_changes', 'effective_changes']]),
                     use_container_width=True, hide_index=True)
        st.caption('Effective changes exceed one percentage point; smaller changes still incur costs. Buy & Hold has no rebalancing turnover under this convention.')


def render_academic_results():
    st.info("Academic Reference — Original TFM Methodology")
    st.subheader("Historical Backtesting")
    st.markdown(
        """
        <div class="panel-box">
            <div class="regime-card-detail">
                Historical Backtesting compares a fully invested Buy & Hold benchmark
                with a strategy that adjusts exposure to the identified risk regime.
                Exposure is applied with a one-session lag, <b>shift(1)</b>, to avoid
                look-ahead bias.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if hasattr(st, "segmented_control"):
        backtest_sample_label = st.segmented_control(
            "Evaluation Sample",
            ["MAIN", "ROBUST"],
            default="MAIN",
            key="backtesting_sample_selector",
        )
    else:
        backtest_sample_label = st.radio(
            "Evaluation Sample",
            ["MAIN", "ROBUST"],
            horizontal=True,
            key="backtesting_sample_selector",
        )
    backtest_sample_label = backtest_sample_label or "MAIN"
    backtest_sample = backtest_sample_label.lower()
    render_split_badge(backtest_sample_label)

    backtest_results = prepare_backtest_results(
        fetch_backtesting_endpoint_safe(
            f"/backtesting/academic/results?sample={backtest_sample}",
            [],
            f"backtest results for {backtest_sample_label}",
        )
    )
    backtest_metrics = prepare_backtest_metrics(
        fetch_backtesting_endpoint_safe(
            "/backtesting/academic/metrics",
            [],
            "backtesting metrics",
        ),
        backtest_sample_label,
    )
    backtest_latest = fetch_backtesting_endpoint_safe(
        f"/backtesting/academic/latest?sample={backtest_sample}",
        {},
        f"the last evaluated backtest session for {backtest_sample_label}",
    )

    st.markdown('<div class="section-title">Out-of-Sample Evaluation</div>', unsafe_allow_html=True)
    render_backtest_metric_cards(backtest_metrics)
    render_defensive_reading(backtest_metrics)

    st.markdown('<div class="section-title">Last Evaluated Historical Session</div>', unsafe_allow_html=True)
    render_backtest_latest(backtest_latest)

    chart_col_left, chart_col_right = st.columns(2)
    with chart_col_left:
        st.markdown('<div class="section-title">Cumulative Return Curves</div>', unsafe_allow_html=True)
        render_backtest_line_chart(
            backtest_results,
            ["benchmark_cum", "strategy_cum"],
            ["Buy & Hold", "Regime Strategy"],
            "Cumulative Return Curves",
            "Cumulative Growth",
        )
    with chart_col_right:
        st.markdown('<div class="section-title">Drawdown Comparison</div>', unsafe_allow_html=True)
        render_backtest_line_chart(
            backtest_results,
            ["benchmark_drawdown", "strategy_drawdown"],
            ["Buy & Hold", "Regime Strategy"],
            "Drawdown Comparison",
            "Drawdown",
        )

    st.markdown('<div class="section-title">Adaptive Portfolio Exposure</div>', unsafe_allow_html=True)
    render_backtest_exposure(backtest_results)
    st.caption(
        "The strategy reduces exposure to 0.75 or 0.25 when the filtered regime indicates greater vulnerability."
    )

    st.markdown('<div class="section-title">Risk Metrics</div>', unsafe_allow_html=True)
    if backtest_metrics.empty:
        st.info("No metrics are available for the selected sample.")
    else:
        display_metrics = backtest_metrics.copy()
        for column in [
            "total_return",
            "mean_daily_return",
            "daily_volatility",
            "annualized_volatility",
            "VaR_95",
            "CVaR_95",
            "max_drawdown",
        ]:
            display_metrics[column] = display_metrics[column].map(
                lambda value: f"{float(value):.2%}"
            )
        st.dataframe(presentation_frame(display_metrics), use_container_width=True, hide_index=True)

    with st.expander("View Out-of-Sample Backtest Data"):
        if backtest_results.empty:
            st.info("No raw backtest data is available.")
        else:
            st.dataframe(presentation_frame(backtest_results.tail(250)), use_container_width=True, hide_index=True)


enter = st.query_params.get("enter", "0")

if enter != "1":
    show_landing()
    st.stop()

left_btn, right_btn = st.columns([1, 6])

with left_btn:
    if st.button("Home"):
        st.query_params.clear()
        st.rerun()

with right_btn:
    st.button("Update Market Data", disabled=True,
              help="Market updates are disabled until a protected update workflow is configured.")
    st.caption("Market updates are disabled. No automated update workflow is configured.")

data = None
try:
    data = load_latest_data()
except requests.HTTPError as exc:
    if exc.response is not None and exc.response.status_code == 503:
        st.warning("No usable operational MAIN publication is available from FastAPI.")
    else:
        st.warning("FastAPI could not return operational results.")
except (requests.RequestException, ValueError):
    st.warning(f"FastAPI is unavailable or returned an invalid response. API: {API_URL}")

try:
    df = load_historical_data()
except (requests.RequestException, ValueError, KeyError):
    df = pd.DataFrame()
    st.warning("Market history is unavailable; other views remain available.")

st.markdown(
    f"""
    <div class="topbar">
        <div class="topbar-title">RISKBEX</div>
        <div class="topbar-subtitle">
            IBEX 35 Risk Intelligence · Publication Information Date: <b>{(data.get('publication') or {}).get('data_date', 'N/A') if data else 'N/A'}</b>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

pages = ["Monitor", "Explore", "Results", "Models", "Research", "Tail Risk"]
requested_page = st.query_params.get("view", "Monitor")
tab_options = {}
if "default" in inspect.signature(st.tabs).parameters:
    tab_options["default"] = requested_page if requested_page in pages else "Monitor"
sections = dict(zip(pages, st.tabs(pages, **tab_options)))

with sections["Monitor"]:
    if data:
        render_operational_overview(data)
        st.caption("Published Session Risk Metrics")
        for col, key, label in zip(st.columns(3), ["cvar_95_60d", "drawdown", "vol_20d"],
                                  ["Expected Shortfall (CVaR) · 95%, 60 Sessions", "Drawdown", "20-Session Volatility"]):
            item = data.get(key)
            col.metric(label, f"{item:.2%}" if item is not None else "N/A")
    if data and data.get("publication") and not df.empty:
        monitor_history = df[df.date <= pd.Timestamp(data["date"])]
        st.caption("Recent published history · the final observation may be stale; see Data Freshness above.")
        render_price_regimes(monitor_history.tail(90))
    if data and data.get("risk_score") is not None:
        with st.expander("Legacy descriptive indicator · historical reference"):
            st.markdown('<div class="section-title">Historical Market State</div>', unsafe_allow_html=True)
            risk_level_text = str(data.get("risk_level", "")).capitalize() if data.get("risk_level") else "N/A"

            regime_cols = st.columns([20, 1])
            with regime_cols[0]:
                render_status_box(data["regime_label"], data["risk_score"])
            with regime_cols[1]:
                info_popover(
                    "Market Regime",
                    "The regime groups market conditions into interpretable Low Risk, Medium Risk and High Risk states."
                )

            metric_labels = [
                "Expected Shortfall (CVaR) · 95%, 60 Sessions",
                "Drawdown",
                "20-Session Volatility",
                "Relative Risk Score",
            ]
            metric_values = [
                f"{data['cvar_95_60d']:.2%}",
                f"{data['drawdown']:.2%}",
                f"{data['vol_20d']:.2%}",
                f"{int(data['risk_score'])} / 100 · {risk_level_text}",
            ]
            metric_notes = [
                "Expected loss in adverse scenarios.",
                "Decline from the latest peak.",
                "Recent market variability.",
                "Aggregate relative risk conditions.",
            ]
            metric_infos = [
                (
                    "CVaR",
                    "Expected Shortfall (CVaR) measures average tail loss beyond the VaR threshold."
                ),
                (
                    "Drawdown",
                    "Drawdown measures the decline from the recent market peak and shows persistent losses."
                ),
                (
                    "20-Session Volatility",
                    "20-session volatility measures recent return variability. Higher values indicate greater instability."
                ),
                (
                    "Relative Risk Score",
                    "The legacy score uses expanding historical percentiles of EWMA volatility, CVaR, drawdown and downside volatility. Values range from 0 (low relative risk) to 100 (extreme relative risk). It does not forecast returns or provide trading signals."
                ),
            ]

            cols = st.columns(4)
            for i, col in enumerate(cols):
                with col:
                    inner_left, inner_right = st.columns([8, 1])
                    with inner_left:
                        metric_card(metric_labels[i], metric_values[i], metric_notes[i])
                    with inner_right:
                        info_popover(metric_infos[i][0], metric_infos[i][1])

            panel_header(
                "How to Read This View",
                "Interpretation",
                "This legacy view summarises relative historical risk on a 0–100 scale. Higher values indicate more extreme conditions relative to prior observations."
            )

            if data["risk_score"] > 70:
                st.warning("The evaluated session indicates elevated relative risk.")
            elif data["risk_score"] > 40:
                st.info("The evaluated session indicates moderate risk and instability.")
            else:
                st.success("The evaluated session indicates relatively contained risk.")

            st.progress(max(0.0, min(float(data["risk_score"]) / 100, 1.0)))
            st.caption("Relative historical score intensity.")

with sections["Explore"]:
    render_decision_explorer()
    st.info("Historical MAIN publication data; this history is not a current signal.")
    df = select_period(df, "explore_period")
    explore_signals = prepare_regime_history(fetch_regime_endpoint_safe(
        "/regimes/history?split=MAIN&limit=all", [], "MAIN regime history"))
    if not explore_signals.empty and not df.empty:
        explore_signals = explore_signals[explore_signals["date"].between(df.date.min(), df.date.max())]
    render_price_regimes(df)
    if not explore_signals.empty:
        st.subheader("Historical Regime Probabilities")
        st.area_chart(explore_signals.set_index("date")[["p_regime_0", "p_regime_1", "p_regime_2"]]
                      .rename(columns={f"p_regime_{i}": f"Regime {i}" for i in range(3)}))
    exposure = prepare_backtest_results(fetch_backtesting_endpoint_safe(
        "/backtesting/results?sample=main", [], "MAIN exposure history"))
    if not exposure.empty and not df.empty:
        exposure = exposure[exposure.date.between(df.date.min(), df.date.max())]
        st.subheader("Adaptive Portfolio Exposure")
        st.line_chart(exposure.set_index("date")[["strategy_exposure", "target_exposure"]]
                      .rename(columns={"strategy_exposure": "Applied Exposure", "target_exposure": "Target Portfolio Exposure"}))
    historical_metric_options = [
        {
            "label": "Relative Risk Score",
            "column": "risk_score",
            "title": "Historical Relative Risk Score",
            "info_title": "Historical Relative Risk Score",
            "info_text": "Historical relative risk score showing deterioration, normalisation and persistent stress.",
            "caption": "Historical relative risk score.",
        },
        {
            "label": "Expected Shortfall (CVaR) · 95%, 60 Sessions",
            "column": "cvar_95_60d",
            "title": "CVaR (95%, 60d)",
            "info_title": "Historical Expected Shortfall (CVaR)",
            "info_text": "Rolling Expected Shortfall (CVaR). More negative values indicate more severe average tail losses.",
            "caption": "Historical tail risk.",
        },
        {
            "label": "20-Session Volatility",
            "column": "vol_20d",
            "title": "20-Session Volatility",
            "info_title": "Historical Volatility",
            "info_text": "Realised volatility over 20 trading sessions tracks recent market instability.",
            "caption": "Historical market variability.",
        },
        {
            "label": "Drawdown",
            "column": "drawdown",
            "title": "Drawdown",
            "info_title": "Historical Drawdown",
            "info_text": "Drawdown tracks cumulative losses from the most recent peak and highlights prolonged declines.",
            "caption": "Cumulative losses from previous peaks.",
        },
        {
            "label": "Skewness",
            "column": "skew_60d",
            "title": "Skewness (60 Sessions)",
            "info_title": "Historical Skewness",
            "info_text": "Skewness describes the asymmetry of returns. Negative skewness indicates a heavier left tail.",
            "caption": "Return distribution skewness.",
        },
    ]

    available_historical_metrics = [
        metric for metric in historical_metric_options if metric["column"] in df.columns and df[metric["column"]].notna().any()
    ]

    if available_historical_metrics:
        selected_historical_label = st.radio(
            "Historical Metric",
            [metric["label"] for metric in available_historical_metrics],
            horizontal=True,
            key="historical_metric_selector",
        )
        selected_historical_metric = next(
            metric
            for metric in available_historical_metrics
            if metric["label"] == selected_historical_label
        )
        panel_header(
            selected_historical_metric["title"],
            selected_historical_metric["info_title"],
            selected_historical_metric["info_text"],
        )
        st.line_chart(
            df.set_index("date")[[selected_historical_metric["column"]]].rename(columns={selected_historical_metric["column"]: selected_historical_metric["label"]}),
            use_container_width=True,
        )
        st.caption(selected_historical_metric["caption"])
    else:
        st.warning("No historical series are available in this view.")

with sections["Research"]:
    st.info("Historical research and evaluation. MAIN versioned results shown here are historical. Consult Monitor for operational signals; ROBUST is an academic reference only.")
    with st.expander("Academic Reference — Original TFM Methodology"):
        render_academic_results()
    figure_options = {
        "Daily Returns": {
            "path": FIGURES_DIR / "daily_returns_ibex35.png",
            "info": "Daily IBEX 35 returns highlight volatility episodes and abrupt market changes."
        },
        "Volatility vs Downside Volatility (60 Sessions)": {
            "path": FIGURES_DIR / "volatility_vs_downside_60d.png",
            "info": "Total volatility compared with downside volatility helps identify instability driven by negative returns."
        },
        "VaR and CVaR (60 Sessions)": {
            "path": FIGURES_DIR / "var_cvar_60d.png",
            "info": "VaR and CVaR describe tail risk. A wide gap indicates particularly severe extreme losses."
        },
        "Drawdown": {
            "path": FIGURES_DIR / "drawdown_ibex35.png",
            "info": "Index losses from previous peaks show the depth and duration of market declines."
        },
        "Skewness (60 Sessions)": {
            "path": FIGURES_DIR / "skew_60d_series.png",
            "info": "Historical return skewness. Persistent negative skewness may indicate more fragile conditions."
        },
        "Risk-Adjusted Return (60 Sessions)": {
            "path": FIGURES_DIR / "ret_risk_60d_series.png",
            "info": "Rolling risk-adjusted returns show how recent performance relates to realised volatility."
        },
    }

    st.subheader("Research")

    selected_figure = st.radio(
        "Figure",
        list(figure_options.keys()),
        horizontal=True,
        key="figure_selector",
    )
    selected_path = figure_options[selected_figure]["path"]
    st.caption(figure_options[selected_figure]["info"])

    if selected_path.exists():
        with open(selected_path, "rb") as f:
            image_bytes = f.read()

        st.image(image_bytes, caption=selected_figure, use_container_width=True)
        st.caption(
            f"Figure Last Modified: {pd.to_datetime(selected_path.stat().st_mtime, unit='s')}"
        )
    else:
        st.warning(f"Research figure unavailable: {selected_path}")

with sections["Models"]:
    st.info("Historical research and evaluation. MAIN versioned results shown here are historical. Consult Monitor for operational signals; ROBUST is an academic reference only.")
    st.subheader("Models")
    st.markdown("**Markov** estimates the Current Market Regime using filtered probabilities. "
                "**XGBoost** provides the Next-Session Regime Forecast. "
                "**Expected Shortfall (CVaR)** measures average loss beyond the VaR threshold. "
                "Model Confidence describes probability concentration, not guaranteed accuracy.")
    st.subheader("Markov Regimes")

    if hasattr(st, "segmented_control"):
        split_selected = st.segmented_control(
            "Evaluation Split",
            ["MAIN", "ROBUST"],
            default="MAIN",
            key="regime_split_selector",
        )
    else:
        split_selected = st.radio(
            "Evaluation Split",
            ["MAIN", "ROBUST"],
            horizontal=True,
            key="regime_split_selector",
        )
    split_selected = split_selected or "MAIN"
    render_split_badge(split_selected)

    latest_selected = fetch_regime_endpoint_safe(
        f"/regimes/latest?split={split_selected}",
        {},
        "the last evaluated regime",
    )
    history_120 = prepare_regime_history(
        fetch_regime_endpoint_safe(
            f"/regimes/history?split={split_selected}&limit=120",
            [],
            "filtered probabilities",
        )
    )
    history_250 = prepare_regime_history(
        fetch_regime_endpoint_safe(
            f"/regimes/history?split={split_selected}&limit=250",
            [],
            "regime history",
        )
    )
    transitions_selected = fetch_regime_endpoint_safe(
        f"/regimes/transitions?split={split_selected}",
        [],
        "the transition matrix",
    )
    durations_selected = fetch_regime_endpoint_safe(
        f"/regimes/durations?split={split_selected}&scope=FULL_FILTERED",
        [],
        "regime duration",
    )
    summary_records = fetch_regime_endpoint_safe(
        "/regimes/summary",
        [],
        "the MAIN vs ROBUST comparison",
    )

    st.markdown('<div class="section-title">Last Evaluated Regime</div>', unsafe_allow_html=True)
    render_regime_card(split_selected, latest_selected)

    st.markdown('<div class="section-title">Filtered Probabilities</div>', unsafe_allow_html=True)
    st.caption("Filtered Markov Switching probabilities")
    if history_120.empty:
        st.info("No historical probabilities are available.")
    else:
        probability_df = history_120.set_index("date")[
            ["p_regime_0", "p_regime_1", "p_regime_2"]
        ]
        st.area_chart(probability_df.rename(columns={f"p_regime_{i}": f"Regime {i}" for i in range(3)}), use_container_width=True)

    st.markdown('<div class="section-title">Recent Regime History</div>', unsafe_allow_html=True)
    if history_250.empty:
        st.info("No regime history is available.")
    else:
        render_regime_timeline(history_250)

    st.markdown('<div class="section-title">Model Confidence</div>', unsafe_allow_html=True)
    uncertainty_col, uncertainty_chart_col = st.columns([1, 2])
    with uncertainty_col:
        render_uncertainty_card(split_selected, latest_selected)
    with uncertainty_chart_col:
        render_uncertainty_chart(history_250)
        st.caption(
            "Descriptive confidence thresholds: high from 80%, moderate from 60% to 80%, and transition below 60%. These are not calibrated forecast accuracy estimates."
        )

    heatmap_col, duration_col = st.columns(2)
    with heatmap_col:
        st.markdown('<div class="section-title">Transition Heatmap</div>', unsafe_allow_html=True)
        render_transition_heatmap(transitions_selected)
        st.caption(
            "High diagonal transition probabilities indicate regime persistence."
        )

    with duration_col:
        st.markdown('<div class="section-title">Regime Persistence / Duration</div>', unsafe_allow_html=True)
        render_duration_bars(durations_selected)
        st.caption("Average length of consecutive regime episodes in trading sessions.")

    st.markdown('<div class="section-title">MAIN vs ROBUST Comparison</div>', unsafe_allow_html=True)
    summary_df = pd.DataFrame(summary_records)
    if summary_df.empty:
        st.info("No regime summary is available.")
    else:
        comparison_df = summary_df[
            [
                "split",
                "economic_label",
                "frequency_pct",
                "mean_ewma_vol",
                "mean_cvar_95_60d",
            ]
        ].copy()
        comparison_df["frequency_pct"] = comparison_df["frequency_pct"].map(
            lambda value: f"{float(value):.1%}"
        )
        comparison_df["mean_ewma_vol"] = comparison_df["mean_ewma_vol"].map(
            lambda value: f"{float(value):.2%}"
        )
        comparison_df["mean_cvar_95_60d"] = comparison_df["mean_cvar_95_60d"].map(
            lambda value: f"{float(value):.2%}"
        )
        st.dataframe(presentation_frame(comparison_df), use_container_width=True, hide_index=True)

with sections["Results"]:
    render_strategy_results()

with sections["Tail Risk"]:
    st.info("Historical research and evaluation. MAIN versioned results shown here are historical. Consult Monitor for operational signals; ROBUST is an academic reference only.")
    st.subheader("Tail Risk")
    st.markdown(
        """
        <div class="panel-box">
            <div class="regime-card-detail">
                Tail risk analysis evaluates Buy & Hold and the
                adaptive strategy during the worst 5% of Out-of-Sample market sessions.
                Extreme events are defined using market returns (<b>ret_1d</b>), so both
                strategies are evaluated on the same stressed sessions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if hasattr(st, "segmented_control"):
        tail_sample_label = st.segmented_control(
            "Evaluation Sample",
            ["MAIN", "ROBUST"],
            default="MAIN",
            key="tail_sample_selector",
        )
    else:
        tail_sample_label = st.radio(
            "Evaluation Sample",
            ["MAIN", "ROBUST"],
            horizontal=True,
            key="tail_sample_selector",
        )
    tail_sample_label = tail_sample_label or "MAIN"
    tail_sample = tail_sample_label.lower()
    render_split_badge(tail_sample_label)

    tail_events = prepare_tail_events(
        fetch_tail_endpoint_safe(
            f"/tail-risk/events?sample={tail_sample}",
            [],
            f"tail events for {tail_sample_label}",
        )
    )
    tail_metrics = prepare_tail_metrics(
        fetch_tail_endpoint_safe(
            "/tail-risk/metrics",
            [],
            "tail risk metrics",
        ),
        tail_sample_label,
    )
    tail_threshold = prepare_tail_threshold(
        fetch_tail_endpoint_safe(
            "/tail-risk/thresholds",
            [],
            "tail risk thresholds",
        ),
        tail_sample_label,
    )
    tail_latest = fetch_tail_endpoint_safe(
        f"/tail-risk/latest?sample={tail_sample}",
        {},
        f"the last evaluated tail risk session for {tail_sample_label}",
    )

    st.markdown('<div class="section-title">Left Tail Risk Evaluation</div>', unsafe_allow_html=True)
    render_tail_metric_cards(tail_threshold, tail_metrics)
    render_tail_defensive_reading(tail_metrics)

    st.markdown('<div class="section-title">Latest</div>', unsafe_allow_html=True)
    render_tail_latest(tail_latest)

    timeline_col, tail_cum_col = st.columns(2)
    with timeline_col:
        st.markdown('<div class="section-title">Extreme Event Timeline</div>', unsafe_allow_html=True)
        render_tail_event_timeline(
            tail_events,
            tail_threshold.get("tail_threshold", 0.0) if tail_threshold else 0.0,
        )
    with tail_cum_col:
        st.markdown('<div class="section-title">Cumulative Return on Tail Sessions</div>', unsafe_allow_html=True)
        render_tail_cumulative_chart(tail_events)

    cvar_col, regime_col = st.columns(2)
    with cvar_col:
        st.markdown('<div class="section-title">Tail CVaR</div>', unsafe_allow_html=True)
        render_tail_cvar_bars(tail_metrics)
    with regime_col:
        st.markdown(
            '<div class="section-title">Regime Composition During Stress</div>',
            unsafe_allow_html=True,
        )
        render_tail_regime_composition(tail_events)

    st.markdown('<div class="section-title">Tail Risk Metrics</div>', unsafe_allow_html=True)
    if tail_metrics.empty:
        st.info("No tail risk metrics are available for the selected sample.")
    else:
        display_tail_metrics = tail_metrics[
            [
                "strategy",
                "n_tail_events",
                "mean_tail_return",
                "tail_volatility",
                "tail_total_return",
                "tail_VaR_95",
                "tail_CVaR_95",
                "max_backtest_drawdown_on_tail_days",
                "hit_ratio_negative",
            ]
        ].copy()
        for column in [
            "mean_tail_return",
            "tail_volatility",
            "tail_total_return",
            "tail_VaR_95",
            "tail_CVaR_95",
            "max_backtest_drawdown_on_tail_days",
            "hit_ratio_negative",
        ]:
            display_tail_metrics[column] = display_tail_metrics[column].map(
                lambda value: f"{float(value):.2%}"
            )
        st.dataframe(presentation_frame(display_tail_metrics), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Worst Sessions</div>', unsafe_allow_html=True)
    if tail_events.empty:
        st.info("No sessions are available.")
    else:
        worst_days = tail_events.sort_values("ret_1d", ascending=True).head(10)
        worst_days = worst_days[
            [
                "date",
                "ret_1d",
                "regime_label",
                "strategy_exposure",
                "benchmark_return",
                "strategy_return",
                "benchmark_drawdown",
                "strategy_drawdown",
                "stress_tail_event",
            ]
        ].copy()
        for column in [
            "ret_1d",
            "benchmark_return",
            "strategy_return",
            "benchmark_drawdown",
            "strategy_drawdown",
        ]:
            worst_days[column] = worst_days[column].map(lambda value: f"{float(value):.2%}")
        worst_days["strategy_exposure"] = worst_days["strategy_exposure"].map(
            lambda value: f"{float(value):.2f}"
        )
        worst_days["date"] = worst_days["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(presentation_frame(worst_days), use_container_width=True, hide_index=True)

st.markdown(
    """
    <div class="footer-note">
        RISKBEX connects market data, risk metrics and regime analysis to monitor IBEX 35 tail risk.
    </div>
    """,
    unsafe_allow_html=True,
)
