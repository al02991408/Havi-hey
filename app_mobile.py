# -*- coding: utf-8 -*-
"""
app_mobile.py — El Cuerpo de HAVI (interfaz móvil)
====================================================
Responsabilidad ÚNICA: renderizar el payload que devuelve logic.py.

SEPARACIÓN DE RESPONSABILIDADES:
    - Este archivo NO tiene lógica de negocio. No decide qué mostrar,
      no calcula métricas y no manipula DataFrames.
    - Toda decisión de contenido ya fue tomada en logic.py y llegó aquí
      como el dict `payload` con 7 llaves exactas.
    - El patrón reactivo funciona así:
        1. El usuario toca un botón o escribe en el chat.
        2. append_user_turn() llama a logic.analyze_interaction().
        3. El nuevo payload se guarda en st.session_state.
        4. st.rerun() dispara un re-render completo.
        5. El bucle for recorre messages y llama a render_assistant_message()
           con cada payload histórico, reconstruyendo la conversación entera.

CORRECCIÓN DE BUGS:
    - StreamlitDuplicateElementId: cada st.plotly_chart() recibe un key único
      construido con el índice del mensaje Y el índice de la gráfica dentro de
      ese mensaje. Así nunca hay dos widgets con el mismo key en el mismo render.
    - Botones de opciones: el key incluye len(messages) para invalidar los
      botones del turno anterior al agregar un nuevo mensaje.
"""

from __future__ import annotations

import uuid
import pandas as pd
import streamlit as st

