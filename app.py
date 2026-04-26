from __future__ import annotations

import pandas as pd
import streamlit as st

import logic
from utils.styles import apply_styles


st.set_page_config(page_title="HAVI | Hey Banco", layout="wide")
apply_styles()

USER_ID = logic.DEFAULT_USER_ID


def initialize_state() -> None:
    if "messages" in st.session_state:
        return

    initial_payload = logic.analyze_interaction("", USER_ID)
    st.session_state.messages = [{"role": "assistant", "payload": initial_payload}]
    st.session_state.current_options = initial_payload["options"]


def render_metric_band(metrics: list[dict]) -> None:
    visible_metrics = metrics[:3]
    columns = st.columns(3)
    for column, metric in zip(columns, visible_metrics):
        delta_html = f'<div class="metric-delta">{metric["delta"]}</div>' if metric.get("delta") else ""
        column.markdown(
            f"""
            <div class="kpi-card tone-{metric["tone"]}">
                <div class="metric-label">{metric["label"]}</div>
                <div class="metric-value">{metric["value"]}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(context: dict) -> None:
    st.sidebar.markdown(
        f"""
        <div class="profile-card">
            <div class="profile-eyebrow">Perfil del usuario</div>
            <div class="profile-id">{context["user_id"]}</div>
            <div class="profile-line">Tier: {context["tier"]}</div>
            <div class="profile-line">Status: {context["status"]}</div>
            <div class="profile-line">Edad: {context["age"]}</div>
            <div class="profile-line">Score: {context["score"]}</div>
            <div class="profile-line">Ciudad: {context["city"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_payload(payload: dict, msg_idx: int) -> None:
    st.markdown(payload["message"])

    for chart_idx, figure in enumerate(payload["charts"]):
        st.plotly_chart(figure, width="stretch", key=f"chart_{msg_idx}_{chart_idx}")

    if isinstance(payload["table"], pd.DataFrame):
        st.dataframe(payload["table"], width="stretch", hide_index=True)


def append_user_turn(user_text: str) -> None:
    payload = logic.analyze_interaction(user_text, USER_ID)
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.messages.append({"role": "assistant", "payload": payload})
    st.session_state.current_options = payload["options"] or logic.DEFAULT_OPTIONS


def latest_payload() -> dict:
    for message in reversed(st.session_state.messages):
        if message["role"] == "assistant":
            return message["payload"]
    return logic.analyze_interaction("", USER_ID)


initialize_state()
current_payload = latest_payload()

st.markdown(
    """
    <div class="hero-shell">
        <div class="eyebrow">HAVI - Hey Banco</div>
        <h1 class="hero-title">Tu asistente <span class="hero-italic">inteligente</span></h1>
        <p class="hero-copy">
            Dashboard conversacional con analisis real de USR-00001, evidencia visual y rutas claras para demo.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_metric_band(current_payload["metrics"])
render_sidebar(current_payload["context"])

for msg_idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_payload(message["payload"], msg_idx)
        else:
            st.markdown(message["content"])

st.markdown('<div class="section-label">Siguiente paso</div>', unsafe_allow_html=True)
button_columns = st.columns(max(len(st.session_state.current_options), 1))
for index, option in enumerate(st.session_state.current_options):
    if button_columns[index].button(
        option,
        key=f"quick_action_{len(st.session_state.messages)}_{index}",
        use_container_width=True,
    ):
        append_user_turn(option)
        st.rerun()

if prompt := st.chat_input("Pregunta algo a HAVI..."):
    append_user_turn(prompt)
    st.rerun()
