import streamlit as st
import pandas as pd

# 1. Configuración de Marca y Estilo Oficial
st.set_page_config(page_title="HAVI | Hey Banco", page_icon="🏦", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,700;0,900;1,400&display=swap');

    .stApp {
        background-color: #F9F8F3;
        font-family: 'Inter', sans-serif;
    }

    .block-container {
        padding: 2rem 5rem !important;
        max-width: 900px;
    }

    h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 900 !important;
        color: #1A1A1A !important;
        font-size: 4rem !important;
        line-height: 0.95;
        letter-spacing: -0.05em;
        text-align: center;
    }

    .bold-italic { font-style: italic; font-weight: 400; }

    /* Tarjeta del Bot */
    .bot-card {
        background-color: #FFFFFF;
        border-radius: 32px;
        padding: 40px;
        border: 1px solid #ECEBE6;
        box-shadow: 0 10px 30px rgba(0,0,0,0.02);
    }

    /* Botones de Opciones Rápidas */
    div.stButton > button {
        background-color: #FFFFFF;
        color: #1A1A1A;
        border: 1px solid #1A1A1A;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    div.stButton > button:hover {
        background-color: #1A1A1A;
        color: #FFFFFF;
    }

    /* Botón de Acceso Superior */
    .login-btn {
        float: right;
        background-color: #3D3D3F !important;
        color: white !important;
    }

    [data-testid="stHeader"], footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

# 2. Navegación
nav_l, nav_r = st.columns([4, 1])
with nav_l:
    st.image("https://banco.hey.inc/content/dam/heybanco/globales/hey-banco-logo.svg", width=110)
with nav_r:
    st.button("Acceso", key="login")

# 3. Hero Section
st.markdown('<h1 style="margin-top:40px;">Tu asistente <span class="bold-italic">inteligente</span></h1>', unsafe_allow_html=True)
st.write("<br>", unsafe_allow_html=True)

# 4. Interfaz de Bot Simplificada
st.markdown('<div class="bot-card">', unsafe_allow_html=True)

# Mensaje inicial del bot
st.chat_message("assistant").write("¡Hola! Soy **HAVI**. Analicé tus movimientos y tengo algunas sugerencias para ti hoy. ¿En qué prefieres enfocarte?")

st.write("---")

# Botones de Opciones (Simulando interacción dinámica)
col_opt1, col_opt2, col_opt3 = st.columns(3)

with col_opt1:
    if st.button("📈 Ver Rendimientos"):
        st.info("Tus inversiones han crecido un **5.2%** este mes.")
with col_opt2:
    if st.button("💰 Plan de Ahorro"):
        st.success("Puedes ahorrar **$1,200 MXN** extra ajustando tus gastos en 'Restaurantes'.")
with col_opt3:
    if st.button("💳 Mi Tarjeta"):
        st.warning("Tu fecha de corte es en 3 días. ¿Quieres programar el pago?")

st.markdown('</div>', unsafe_allow_html=True)

# Input de texto opcional al final
st.write("<br>", unsafe_allow_html=True)
st.chat_input("O escribe otra duda aquí...")