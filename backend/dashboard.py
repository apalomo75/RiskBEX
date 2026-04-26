import streamlit as st
import requests
import pandas as pd
from pathlib import Path

API_URL = "http://127.0.0.1:8000"
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

    .stSelectbox > div > div {
        background-color: rgba(214, 194, 168, 0.08);
        border: 1px solid var(--border);
        border-radius: 14px;
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
                        <div class="landing-subline">TFM to applied portfolio prototype</div>
                        <div class="landing-author">Desarrollado por Alex Palomo</div>
                        <div class="landing-subtitle">
                            RISKBEX es la capa de presentación de un proyecto académico centrado en el análisis de riesgo de cartera y en la optimización dinámica. El sistema construye variables de riesgo de mercado a partir de datos del IBEX 35, evalúa las condiciones de deterioro mediante medidas como la volatilidad, el drawdown y el Conditional Value at Risk, y evoluciona hacia un marco de asignación apoyado en machine learning capaz de ajustar los pesos de la cartera automáticamente con el objetivo de minimizar el riesgo de cola.
                        </div>
                        <div class="landing-badges">
                            <span class="landing-badge">Tail Risk</span>
                            <span class="landing-badge">Market Regimes</span>
                            <span class="landing-badge">Dynamic Allocation</span>
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
    response = requests.get(f"{API_URL}/historical-risk", timeout=10)
    response.raise_for_status()
    hist_data = response.json()
    df = pd.DataFrame(hist_data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df


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
        st.cache_data.clear()
        st.rerun()

try:
    data = load_latest_data()
    df = load_historical_data()
except Exception as e:
    st.markdown(
        """
        <div class="panel-box">
            <h2>Error de conexión</h2>
            <p>No se pudieron recuperar los datos desde la API local. Comprueba que FastAPI esté funcionando en http://127.0.0.1:8000.</p>
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
            Monitor de riesgo de mercado y análisis dinámico de cartera sobre el IBEX 35 · Última actualización disponible: <b>{data['date']}</b>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["Visión general", "Análisis histórico", "Figuras de investigación"])

with tab1:
    st.markdown('<div class="tab-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Estado actual del mercado</div>', unsafe_allow_html=True)

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
        f"{int(data['risk_score'])} / 100",
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
            "El nivel de riesgo es un indicador compuesto entre 0 y 100 diseñado para resumir el estado actual del mercado. Integra señales de volatilidad, drawdown y riesgo de cola para ofrecer una lectura rápida e interpretable."
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

    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    panel_header(
        "Cómo leer este dashboard",
        "Interpretación general",
        "Esta vista resume el estado actual del mercado a través de un régimen, un nivel agregado de riesgo y varias métricas clave. La lógica general es simple: cuanto mayores son la volatilidad, el drawdown y el riesgo de cola, más adverso es el entorno para una cartera."
    )

    if data["risk_score"] > 70:
        st.warning("El entorno actual es consistente con una fase de riesgo elevado.")
    elif data["risk_score"] > 40:
        st.info("El mercado muestra un nivel intermedio de riesgo y señales de inestabilidad.")
    else:
        st.success("El entorno actual sigue siendo relativamente contenido en términos de riesgo.")

    st.progress(max(0.0, min(float(data["risk_score"]) / 100, 1.0)))
    st.caption("Intensidad actual del indicador agregado de riesgo.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="tab-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Dinámica histórica del riesgo</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    panel_header(
        "Evolución del nivel de riesgo",
        "Nivel de riesgo histórico",
        "Este gráfico muestra la trayectoria histórica del indicador agregado de riesgo. Permite identificar fases de deterioro, normalización y persistencia del estrés."
    )
    st.line_chart(df.set_index("date")["risk_score"], use_container_width=True)
    st.caption("Trayectoria histórica del indicador agregado de riesgo.")
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        panel_header(
            "CVaR (95%, 60d)",
            "CVaR histórico",
            "Este panel sigue la evolución del Conditional Value at Risk en ventana móvil. Cuanto más extremo sea su valor, más severas son las pérdidas esperadas en escenarios adversos."
        )
        st.line_chart(df.set_index("date")["cvar_95_60d"], use_container_width=True)
        st.caption("Evolución del riesgo de cola.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        panel_header(
            "Volatilidad (20d)",
            "Volatilidad histórica",
            "Esta serie recoge la volatilidad realizada a 20 días. Es una señal útil para seguir episodios de inestabilidad reciente."
        )
        st.line_chart(df.set_index("date")["vol_20d"], use_container_width=True)
        st.caption("Evolución de la variabilidad reciente del mercado.")
        st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        panel_header(
            "Drawdown",
            "Drawdown histórico",
            "El drawdown permite seguir la profundidad de las caídas acumuladas respecto al máximo más reciente. Resulta especialmente útil para detectar fases de deterioro prolongado."
        )
        st.line_chart(df.set_index("date")["drawdown"], use_container_width=True)
        st.caption("Pérdidas acumuladas respecto a máximos previos.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        panel_header(
            "Asimetría (60d)",
            "Asimetría histórica",
            "La asimetría muestra si la distribución de rendimientos tiene más peso hacia la cola izquierda o derecha. En episodios de estrés suelen aparecer sesgos más negativos."
        )
        st.line_chart(df.set_index("date")["skew_60d"], use_container_width=True)
        st.caption("Asimetría de la distribución de rendimientos.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="tab-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Figuras de investigación</div>', unsafe_allow_html=True)

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

    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    header_cols = st.columns([20, 1])
    with header_cols[0]:
        st.subheader("Explorador de figuras")
    with header_cols[1]:
        info_popover(
            "Figuras de investigación",
            "Esta sección integra las figuras generadas en el pipeline analítico. Su función es complementar el dashboard con evidencia visual más cercana a la parte académica del proyecto."
        )

    selected_figure = st.selectbox("Selecciona una figura", list(figure_options.keys()))
    selected_path = figure_options[selected_figure]["path"]

    info_popover(selected_figure, figure_options[selected_figure]["info"])

    if selected_path.exists():
        with open(selected_path, "rb") as f:
            image_bytes = f.read()

        st.image(image_bytes, caption=selected_figure, use_container_width=True)
        st.caption(
            f"Última modificación: {pd.to_datetime(selected_path.stat().st_mtime, unit='s')}"
        )
    else:
        st.warning(f"No se encontró la figura: {selected_path}")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-note">
        RISKBEX conecta datos de mercado, métricas de riesgo y análisis de régimen dentro de un marco orientado a cartera.
    </div>
    """,
    unsafe_allow_html=True,
)