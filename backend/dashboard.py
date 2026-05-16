import streamlit as st
import requests
import pandas as pd
import os
import matplotlib.pyplot as plt
from pathlib import Path

API_URL = os.getenv("RISKBEX_API_URL", "http://127.0.0.1:8000")
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
    st.markdown(
        """
        <a href="?enter=1" class="hero-link">
            <div class="landing-wrapper">
                <div class="landing-box">
                    <div class="landing-content">
                        <div class="landing-kicker">Proyecto académico aplicado</div>
                        <div class="landing-title">Bienvenido a RISKBEX</div>
                        <div class="landing-subline">TFM to applied risk monitoring dashboard</div>
                        <div class="landing-author">Desarrollado por Alejandro Palomo Morales</div>
                        <div class="landing-subtitle">
                            RISKBEX es la capa de presentación de un proyecto académico centrado en la monitorización interpretable del riesgo extremo del IBEX 35. El sistema construye variables de riesgo de mercado a partir de datos del índice y evalúa las condiciones de deterioro mediante medidas como la volatilidad, el drawdown y el Conditional Value at Risk para facilitar el seguimiento del entorno de riesgo.
                        </div>
                        <div class="landing-badges">
                            <span class="landing-badge">Tail Risk</span>
                            <span class="landing-badge">Market Regimes</span>
                            <span class="landing-badge">Risk Monitoring</span>
                        </div>
                        <div class="landing-hint">
                            Haz clic en cualquier parte para entrar al dashboard
                        </div>
                    </div>
                </div>
            </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


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
        title = "Régimen de estrés"
        text = (
            "El mercado muestra señales de inestabilidad elevada, mayor presión bajista "
            "y un entorno menos favorable para asumir riesgo."
        )
    elif regime == "turbulence":
        css_class = "status-box status-turbulence"
        title = "Régimen de turbulencia"
        text = (
            "El mercado se encuentra en una fase intermedia de riesgo. No es un escenario "
            "plenamente extremo, pero sí aparecen señales de tensión."
        )
    else:
        css_class = "status-box status-calm"
        title = "Régimen de calma"
        text = (
            "El mercado se encuentra en una fase relativamente estable, con riesgo a la baja "
            "más contenido y menor presión agregada."
        )

    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="status-title">{title}</div>
            <div class="status-text">
                Régimen detectado: <b>{regime_label.upper()}</b><br>
                Nivel de riesgo agregado: <b>{int(risk_score)} / 100</b>
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
    return response.json()


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
        st.warning(f"No se pudo cargar {label}.")
        st.caption(str(e))
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
        return "validación robusta temporal"
    return "partición principal"


def render_split_badge(split: str):
    st.markdown(
        f'<span class="split-badge">{split} · {split_description(split)}</span>',
        unsafe_allow_html=True,
    )


def render_regime_card(title: str, payload: dict):
    if not payload:
        st.info("No hay estado actual disponible.")
        return
    probability = float(payload.get("dominant_probability", 0.0))
    card_class = regime_card_class(payload.get("economic_label", ""))
    st.markdown(
        f"""
        <div class="regime-card {card_class}">
            <div class="regime-card-title">{title}</div>
            <div class="regime-card-label">{payload.get("economic_label", "N/D")}</div>
            <div class="regime-card-detail">
                Probabilidad dominante<br>
                <b>{probability:.1%}</b><br>
                Orden de riesgo: <b>{int(payload.get("risk_order", 0))}</b><br>
                Fecha: <b>{payload.get("date", "N/D")}</b>
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
        return "Alta confianza"
    if dominant_probability >= 0.60:
        return "Confianza moderada"
    return "Zona de transición"


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
        st.info("No hay datos suficientes para calcular incertidumbre probabilística.")
        return
    metrics = uncertainty_metrics(latest_payload)
    gap_note = (
        "El gap es estrecho: hay mezcla relevante entre estados de riesgo."
        if metrics["probability_gap"] < 0.20
        else "El régimen dominante se separa con claridad del segundo estado."
    )
    st.markdown(
        f"""
        <div class="panel-box">
            <div class="regime-card-title">Incertidumbre probabilística · {split}</div>
            <div class="regime-card-label">{metrics["confidence_label"]}</div>
            <div class="regime-card-detail">
                Probabilidad dominante: <b>{metrics["dominant_probability"]:.1%}</b><br>
                Segunda probabilidad: <b>{metrics["second_probability"]:.1%}</b><br>
                Gap probabilístico: <b>{metrics["probability_gap"]:.1%}</b>
            </div>
            <div class="uncertainty-note">
                {gap_note}<br>
                Las probabilidades filtradas permiten representar transiciones graduales entre estados de riesgo.
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
        st.info("No hay histórico suficiente para visualizar incertidumbre.")
        return
    uncertainty_df = add_uncertainty_columns(history_df)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(
        uncertainty_df["date"],
        uncertainty_df["dominant_probability"],
        color="#d6c2a8",
        linewidth=2.0,
        label="Probabilidad dominante",
    )
    ax.plot(
        uncertainty_df["date"],
        uncertainty_df["probability_gap"],
        color="#7f8f7a",
        linewidth=1.8,
        label="Gap dominante-segunda",
    )
    ax.axhline(0.80, color="#7fb58a", linewidth=1.0, linestyle="--", alpha=0.55)
    ax.axhline(0.60, color="#d2a450", linewidth=1.0, linestyle="--", alpha=0.55)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Probabilidad")
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
        st.info("No hay matriz de transición disponible.")
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
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Destino")
    ax.set_ylabel("Origen")
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
        st.info("No hay datos de duración disponibles.")
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
        label="Media",
        color="#d6c2a8",
    )
    ax.bar(
        median_positions,
        duration_df["median_duration_trading_days"],
        width=width,
        label="Mediana",
        color="#7f8f7a",
    )
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Sesiones")
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


enter = st.query_params.get("enter", "0")

if enter != "1":
    show_landing()
    st.stop()

left_btn, right_btn = st.columns([1, 6])

with left_btn:
    if st.button("Inicio"):
        st.query_params.clear()
        st.rerun()

with right_btn:
    if st.button("Actualizar datos"):
        with st.spinner("Actualizando datos..."):
            try:
                response = requests.post(f"{API_URL}/run-update", timeout=320)
                response.raise_for_status()
                update_result = response.json()
            except Exception as e:
                st.error("No se pudo actualizar el sistema.")
                if getattr(e, "response", None) is not None:
                    try:
                        error_payload = e.response.json()
                        st.code(error_payload.get("stderr") or error_payload.get("message") or str(error_payload))
                    except Exception:
                        st.code(e.response.text)
                else:
                    st.code(str(e))
            else:
                st.success("Datos actualizados correctamente.")
                st.cache_data.clear()
                st.rerun()

try:
    data = load_latest_data()
    df = load_historical_data()
except Exception as e:
    st.markdown(
        f"""
        <div class="panel-box">
            <h2>Error de conexión</h2>
            <p>No se pudieron recuperar los datos desde la API configurada. Comprueba que FastAPI esté funcionando en {API_URL}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.exception(e)
    st.stop()

st.markdown(
    f"""
    <div class="topbar">
        <div class="topbar-title">RISKBEX</div>
        <div class="topbar-subtitle">
            Monitor interpretable de riesgo extremo del IBEX 35 · Última actualización disponible: <b>{data['date']}</b>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs(
    ["Visión general", "Análisis histórico", "Figuras de investigación", "Regímenes"]
)

with tab1:
    st.markdown('<div class="section-title">Estado actual del mercado</div>', unsafe_allow_html=True)
    risk_level_text = str(data.get("risk_level", "")).capitalize() if data.get("risk_level") else "N/D"

    regime_cols = st.columns([20, 1])
    with regime_cols[0]:
        render_status_box(data["regime_label"], data["risk_score"])
    with regime_cols[1]:
        info_popover(
            "Régimen de mercado",
            "El régimen resume el estado actual del mercado en una categoría interpretable. En esta versión del sistema se usa para distinguir entre entornos de calma, turbulencia y estrés."
        )

    metric_labels = [
        "CVaR 95% (60d)",
        "Drawdown",
        "Volatilidad 20d",
        "Nivel de riesgo",
    ]
    metric_values = [
        f"{data['cvar_95_60d']:.2%}",
        f"{data['drawdown']:.2%}",
        f"{data['vol_20d']:.2%}",
        f"{int(data['risk_score'])} / 100 · {risk_level_text}",
    ]
    metric_notes = [
        "Pérdida esperada en escenarios adversos.",
        "Caída respecto al último máximo.",
        "Variabilidad reciente del mercado.",
        "Síntesis agregada del entorno de riesgo.",
    ]
    metric_infos = [
        (
            "CVaR",
            "El Conditional Value at Risk mide la pérdida media esperada en la cola de la distribución, una vez superado el umbral de VaR. Es una medida útil para evaluar riesgo extremo."
        ),
        (
            "Drawdown",
            "El drawdown captura cuánto ha caído el mercado desde su máximo reciente. Ayuda a visualizar deterioros acumulados y episodios de pérdida persistente."
        ),
        (
            "Volatilidad 20 días",
            "La volatilidad a 20 días resume la variabilidad reciente de los rendimientos. Valores más altos suelen indicar un entorno más incierto e inestable."
        ),
        (
            "Nivel de riesgo",
            "El indicador de riesgo mide la posición relativa histórica del riesgo de mercado en escala 0-100 usando percentiles históricos expanding. Combina EWMA volatility, CVaR, drawdown y downside volatility. Un valor 0 representa riesgo relativo bajo y 100 riesgo extremo relativo. No predice retornos ni constituye señal de compra o venta."
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
        "Cómo leer este dashboard",
        "Interpretación general",
        "Esta vista resume el estado actual del mercado mediante un régimen y un indicador agregado de riesgo relativo histórico (0-100). Cuanto mayor es el indicador, más extremo es el entorno de riesgo frente a su propia historia."
    )

    if data["risk_score"] > 70:
        st.warning("El entorno actual es consistente con una fase de riesgo elevado.")
    elif data["risk_score"] > 40:
        st.info("El mercado muestra un nivel intermedio de riesgo y señales de inestabilidad.")
    else:
        st.success("El entorno actual sigue siendo relativamente contenido en términos de riesgo.")

    st.progress(max(0.0, min(float(data["risk_score"]) / 100, 1.0)))
    st.caption("Intensidad actual del indicador agregado de riesgo.")

with tab2:
    historical_metric_options = [
        {
            "label": "Nivel de riesgo",
            "column": "risk_score",
            "title": "Evolución del nivel de riesgo",
            "info_title": "Nivel de riesgo histórico",
            "info_text": "Este gráfico muestra la trayectoria histórica del indicador agregado de riesgo. Permite identificar fases de deterioro, normalización y persistencia del estrés.",
            "caption": "Trayectoria histórica del indicador agregado de riesgo.",
        },
        {
            "label": "CVaR 95% 60d",
            "column": "cvar_95_60d",
            "title": "CVaR (95%, 60d)",
            "info_title": "CVaR histórico",
            "info_text": "Este panel sigue la evolución del Conditional Value at Risk en ventana móvil. Cuanto más extremo sea su valor, más severas son las pérdidas esperadas en escenarios adversos.",
            "caption": "Evolución del riesgo de cola.",
        },
        {
            "label": "Volatilidad 20d",
            "column": "vol_20d",
            "title": "Volatilidad (20d)",
            "info_title": "Volatilidad histórica",
            "info_text": "Esta serie recoge la volatilidad realizada a 20 días. Es una señal útil para seguir episodios de inestabilidad reciente.",
            "caption": "Evolución de la variabilidad reciente del mercado.",
        },
        {
            "label": "Drawdown",
            "column": "drawdown",
            "title": "Drawdown",
            "info_title": "Drawdown histórico",
            "info_text": "El drawdown permite seguir la profundidad de las caídas acumuladas respecto al máximo más reciente. Resulta especialmente útil para detectar fases de deterioro prolongado.",
            "caption": "Pérdidas acumuladas respecto a máximos previos.",
        },
        {
            "label": "Skewness",
            "column": "skew_60d",
            "title": "Asimetría (60d)",
            "info_title": "Asimetría histórica",
            "info_text": "La asimetría muestra si la distribución de rendimientos tiene más peso hacia la cola izquierda o derecha. En episodios de estrés suelen aparecer sesgos más negativos.",
            "caption": "Asimetría de la distribución de rendimientos.",
        },
    ]

    available_historical_metrics = [
        metric for metric in historical_metric_options if metric["column"] in df.columns
    ]

    if available_historical_metrics:
        selected_historical_label = st.radio(
            "Serie histórica",
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
            df.set_index("date")[selected_historical_metric["column"]],
            use_container_width=True,
        )
        st.caption(selected_historical_metric["caption"])
    else:
        st.warning("No hay series históricas disponibles para mostrar en esta sección.")

with tab3:
    figure_options = {
        "Rendimientos diarios": {
            "path": FIGURES_DIR / "daily_returns_ibex35.png",
            "info": "Representa la evolución diaria de los rendimientos del IBEX 35. Sirve para identificar episodios de alta variabilidad y cambios bruscos en la dinámica del mercado."
        },
        "Volatilidad vs downside (60d)": {
            "path": FIGURES_DIR / "volatility_vs_downside_60d.png",
            "info": "Compara la volatilidad total con una medida centrada en el riesgo a la baja. Es útil para ver si el deterioro viene principalmente por movimientos negativos."
        },
        "VaR y CVaR (60d)": {
            "path": FIGURES_DIR / "var_cvar_60d.png",
            "info": "Compara dos medidas de riesgo de cola. Si el CVaR se separa mucho del VaR, suele indicar que las pérdidas extremas son especialmente severas."
        },
        "Drawdown": {
            "path": FIGURES_DIR / "drawdown_ibex35.png",
            "info": "Muestra las caídas acumuladas del índice respecto a sus máximos previos. Ayuda a visualizar la profundidad y duración de los episodios bajistas."
        },
        "Asimetría (60d)": {
            "path": FIGURES_DIR / "skew_60d_series.png",
            "info": "Permite seguir la evolución temporal de la asimetría de la distribución de rendimientos. Sesgos negativos persistentes pueden asociarse a entornos más frágiles."
        },
        "Retorno ajustado por riesgo (60d)": {
            "path": FIGURES_DIR / "ret_risk_60d_series.png",
            "info": "Relaciona rendimiento y riesgo dentro de una ventana móvil. Ayuda a observar si las rentabilidades recientes compensan adecuadamente la volatilidad asumida."
        },
    }

    st.subheader("Figuras de investigación")

    selected_figure = st.radio(
        "Figura",
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
            f"Última modificación: {pd.to_datetime(selected_path.stat().st_mtime, unit='s')}"
        )
    else:
        st.warning(f"No se encontró la figura: {selected_path}")

with tab4:
    st.subheader("Regímenes Markov")

    if hasattr(st, "segmented_control"):
        split_selected = st.segmented_control(
            "Selector de partición",
            ["MAIN", "ROBUST"],
            default="MAIN",
            key="regime_split_selector",
        )
    else:
        split_selected = st.radio(
            "Selector de partición",
            ["MAIN", "ROBUST"],
            horizontal=True,
            key="regime_split_selector",
        )
    split_selected = split_selected or "MAIN"
    render_split_badge(split_selected)

    latest_selected = fetch_regime_endpoint_safe(
        f"/regimes/latest?split={split_selected}",
        {},
        "el estado actual del régimen",
    )
    history_120 = prepare_regime_history(
        fetch_regime_endpoint_safe(
            f"/regimes/history?split={split_selected}&limit=120",
            [],
            "las probabilidades filtradas",
        )
    )
    history_250 = prepare_regime_history(
        fetch_regime_endpoint_safe(
            f"/regimes/history?split={split_selected}&limit=250",
            [],
            "el histórico de regímenes",
        )
    )
    transitions_selected = fetch_regime_endpoint_safe(
        f"/regimes/transitions?split={split_selected}",
        [],
        "la matriz de transición",
    )
    durations_selected = fetch_regime_endpoint_safe(
        f"/regimes/durations?split={split_selected}&scope=FULL_FILTERED",
        [],
        "las duraciones de régimen",
    )
    summary_records = fetch_regime_endpoint_safe(
        "/regimes/summary",
        [],
        "el resumen comparativo MAIN vs ROBUST",
    )

    st.markdown('<div class="section-title">Estado actual del régimen</div>', unsafe_allow_html=True)
    render_regime_card(split_selected, latest_selected)

    st.markdown('<div class="section-title">Probabilidades filtradas</div>', unsafe_allow_html=True)
    st.caption("Probabilidades filtradas del modelo Markov Switching")
    if history_120.empty:
        st.info("No hay histórico de probabilidades disponible.")
    else:
        probability_df = history_120.set_index("date")[
            ["p_regime_0", "p_regime_1", "p_regime_2"]
        ]
        st.area_chart(probability_df, use_container_width=True)

    st.markdown('<div class="section-title">Histórico reciente de regímenes</div>', unsafe_allow_html=True)
    if history_250.empty:
        st.info("No hay histórico de regímenes disponible.")
    else:
        render_regime_timeline(history_250)

    st.markdown('<div class="section-title">Incertidumbre probabilística</div>', unsafe_allow_html=True)
    uncertainty_col, uncertainty_chart_col = st.columns([1, 2])
    with uncertainty_col:
        render_uncertainty_card(split_selected, latest_selected)
    with uncertainty_chart_col:
        render_uncertainty_chart(history_250)
        st.caption(
            "Umbrales operativos: alta confianza desde 80%, confianza moderada entre 60% y 80%, y zona de transición por debajo de 60%."
        )

    heatmap_col, duration_col = st.columns(2)
    with heatmap_col:
        st.markdown('<div class="section-title">Heatmap de transición</div>', unsafe_allow_html=True)
        render_transition_heatmap(transitions_selected)
        st.caption(
            "Las probabilidades diagonales elevadas reflejan persistencia de régimen."
        )

    with duration_col:
        st.markdown('<div class="section-title">Persistencia / duraciones</div>', unsafe_allow_html=True)
        render_duration_bars(durations_selected)
        st.caption("Duración media de bloques consecutivos de régimen.")

    st.markdown('<div class="section-title">Comparación MAIN vs ROBUST</div>', unsafe_allow_html=True)
    summary_df = pd.DataFrame(summary_records)
    if summary_df.empty:
        st.info("No hay resumen de regímenes disponible.")
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
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

st.markdown(
    """
    <div class="footer-note">
        RISKBEX conecta datos de mercado, métricas de riesgo y análisis de régimen para monitorizar el riesgo extremo del IBEX 35.
    </div>
    """,
    unsafe_allow_html=True,
)
