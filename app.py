import streamlit as st
import pandas as pd

st.set_page_config(page_title="Havi - Hey Banco", layout="wide")

st.title("Havi - Banco Personalizado")

# Simulación de carga de datos
st.sidebar.header("Configuración")
perfil = st.sidebar.selectbox("Seleccionar Perfil de Usuario", ["Inversionista", "Usuario con Incidencias", "Ahorrador"])

tab1, tab2 = st.tabs(["💬 Simulador de Chat", "📊 Contexto del Cliente"])

with tab1:
    st.subheader(f"Simulando interacción para: {perfil}")
    st.chat_message("assistant").write(f"Hola, soy Havi. Veo que eres un perfil {perfil}, ¿en qué puedo ayudarte?")

with tab2:
    st.write("Aquí mostraremos los datos de las 4 bases de datos una vez procesadas.")