import logic

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HAVI Mobile | Hey Banco",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS — Dark Mode Nativo simulado
# El diseño imita una app móvil real: header fijo, área de scroll central
# y barra de navegación inferior. Todo con variables CSS para un cambio
# de tema sencillo en el futuro.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* === Variables de diseño Hey Banco === */
    :root {
        --bg-primary:   #212023;
        --bg-card:      #2a2a2e;
        --border:       #49494e;
        --text-primary: #fbf8f2;
        --text-muted:   #a9a9a9;
        --green:        #00b478;
        --red:          #fa94ae;
        --blue:         #a0cff0;
        --purple:       #b785f5;
    }

    /* Fondo global y tipografía */
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
        font-family: 'Inter', sans-serif;
    }

    /* Ocultar elementos nativos de Streamlit que rompen la ilusión móvil */
    [data-testid="stHeader"], footer, [data-testid="stSidebar"] {
        visibility: hidden;
        display: none;
    }

    /* Contenedor principal: espacio para header fijo (top) y nav fija (bottom) */
    .block-container {
        padding-top:    5rem  !important;
        padding-bottom: 6rem  !important;
        padding-left:   1rem  !important;
        padding-right:  1rem  !important;
        max-width: 600px;
        margin: auto;
    }

    /* ── Header fijo ── */
    .mobile-header {
        position: fixed;
        top: 0; left: 0; right: 0;
        height: 60px;
        background-color: var(--bg-primary);
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 1rem;
        z-index: 1000;
        border-bottom: 1px solid var(--border);
    }
    .header-icon  { font-size: 1.5rem; color: var(--text-primary); cursor: pointer; }
    .header-title { font-weight: bold; font-size: 1.2rem; color: var(--text-primary); }
    .header-avatar {
        background-color: var(--green);
        color: white;
        border-radius: 50%;
        width: 36px; height: 36px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-weight: bold;
        font-size: 1rem;
    }

    /* ── Tarjetas del dashboard superior ── */
    .dash-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100px;
    }
    .dash-card-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        color: var(--text-primary);
    }
    .dash-card-value {
        color: var(--green);
        font-size: 1.4rem;
        font-weight: bold;
        margin-top: 0.5rem;
    }

    /* ── Mensajes del chat ── */
    div[data-testid="stChatMessage"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
    }
    div[data-testid="stChatMessage"] * { color: var(--text-primary) !important; }

    /* ── Botones de acción rápida (pills móviles) ── */
    div.stButton > button {
        background-color: var(--bg-card);
        color: var(--text-primary);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        width: 100%;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    div.stButton > button:hover {
        background-color: var(--border);
        border-color: var(--text-primary);
    }

    /* ── Tarjetas de métricas inline (dentro de mensajes) ── */
    .metric-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
    }
    .metric-label { font-size: 0.8rem; color: var(--text-muted); }
    .metric-val   { font-size: 1.1rem; font-weight: bold; }
    .metric-val.positive { color: var(--green); }
    .metric-val.info     { color: var(--blue);  }
    .metric-val.negative { color: var(--red);   }

    /* ── Barra de navegación inferior fija ── */
    .bottom-nav {
        position: fixed;
        bottom: 0; left: 0; right: 0;
        height: 70px;
        background-color: var(--bg-primary);
        border-top: 1px solid var(--border);
        display: flex;
        justify-content: space-around;
        align-items: center;
        z-index: 1000;
        padding-bottom: env(safe-area-inset-bottom); /* safe area para iPhone */
    }
    .nav-icon        { font-size: 1.5rem; color: var(--text-primary); cursor: pointer; padding: 10px; border-radius: 50%; }
    .nav-icon.active { background-color: rgba(0, 180, 120, 0.2); color: var(--green); }

    /* ── Input del chat ── */
    div[data-testid="stChatInput"] {
        border-radius: 24px;
        background: var(--bg-card);
        border: 1px solid var(--border);
        color: var(--text-primary);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header fijo (componente reutilizable en HTML)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="mobile-header">
        <div class="header-icon">☰</div>
        <div class="header-title">Hey, Alex</div>
        <div class="header-avatar">A</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Dashboard Cards
# Los datos estáticos reflejan los valores del perfil USR-00001 del CSV.
# En una versión productiva estos valores vendrían del payload/context.
# ---------------------------------------------------------------------------

def render_dashboard_cards() -> None:
    """
    Renderiza las 4 tarjetas de resumen en la parte superior.

    Componente reutilizable: los valores están separados en variables para que
    sea fácil conectarlos a context["total_balance"] etc. en la siguiente iteración.
    """
    col1, col2 = st.columns(2)

    # Columna izquierda — saldo y recompensas
    with col1:
        st.markdown(
            """
            <div class="dash-card">
                <div class="dash-card-header"><span style="color:#b785f5;">💵</span> Dinero disponible</div>
                <div class="dash-card-value">$169,745.00</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="dash-card">
                <div class="dash-card-header"><span style="color:#8b6f43;">🪙</span> Recompensas</div>
                <div class="dash-card-value">$122.33</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Columna derecha — tarjeta y seguro
    with col2:
        st.markdown(
            """
            <div class="dash-card">
                <div class="dash-card-header"><span style="color:#FFD700;">💳</span> Tarjeta Hey</div>
                <div class="dash-card-value" style="color:#fbf8f2; font-size:1rem; margin-top:1rem;">Activa</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="dash-card">
                <div class="dash-card-header"><span style="color:#a0cff0;">🚙</span> Seguro de Auto</div>
                <div class="dash-card-value" style="color:#fbf8f2; font-size:1rem; margin-top:1rem;">Cotizar</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


render_dashboard_cards()
st.write("---")

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
USER_ID = logic.DEFAULT_USER_ID


def initialize_state() -> None:
    """
    Inicializa st.session_state en la primera carga de la app.

    Por qué guardamos los mensajes en session_state:
        Streamlit re-ejecuta el script completo en cada interacción del usuario.
        session_state es el único mecanismo que persiste datos entre re-renders.
        Al guardar la lista `messages_mobile`, reconstruimos el historial completo
        del chat en cada re-render sin volver a llamar a logic.analyze_interaction().

    Estructura de cada mensaje:
        {"role": "assistant", "payload": dict}   ← respuesta del motor
        {"role": "user",      "content": str}    ← texto del usuario
    """
    if "messages_mobile" not in st.session_state:
        st.session_state.messages_mobile        = []
        initial_payload                          = logic.analyze_interaction("inicio", USER_ID)
        st.session_state.messages_mobile.append({"role": "assistant", "payload": initial_payload})
        # Opciones iniciales sugeridas como botones de onboarding.
        st.session_state.current_options_mobile = initial_payload.get("options") or logic.DEFAULT_OPTIONS


def append_user_turn(user_text: str) -> None:
    """
    Añade el turno del usuario y la respuesta de HAVI al historial.

    Flujo:
        1. Llama a logic.analyze_interaction() — el motor calcula el nuevo payload.
        2. Agrega el mensaje del usuario a messages_mobile.
        3. Agrega la respuesta de HAVI (payload completo) a messages_mobile.
        4. Actualiza current_options_mobile con los botones del nuevo turno.

    NOTA: No llamamos a st.rerun() aquí. El caller (el handler del botón o el
    chat_input) es responsable de llamar a st.rerun() después de append_user_turn().
    Esto mantiene la función pura y testeable sin efectos secundarios de UI.
    """
    payload = logic.analyze_interaction(user_text, USER_ID)
    st.session_state.messages_mobile.append({"role": "user",      "content": user_text})
    st.session_state.messages_mobile.append({"role": "assistant", "payload": payload})
    st.session_state.current_options_mobile = payload.get("options") or logic.DEFAULT_OPTIONS


# ---------------------------------------------------------------------------
# Renderizado de mensajes
# ---------------------------------------------------------------------------

def render_metric_cards(metrics: list[dict]) -> None:
    """
    Renderiza las tarjetas de KPI dentro de un mensaje del asistente.

    Diseño: máximo 2 columnas en móvil para que los números sean legibles.
    El índice `i % len(m_cols)` distribuye las tarjetas en las columnas
    de forma circular (wrap) sin importar cuántas métricas haya.
    """
    if not metrics:
        return
    n_cols  = min(len(metrics), 2)
    m_cols  = st.columns(n_cols)
    for i, metric in enumerate(metrics):
        tone = metric.get("tone", "info")
        html = f"""
        <div class="metric-card">
            <div class="metric-label">{metric.get("label", "")}</div>
            <div class="metric-val {tone}">{metric.get("value", "")}</div>
        </div>
        """
        m_cols[i % n_cols].markdown(html, unsafe_allow_html=True)


def render_assistant_message(payload: dict, msg_idx: int) -> None:
    """
    Renderiza el contenido completo de un turno del asistente.

    Recibe el payload de 7 llaves y renderiza en este orden:
        1. Texto del mensaje (Markdown).
        2. Tarjetas de métricas (si existen).
        3. Gráficas Plotly (si existen).
        4. Tabla de datos (si es un DataFrame no vacío).

    FIX StreamlitDuplicateElementId:
        Cada gráfica recibe key=f"chart_{msg_idx}_{chart_idx}".
        - msg_idx: posición del mensaje en el historial (único por turno).
        - chart_idx: posición de la gráfica dentro del mensaje.
        Esta combinación garantiza unicidad incluso cuando hay múltiples
        gráficas en múltiples mensajes en el mismo render.

    Por qué NO usamos uuid.uuid4() para el key:
        uuid4() genera un ID nuevo en cada re-render. Esto causa que Streamlit
        re-cree el widget en cada ejecución, lo que produce flickering y
        desperdicia recursos. El índice posicional es determinista y estable.
    """
    # 1. Texto
    st.markdown(payload["message"])

    # 2. Métricas
    render_metric_cards(payload.get("metrics", []))

    # 3. Gráficas — key único por (mensaje, gráfica) para evitar DuplicateElementId
    for chart_idx, chart in enumerate(payload.get("charts", [])):
        st.plotly_chart(
            chart,
            use_container_width=True,
            key=f"chart_{msg_idx}_{chart_idx}",   # ← FIX del bug
        )

    # 4. Tabla
    table = payload.get("table")
    if isinstance(table, pd.DataFrame) and not table.empty:
        st.dataframe(table, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Inicialización y renderizado del chat
# ---------------------------------------------------------------------------

initialize_state()

# Bucle reactivo: recorre todo el historial de mensajes.
# En cada re-render de Streamlit este bucle reconstruye el chat completo
# desde session_state. No hay "render incremental" — Streamlit siempre
# dibuja todo desde cero, y session_state provee la memoria.
for msg_idx, message in enumerate(st.session_state.messages_mobile):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_assistant_message(message["payload"], msg_idx)
        else:
            st.markdown(message["content"])

# ---------------------------------------------------------------------------
# Botones de acción rápida (opciones sugeridas)
# ---------------------------------------------------------------------------
if st.session_state.current_options_mobile:
    st.write("<br>", unsafe_allow_html=True)
    # Una opción por fila en móvil — más fácil de tocar que columnas estrechas.
    for idx, option in enumerate(st.session_state.current_options_mobile):
        # Key incluye len(messages) para que los botones del turno anterior
        # sean distintos a los del turno actual y no generen DuplicateElementId.
        if st.button(option, key=f"btn_{len(st.session_state.messages_mobile)}_{idx}"):
            append_user_turn(option)
            st.rerun()

# ---------------------------------------------------------------------------
# Input de texto libre
# ---------------------------------------------------------------------------
st.write("<br><br>", unsafe_allow_html=True)
if prompt := st.chat_input("Escribe a HAVI..."):
    append_user_turn(prompt)
    st.rerun()

# ---------------------------------------------------------------------------
# Barra de navegación inferior (simulada con HTML)
# El ícono activo (🤖) representa la pantalla actual de HAVI.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="bottom-nav">
        <div class="nav-icon">🏠</div>
        <div class="nav-icon">🪙</div>
        <div class="nav-icon active">🤖</div>
        <div class="nav-icon">🔁</div>
        <div class="nav-icon">📩</div>
    </div>
    """,
    unsafe_allow_html=True,
)