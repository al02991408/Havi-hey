from __future__ import annotations

import pandas as pd
import streamlit as st

import logic
from utils.styles import apply_custom_styles


st.set_page_config(page_title="HAVI | Hey Banco", layout="wide")
apply_custom_styles()

USER_ID = logic.DEFAULT_USER_ID

TONE_MAP = {
    "neutral": {"accent": "#212023", "surface": "#fbf8f2", "badge": "#a0cff0"},
    "positive": {"accent": "#00b478", "surface": "#ecfbf4", "badge": "#00b478"},
    "negative": {"accent": "#fa94ae", "surface": "#fff0f4", "badge": "#fa94ae"},
}


def initialize_state() -> None:
    if "messages" in st.session_state:
        return

    initial_payload = logic.analyze_interaction("Inicio", USER_ID)
    st.session_state.messages = [{"role": "assistant", "payload": initial_payload}]
    st.session_state.current_options = initial_payload["options"]


def apply_tone_overrides(payload: dict) -> None:
    tone = TONE_MAP.get(payload["context"].get("ui_tone", "neutral"), TONE_MAP["neutral"])
    st.markdown(
        f"""
        <style>
        :root {{
            --journey-accent: {tone["accent"]};
            --journey-surface: {tone["surface"]};
            --journey-badge: {tone["badge"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_strip(metrics: list[dict]) -> None:
    columns = st.columns(3)
    for column, metric in zip(columns, metrics[:3]):
        delta_html = f'<div class="kpi-delta">{metric["delta"]}</div>' if metric.get("delta") else ""
        column.markdown(
            f"""
            <div class="kpi-card kpi-{metric["tone"]}">
                <div class="kpi-label">{metric["label"]}</div>
                <div class="kpi-value">{metric["value"]}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(context: dict) -> None:
    st.sidebar.markdown(
        f"""
        <div class="profile-card">
            <div class="profile-eyebrow">Perfil maestro</div>
            <div class="profile-name">{context["name"]}</div>
            <div class="profile-tier">{context["tier"]}</div>
            <div class="profile-status tone-{context["status_tone"]}">
                <span class="status-dot"></span>
                <span>{context["status"]}</span>
            </div>
            <div class="profile-line">Edad: {context["age"]}</div>
            <div class="profile-line">Ciudad: {context["city"]}</div>
            <div class="profile-line">Score Buró: {context["score"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_journey_badge(payload: dict) -> None:
    badge_copy = {
        "retention": "Ruta activa: Retención",
        "onboarding": "Ruta activa: Onboarding",
        "finanzas": "Ruta activa: Finanzas",
        "rendimientos": "Ruta activa: Inversión",
        "soporte": "Ruta activa: Soporte",
    }
    label = badge_copy.get(payload["intent"])
    if not label:
        return
    st.markdown(f'<div class="journey-badge">{label}</div>', unsafe_allow_html=True)


def render_payload(payload: dict) -> None:
    render_journey_badge(payload)
    st.markdown(payload["message"])

    for figure in payload["charts"]:
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

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
    return logic.analyze_interaction("Inicio", USER_ID)


initialize_state()
current_payload = latest_payload()
apply_tone_overrides(current_payload)

st.markdown(
    """
    <div class="hero-wrap">
        <div class="hero-brand">hey,banco</div>
        <div class="hero-headline">Tu asistente <span class="hero-italic">inteligente</span></div>
        <div class="hero-subtitle">
            Respuestas accionables, lectura ejecutiva y una experiencia conversacional lista para la demo final.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_kpi_strip(current_payload["metrics"])
render_sidebar(current_payload["context"])

for index, message in enumerate(st.session_state.messages):
    avatar = "🟢" if message["role"] == "assistant" else "🙂"
    with st.chat_message(message["role"], avatar=avatar):
        if message["role"] == "assistant":
            render_payload(message["payload"])
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

if prompt := st.chat_input("Escribe tu consulta a HAVI..."):
    append_user_turn(prompt)
    st.rerun()
