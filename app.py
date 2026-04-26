from __future__ import annotations

import pandas as pd
import streamlit as st

import logic
from utils.styles import apply_custom_styles

# Configuración inicial de la página.
st.set_page_config(page_title="HAVI | Hey Banco", layout="wide")
apply_custom_styles()

USER_ID = logic.DEFAULT_USER_ID

# Inicializa el estado de la aplicación.
def initialize_state() -> None:
    if "messages" in st.session_state:
        return

    # Lista para recordar temas recientes.
    st.session_state.recent_topics = []

    # Obtiene el payload inicial del motor.
    initial_payload = logic.analyze_interaction("", USER_ID, st.session_state.recent_topics)
    st.session_state.messages = [{"role": "assistant", "payload": initial_payload}]
    st.session_state.current_options = initial_payload.get("options", logic.DEFAULT_OPTIONS)

# Registra el turno del usuario y la respuesta.
def append_user_turn(user_text: str) -> None:
    # Llama al motor pasando la memoria de tópicos.
    payload = logic.analyze_interaction(user_text, USER_ID, st.session_state.recent_topics)
    
    # Guarda el tema si es nuevo.
    current_intent = payload.get("intent")
    if current_intent and current_intent not in st.session_state.recent_topics:
        st.session_state.recent_topics.append(current_intent)

    # Actualiza el historial.
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.messages.append({"role": "assistant", "payload": payload})
    st.session_state.current_options = payload.get("options", logic.DEFAULT_OPTIONS)

# Recupera el último payload del asistente.
def latest_payload() -> dict:
    for message in reversed(st.session_state.messages):
        if message["role"] == "assistant":
            return message["payload"]
    return logic.analyze_interaction("", USER_ID, st.session_state.get("recent_topics", []))

# Renderiza los indicadores principales.
def render_metric_band(metrics: list[dict]) -> None:
    visible_metrics = metrics[:3]
    columns = st.columns(3)
    for column, metric in zip(columns, visible_metrics):
        delta_html = f'<div class="metric-delta">{metric.get("delta", "")}</div>' if metric.get("delta") else ""
        column.markdown(
            f"""
            <div class="kpi-card tone-{metric.get("tone", "info")}">
                <div class="metric-label">{metric.get("label", "")}</div>
                <div class="metric-value">{metric.get("value", "")}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

# Renderiza la barra lateral con el perfil.
def render_sidebar(context: dict) -> None:
    st.sidebar.markdown(
        f"""
        <div class="profile-card">
            <div class="profile-eyebrow">Perfil del usuario</div>
            <div class="profile-id">{context.get("user_id", "")}</div>
            <div class="profile-line">Tier: {context.get("tier", "")}</div>
            <div class="profile-line">Status: {context.get("status", "")}</div>
            <div class="profile-line">Edad: {context.get("age", "")}</div>
            <div class="profile-line">Score: {context.get("score", "")}</div>
            <div class="profile-line">Ciudad: {context.get("city", "")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Renderiza el contenido del asistente.
def render_payload(payload: dict, msg_idx: int) -> None:
    st.markdown(payload.get("message", ""))

    # Genera las gráficas con identificadores únicos.
    for chart_idx, figure in enumerate(payload.get("charts", [])):
        st.plotly_chart(figure, use_container_width=True, key=f"chart_{msg_idx}_{chart_idx}")

    # Muestra la tabla de datos si existe.
    if isinstance(payload.get("table"), pd.DataFrame):
        st.dataframe(payload["table"], use_container_width=True, hide_index=True)

initialize_state()
current_payload = latest_payload()

# Renderiza la cabecera principal.
st.markdown(
    """
    <div class="hero-shell">
        <div class="eyebrow">HAVI - Hey Banco</div>
        <h1 class="hero-title">Tu asistente <span class="hero-italic">inteligente</span></h1>
        <p class="hero-copy">
            Descubre información valiosa sobre tus productos financieros de Hey Banco con la ayuda de HAVI.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_metric_band(current_payload.get("metrics", []))
render_sidebar(current_payload.get("context", {}))

# Dibuja el historial de chat.
for msg_idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_payload(message["payload"], msg_idx)
        else:
            st.markdown(message["content"])

st.markdown('<div class="section-label">Siguiente paso</div>', unsafe_allow_html=True)

# Renderiza los botones de acción rápida.
current_opts = st.session_state.get("current_options", [])
if current_opts:
    button_columns = st.columns(max(len(current_opts), 1))
    for index, option in enumerate(current_opts):
        if button_columns[index].button(
            option,
            key=f"quick_action_{len(st.session_state.messages)}_{index}",
            use_container_width=True,
        ):
            append_user_turn(option)
            st.rerun()

# Renderiza la barra de entrada de texto.
if prompt := st.chat_input("Pregunta algo a HAVI..."):
    append_user_turn(prompt)
    st.rerun()