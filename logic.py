"""
logic.py — El Cerebro de HAVI
==============================
Motor de análisis financiero 100% desacoplado de la UI.

CONTRATO DE INTERFAZ (invariante):
    analyze_interaction(user_input, user_id) → dict con SIEMPRE estas 7 llaves:
        {
            "message": str,        # Texto que HAVI muestra al usuario
            "options": list[str],  # Botones de siguiente paso
            "charts": list,        # Lista de figuras Plotly (puede estar vacía)
            "metrics": list[dict], # KPIs para la banda superior
            "table": pd.DataFrame | None,
            "intent": str,         # Etiqueta del flujo detectado
            "context": dict,       # Snapshot del perfil del usuario
        }

GESTIÓN DE ESTADO CONVERSACIONAL:
    logic.py NO almacena estado propio entre llamadas. El estado conversacional
    (ej. en qué paso del flujo de tarjeta está el usuario) vive en st.session_state
    de Streamlit y se comunica implícitamente a través del texto del user_input.
    _detect_intent() re-evalúa el intent desde cero en cada turno examinando
    las keywords presentes en el input, lo que hace el sistema stateless y por
    ende fácil de testear (test_logic.py no necesita ningún mock de sesión).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Rutas de datos
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent / "data"
MASTER_CLIENTS_PATH = DATA_DIR / "base_maestra_clientes.csv"
PRODUCTS_PATH       = DATA_DIR / "hey_productos.csv"
TRANSACTIONS_PATH   = DATA_DIR / "hey_transacciones.csv"
USER_TRANSACTIONS_PATH = DATA_DIR / "hey_transacciones_usr_00001.csv"

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------
DEFAULT_USER_ID = "USR-00001"

# Opciones de fallback: se usan si un payload no define las suyas propias.
DEFAULT_OPTIONS = [
    "📊 Analizar mis Gastos",
    "📈 Empezar a Invertir",
    "🛡️ Configurar Seguridad",
]

# Paleta de colores alineada con la identidad de Hey Banco.
PLOTLY_SCALE = ["#8b6f43", "#964831", "#2b497d", "#546436"]

# Conjunto de tipos de operación que representan SALIDAS de dinero.
# Usado para calcular gastos, capacidad de inversión y top categorías.
OUTGOING_OPERATIONS = {
    "compra",
    "transf_salida",
    "retiro_cajero",
    "pago_servicio",
    "pago_credito",
    "cargo_recurrente",
    "abono_inversion",
}

# ---------------------------------------------------------------------------
# Diccionarios de keywords para detección de intents
# Principio: cada keyword set es excluyente y ordenado por prioridad en
# _detect_intent(). El orden de evaluación importa (card_onboarding > onboarding
# > retention > rendimientos > finanzas > soporte).
# ---------------------------------------------------------------------------

RETENTION_KEYWORDS = (
    "cancelar",
    "cancelación",
    "cancelacion",
    "cerrar cuenta",
    "cerrar mi cuenta",
    "dar de baja",
    "baja mi cuenta",
)

ONBOARDING_KEYWORDS = (
    "inicio",
    "empezar",
    "bienvenida",
    "bienvenido",
    "nuevo usuario",
    "nueva cuenta",
)

INVESTMENT_KEYWORDS = (
    "rendimientos",
    "rendimiento",
    "inversión",
    "inversion",
    "invertir",
    "capacidad",
    "portafolio",
)

FINANCE_KEYWORDS = (
    "finanzas",
    "gastos",
    "gasto",
    "ingresos",
    "flujo",
    "presupuesto",
    "cashback",
    "saldo",
    "analizar",
)

CARD_BLOCK_KEYWORDS = (
    "bloquear",
    "bloquea",
    "bloqueo",
    "tarjeta robada",
    "tarjeta perdida",
    "perdí mi tarjeta",
    "perdi mi tarjeta",
)

CHARGE_KEYWORDS = (
    "no reconozco",
    "cargo",
    "cobro",
    "fraude",
    "estafa",
    "movimiento extraño",
    "movimiento extrano",
)

SECURITY_KEYWORDS = (
    "seguridad",
    "nip",
    "contraseña",
    "contrasena",
    "app",
    "acceso",
    "login",
)

SUPPORT_KEYWORDS = (
    CARD_BLOCK_KEYWORDS
    + CHARGE_KEYWORDS
    + SECURITY_KEYWORDS
    + (
        "soporte",
        "ayuda",
        "problema",
        "error",
        "asesor",
        "humano",
    )
)

# Keywords que activan el flujo guiado de solicitud de tarjeta física.
# Incluye la frase inicial y las respuestas del usuario en los pasos 1 y 2.
CARD_ONBOARDING_KEYWORDS = (
    "solicitar tarjeta física",
    "solicitar tarjeta fisica",
    "tarjeta física",
    "tarjeta fisica",
    "ya estoy en tarjeta",           # paso 1 → paso 2
    "💳 ya estoy en tarjeta",        # variante con emoji desde botón
    "enviar a este domicilio",        # paso 2 → confirmación
    "✅ sí, enviar a este domicilio", # variante con emoji desde botón
    "sí, enviar a este domicilio",
    "si, enviar a este domicilio",
)


# ===========================================================================
# CARGA DE DATOS (cacheada con st.cache_data)
# ===========================================================================

@st.cache_data(show_spinner=False)
def load_master_clients() -> tuple[pd.DataFrame | None, str | None]:
    """
    Carga base_maestra_clientes.csv y normaliza columnas numéricas clave.

    Returns:
        (DataFrame, None) si éxito.
        (None, nombre_fuente) si falla — el llamador mostrará un payload de mantenimiento.

    Diseño: el patrón (data, error) evita exceptions silenciosas y permite
    que analyze_interaction() tome la decisión de qué mostrar al usuario
    sin propagar un traceback a la UI.
    """
    try:
        df = pd.read_csv(MASTER_CLIENTS_PATH, encoding="utf-8")
        numeric_cols = [
            "edad",
            "ingreso_mensual_mxn",
            "score_buro",
            "saldo_total",
            "limite_credito_total",
            "utilizacion_promedio",
            "monto_total",
            "cashback_total",
            "n_transacciones",
            "n_transacciones_no_procesadas",
            "pct_transacciones_internacionales",
            "antiguedad_dias",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df, None
    except Exception:
        return None, "base maestra"


@st.cache_data(show_spinner=False)
def load_products() -> tuple[pd.DataFrame | None, str | None]:
    """
    Carga hey_productos.csv con solo las columnas necesarias para el demo.
    El subset de columnas reduce memoria y hace explícito qué campos usa el motor.
    """
    try:
        df = pd.read_csv(
            PRODUCTS_PATH,
            encoding="utf-8",
            usecols=[
                "user_id",
                "tipo_producto",
                "estatus",
                "saldo_actual",
                "limite_credito",
                "utilizacion_pct",
                "tasa_interes_anual",
            ],
        )
        for col in ("saldo_actual", "limite_credito", "utilizacion_pct", "tasa_interes_anual"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df, None
    except Exception:
        return None, "productos"


@st.cache_data(show_spinner=False)
def load_user_transactions(user_id: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Carga transacciones del usuario especificado.

    Optimización para USR-00001 en demo: si existe el CSV pre-filtrado
    (hey_transacciones_usr_00001.csv), lo usa directamente sin iterar sobre
    el CSV completo. Para cualquier otro user_id, lee el CSV master en chunks
    de 100k filas para no saturar RAM (el archivo puede ser >1M de rows).

    La columna `month` (YYYY-MM) se deriva aquí una vez para que todos los
    payloads que necesiten agrupar por mes no repitan el slice.
    """
    try:
        use_prefiltered = user_id == DEFAULT_USER_ID and USER_TRANSACTIONS_PATH.exists()
        preferred_path = USER_TRANSACTIONS_PATH if use_prefiltered else TRANSACTIONS_PATH

        cols = [
            "user_id",
            "fecha_hora",
            "tipo_operacion",
            "monto",
            "categoria_mcc",
            "estatus",
            "es_internacional",
        ]

        chunks: list[pd.DataFrame] = []
        for chunk in pd.read_csv(preferred_path, encoding="utf-8", usecols=cols, chunksize=100_000):
            # Si usamos el CSV master necesitamos filtrar; el pre-filtrado no.
            filtered = chunk if use_prefiltered else chunk.loc[chunk["user_id"] == user_id].copy()
            if not filtered.empty:
                chunks.append(filtered)

        df = (
            pd.concat(chunks, ignore_index=True)
            if chunks
            else pd.DataFrame(columns=cols)
        )

        df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0.0)
        df["es_internacional"] = df["es_internacional"].fillna(False).astype(bool)
        # month como string YYYY-MM para groupby y ejes X en gráficas.
        df["month"] = df["fecha_hora"].astype(str).str.slice(0, 7) if not df.empty else pd.Series(dtype="object")

        return df, None
    except Exception:
        return None, "transacciones"


# ===========================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ===========================================================================
def analyze_interaction(user_input: str, user_id: str = DEFAULT_USER_ID, recent_topics: list = None) -> dict:
    recent_topics = recent_topics or []
    
    try:
        master_clients, master_error = load_master_clients()
        products,       prod_error   = load_products()
        user_tx,        tx_error     = load_user_transactions(user_id)

        failed_source = master_error or prod_error or tx_error
        if failed_source or master_clients is None or products is None or user_tx is None:
            return _maintenance_payload(user_id, failed_source or "datos")

        context = get_user_context(user_id, master_clients, products, user_tx)
        intent  = _detect_intent(user_input, context)

        if intent == "card_onboarding":
            return _build_card_onboarding_payload(user_input, context)
        if intent == "onboarding":
            return _build_onboarding_payload(context)
        if intent == "retention":
            return _build_retention_payload(context, products)
        if intent == "rendimientos":
            return _build_rendimientos_payload(context, user_tx)
        if intent == "finanzas":
            return _build_finanzas_payload(context, user_tx)

        # MODIFICADO: Enviar recent_topics al flujo de soporte
        return _build_support_payload(context, user_tx, user_input, recent_topics)

    except Exception:
        return _maintenance_payload(user_id, "sistema")


def _build_support_payload(context: dict, user_transactions: pd.DataFrame, user_input: str, recent_topics: list) -> dict:
    text = (user_input or "").strip().lower()
    if any(kw in text for kw in CARD_BLOCK_KEYWORDS):
        return _build_card_block_payload(context)
    if any(kw in text for kw in CHARGE_KEYWORDS):
        return _build_charge_payload(context, user_transactions)
    if any(kw in text for kw in SECURITY_KEYWORDS):
        return _build_security_payload(context)
    
    # MODIFICADO: Pasar tópicos a la ayuda genérica
    return _build_generic_help_payload(context, recent_topics)


def _build_generic_help_payload(context: dict, recent_topics: list) -> dict:
    options = ["Analizar mis Gastos", "Configurar Seguridad", "Centro de Ayuda"]
    
    # NUEVO: Lógica para inyectar opciones basadas en el historial del usuario
    if "finanzas" in recent_topics:
        options.insert(0, "Revisar Presupuesto Mensual")
    if "rendimientos" in recent_topics:
        options.insert(0, "Ver Proyección de Inversión")
    if "card_onboarding" in recent_topics:
        options.insert(0, "Rastrear Envío de Tarjeta")
        
    options = options[:4]

    message = (
        f"{context['name']}, estoy aquí para resolverlo contigo.\n\n"
        "He guardado el contexto de nuestras interacciones. Cuéntame qué necesitas o elige "
        "una de las opciones rápidas para retomar un tema pendiente."
    )
    return {
        "message": message,
        "options": options,
        "charts":  [],
        "metrics": _support_metrics(context, "Acompañamiento activo"),
        "table":   None,
        "intent":  "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


# ===========================================================================
# CONTEXTO DE USUARIO
# ===========================================================================

def get_user_context(
    user_id: str,
    master_clients: pd.DataFrame,
    products: pd.DataFrame,
    user_transactions: pd.DataFrame,
) -> dict:
    """
    Construye el snapshot de KPIs del usuario a partir de los tres DataFrames.

    El dict resultante es inmutable durante un turno: los builders de payload
    hacen `{**context, "ui_tone": "..."}` para obtener versiones derivadas
    sin modificar el original (patrón de copia superficial / structural sharing).

    Campos clave:
        tier          → "Hey Pro" o "Hey Banco" según es_hey_pro en el CSV.
        new_user      → True si antigüedad ≤ 45 días; activa el flujo onboarding.
        has_investment→ True si existe algún producto tipo "inversion" activo.
        preferred_rate→ Tasa de interés mínima entre los productos del usuario
                        (la más baja es la más beneficiosa para él).
    """
    row = master_clients.loc[master_clients["user_id"] == user_id]
    if row.empty:
        return _empty_context(user_id)

    client       = row.iloc[0]
    user_prods   = products.loc[products["user_id"] == user_id].copy()
    top_category = _top_spending_category(user_transactions)

    has_investment = bool(
        user_prods["tipo_producto"]
        .astype(str)
        .str.contains("inversion", case=False, na=False)
        .any()
    )
    # .replace(0, pd.NA) excluye productos sin tasa registrada antes de sacar el mínimo.
    preferred_rate = _safe_number(
        user_prods["tasa_interes_anual"].replace(0, pd.NA).dropna().min()
    )

    return {
        "user_id":           user_id,
        "name":              "Alex" if user_id == DEFAULT_USER_ID else user_id,
        "tier":              "Hey Pro" if bool(client.get("es_hey_pro")) else "Hey Banco",
        "status":            str(client.get("satisfaccion_cliente", "Neutral")),
        "status_tone":       _status_tone(str(client.get("satisfaccion_cliente", "Neutral"))),
        "age":               int(_safe_number(client.get("edad"))),
        "city":              str(client.get("ciudad", "Sin datos")),
        "score":             int(_safe_number(client.get("score_buro"))),
        "income_monthly":    _safe_number(client.get("ingreso_mensual_mxn")),
        "total_balance":     _safe_number(client.get("saldo_total")),
        "cashback_total":    _safe_number(client.get("cashback_total")),
        "total_amount":      _safe_number(client.get("monto_total")),
        "top_category":      top_category,
        "has_investment":    has_investment,
        "credit_limit_total":_safe_number(client.get("limite_credito_total")),
        "utilization_average":_safe_number(client.get("utilizacion_promedio")),
        "account_age_days":  int(_safe_number(client.get("antiguedad_dias"))),
        "preferred_rate":    preferred_rate,
        "new_user":          bool(_safe_number(client.get("antiguedad_dias")) <= 45),
        "ui_tone":           "neutral",
    }


# ===========================================================================
# DETECCIÓN DE INTENT
# ===========================================================================

def _detect_intent(user_input: str, context: dict) -> str:
    """
    Clasifica el input en uno de 6 intents usando matching de substrings.

    Prioridad explícita (mayor a menor):
        1. card_onboarding  — flujo de solicitud de tarjeta física (multi-paso)
        2. onboarding       — bienvenida o usuario nuevo (antigüedad ≤ 45 días)
        3. retention        — palabras de cancelación / baja
        4. rendimientos     — inversión, portafolio, rendimientos
        5. finanzas         — gastos, saldo, cashback, presupuesto
        6. soporte          — todo lo demás (bloqueos, cargos, seguridad, ayuda)

    Por qué substring y no NLP:
        - Velocidad de ejecución sin dependencias extra (spaCy, etc.).
        - Determinismo total: facilita pruebas unitarias sin mocks.
        - Suficiente para un demo controlado donde las opciones guían al usuario.
    """
    text = (user_input or "").strip().lower()

    # card_onboarding tiene prioridad máxima porque sus keywords son específicas
    # y forman parte de un flujo multi-paso que no debe confundirse con onboarding genérico.
    if any(kw in text for kw in CARD_ONBOARDING_KEYWORDS):
        return "card_onboarding"

    # Sin input, el usuario llegó por primera vez → onboarding.
    # También si el usuario regresó al inicio (botón "🏠 Volver al Inicio").
    if (
        not text
        or text == "inicio"
        or text == "🏠 volver al inicio"
        or context.get("new_user")
        or any(kw in text for kw in ONBOARDING_KEYWORDS)
    ):
        return "onboarding"

    if any(kw in text for kw in RETENTION_KEYWORDS):
        return "retention"
    if any(kw in text for kw in INVESTMENT_KEYWORDS):
        return "rendimientos"
    if any(kw in text for kw in FINANCE_KEYWORDS):
        return "finanzas"
    if any(kw in text for kw in SUPPORT_KEYWORDS):
        return "soporte"

    # Fallback seguro: soporte genérico nunca deja al usuario sin respuesta.
    return "soporte"


# ===========================================================================
# BUILDERS DE PAYLOAD
# ===========================================================================

def _build_card_onboarding_payload(user_input: str, context: dict) -> dict:
    """
    Flujo conversacional de 3 pasos para solicitar tarjeta física.

    GESTIÓN DE ESTADO implícita:
        El estado del flujo NO se almacena en una variable global. En cambio,
        _detect_intent() redirige a este builder cada vez que el input contiene
        una keyword del flujo. Dentro de este builder, el texto del input determina
        en qué paso se encuentra el usuario:

            Texto sin "ya estoy" ni "enviar" → Paso 0: inicio del flujo.
            "ya estoy en tarjeta"             → Paso 1: usuario llegó a la sección.
            "enviar a este domicilio"         → Paso 2: confirmación y cierre.

        Esto es intencional: al no depender de un índice de paso almacenado en
        sesión, el flujo es idempotente y resiliente a recargas de página.

    Beneficio Hey Pro:
        Si context["tier"] == "Hey Pro" se inyecta el texto de envío gratuito.
        La condición vive aquí (en el cerebro) y no en la UI, garantizando que
        la lógica de negocio no se filtre a app_mobile.py.
    """
    text = (user_input or "").strip().lower()

    # ------------------------------------------------------------------
    # PASO 2 — Usuario confirmó domicilio; solicitud aprobada
    # ------------------------------------------------------------------
    if "enviar a este domicilio" in text:
        message = (
            f"¡Todo listo, {context['name']}! 🎉\n\n"
            "Tu tarjeta física ha sido solicitada exitosamente. "
            "Llegará en **3 a 5 días hábiles** al domicilio registrado. "
            "Te notificaremos por push cuando salga a reparto."
        )
        options = ["🏠 Volver al Inicio", "📊 Analizar mis Gastos"]
        metrics = [
            _metric("Estatus",    "✅ Aprobada",  "Solicitud procesada",      "positive"),
            _metric("Llegada",    "3-5 Días",     "Días hábiles",             "info"),
            _metric("Costo envío","$0.00 MXN",    "Beneficio Hey Pro",        "positive"),
        ]

    # ------------------------------------------------------------------
    # PASO 1 — Usuario llegó a la sección de tarjeta en la app
    # ------------------------------------------------------------------
    elif "ya estoy en tarjeta" in text:
        city = context.get("city", "tu ciudad")
        message = (
            f"Perfecto, {context['name']}. Estás a un paso.\n\n"
            f"He detectado tu domicilio registrado en **{city}**. "
            "¿Es correcto para el envío?"
        )
        options = [
            "✅ Sí, enviar a este domicilio",
            "✏️ Modificar dirección",
        ]
        metrics = [
            _metric("Dirección", city, "Domicilio registrado", "info"),
        ]

    # ------------------------------------------------------------------
    # PASO 0 — Primera vez que el usuario toca el flujo de tarjeta
    # ------------------------------------------------------------------
    else:
        # La lógica de negocio (envío gratis para Hey Pro) vive aquí, no en la UI.
        pro_msg = (
            "Como eres cliente **Hey Pro**, tu tarjeta física tiene **envío sin costo**. "
        ) if context.get("tier") == "Hey Pro" else ""

        message = (
            f"¡Hola {context['name']}! {pro_msg}\n\n"
            "Vamos a solicitar tu tarjeta física en 3 pasos simples:\n\n"
            "**Paso 1:** Abre la app y ve a la sección **Mis Productos**.\n"
            "Toca la tarjeta amarilla Hey para ver sus opciones.\n\n"
            "Cuando llegues a esa pantalla, presiona el botón de abajo."
        )
        options = [
            "💳 Ya estoy en Tarjeta",
            "❌ Cancelar",
        ]
        metrics = []

    return {
        "message":  message,
        "options":  options,
        "charts":   [],
        "metrics":  metrics,
        "table":    None,
        "intent":   "card_onboarding",
        "context":  context,
    }


def _build_onboarding_payload(context: dict) -> dict:
    """
    Payload de bienvenida / primera sesión.

    La tabla de herramientas actúa como menú visual — más impactante que
    una lista de texto plano para el pitch del Datathon.
    """
    context = {**context, "ui_tone": "positive"}

    table = pd.DataFrame([
        {"herramienta": "📊 Analizar mis Gastos",    "qué verás": "Patrones, alertas y oportunidades",     "estado": "Listo"},
        {"herramienta": "📈 Empezar a Invertir",      "qué verás": "Capacidad mensual y ruta sugerida",     "estado": "Disponible"},
        {"herramienta": "💳 Solicitar Tarjeta Física","qué verás": "Envío gratis para clientes Hey Pro",    "estado": "Listo"},
        {"herramienta": "🛡️ Configurar Seguridad",   "qué verás": "Bloqueos, alertas y control de accesos","estado": "Recomendado"},
        {"herramienta": "🆘 Centro de Ayuda",         "qué verás": "Soporte guiado y escalamiento humano",  "estado": "Activo"},
    ])

    pro_banner = (
        "\n\n✨ **Eres cliente Hey Pro** — tienes tarjeta física sin costo, tasa preferencial y soporte prioritario."
        if context.get("tier") == "Hey Pro" else ""
    )

    return {
        "message": (
            f"¡Bienvenido al Universo Hey, {context['name']}! Soy **HAVI**, tu asistente de inteligencia financiera."
            f"{pro_banner}\n\n"
            "Puedo ayudarte a entender tus gastos, activar tu ruta de inversión, solicitar tu tarjeta física, "
            "configurar seguridad y resolver dudas con respuestas accionables en lenguaje natural."
        ),
        "options": [
            "📊 Analizar mis Gastos",
            "📈 Empezar a Invertir",
            "💳 Solicitar Tarjeta Física",
            "🛡️ Configurar Seguridad",
        ],
        "charts": [],
        "metrics": [
            _metric("Saldo disponible", _format_currency(context["total_balance"]), "Cuenta activa",         "positive"),
            _metric("Score Buró",       str(context["score"]),                       context["tier"],          "info"),
            _metric("Cashback acum.",   _format_currency(context["cashback_total"]), "Listo para usar",       "positive"),
        ],
        "table":   table,
        "intent":  "onboarding",
        "context": context,
    }


def _build_retention_payload(context: dict, products: pd.DataFrame) -> dict:
    """
    Flujo de retención: muestra el costo real de cancelar la cuenta.

    Estrategia de persuasión basada en datos:
        1. Cashback acumulado que se perdería → pérdida tangible inmediata.
        2. Impacto estimado en score buró → consecuencia a mediano plazo.
        3. Gráfica comparativa pérdida vs. valor retenido → golpe visual.
    """
    user_prods     = products.loc[products["user_id"] == context["user_id"]].copy()
    preferred_rate = context["preferred_rate"] or _safe_number(
        user_prods["tasa_interes_anual"].replace(0, pd.NA).dropna().min()
    )
    score_drop = _estimate_score_drop(context)

    comparison = pd.DataFrame({
        "escenario": ["Cancelar hoy", "Conservar beneficios"],
        "impacto":   [
            context["cashback_total"] + score_drop,
            max(context["cashback_total"] * 1.2, 150.0),
        ],
        "lectura": ["Pérdidas", "Valor retenido"],
    })

    chart = _style_figure(
        px.bar(
            comparison,
            x="escenario",
            y="impacto",
            color="escenario",
            title="Impacto financiero: cancelar vs. conservar",
            color_discrete_sequence=["#fa94ae", "#00b478"],
            text_auto=".2f",
        )
    )

    context   = {**context, "ui_tone": "negative"}
    rate_note = f" Tu tasa preferencial actual ronda el {preferred_rate:.2f}%." if preferred_rate else ""

    message = (
        f"{context['name']}, lamento que consideres dejarnos. Antes de proceder, detecté que tienes "
        f"**{_format_currency(context['cashback_total'])}** de cashback sin utilizar y tu estatus Hey Pro "
        f"te otorga una tasa preferencial que perderías hoy.{rate_note}\n\n"
        f"Si cierras tu cuenta hoy, podrías ver una presión estimada de **{score_drop} puntos** "
        "en tu historial por reducir antigüedad y modificar tu utilización reportada. "
        "Puedo ayudarte a explorar alternativas antes de que tomes la decisión final."
    )

    return {
        "message": message,
        "options": ["💬 Hablar con un Humano", "🎁 Ver Beneficios Pro", "⚙️ Continuar Proceso"],
        "charts":  [chart],
        "metrics": [
            _metric("Cashback en riesgo",  _format_currency(context["cashback_total"]), "Se pierde al cerrar",             "negative"),
            _metric("Impacto estimado",    f"-{score_drop} pts",                        "Score Buró potencial",            "negative"),
            _metric("Score actual",        str(context["score"]),                        "Mantener cuenta ayuda estabilidad","positive"),
        ],
        "table":   None,
        "intent":  "retention",
        "context": context,
    }


def _build_finanzas_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    """
    Análisis de gastos: ingreso vs. gasto observado + top 5 categorías.

    Dos gráficas:
        1. Bar chart ingreso vs. gasto total (visión macro).
        2. Bar chart top 5 categorías de gasto (visión táctica).

    La tabla adjunta replica las categorías para facilitar la lectura de números exactos.
    """
    top_cats    = _top_categories_frame(user_transactions)
    compare_frame = pd.DataFrame({
        "concepto": ["Ingreso mensual", "Gasto observado"],
        "valor":    [context["income_monthly"], context["total_amount"]],
    })
    spend_ratio = (
        context["total_amount"] / context["income_monthly"]
        if context["income_monthly"] else 0.0
    )

    charts = [
        _style_figure(
            px.bar(
                compare_frame,
                x="concepto", y="valor",
                title="Ingreso mensual vs. gasto observado",
                color="concepto",
                color_discrete_sequence=PLOTLY_SCALE,
                text_auto=".2s",
            )
        )
    ]
    if not top_cats.empty:
        charts.append(
            _style_figure(
                px.bar(
                    top_cats,
                    x="categoria", y="monto_total",
                    title="Top 5 categorías de gasto",
                    color="categoria",
                    color_discrete_sequence=PLOTLY_SCALE,
                    text_auto=".2s",
                )
            )
        )

    top_cat = top_cats.iloc[0]["categoria"] if not top_cats.empty else context["top_category"]

    message = (
        f"{context['name']}, revisé tus movimientos y veo una oportunidad para optimizar tu dinero.\n\n"
        f"Hoy concentras más gasto en **{top_cat}**. Tu flujo observado suma "
        f"{_format_currency(context['total_amount'])} frente a un ingreso mensual de "
        f"{_format_currency(context['income_monthly'])}, así que tu ritmo actual corre **{spend_ratio:.1f}x** "
        "sobre tu ingreso mensual. Si quieres, el siguiente paso es recortar esa categoría o mover ese "
        "excedente a una ruta de inversión."
    )

    return {
        "message": message,
        "options": ["📈 Empezar a Invertir", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts":  charts,
        "metrics": _kpi_metrics(context),
        "table":   top_cats,
        "intent":  "finanzas",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_rendimientos_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    """
    Payload de inversión: muestra capacidad de inversión mensual o balance neto
    dependiendo de si el usuario ya tiene un portafolio activo.

    La tabla adjunta permite al usuario ver los números exactos por mes
    sin depender solo de la gráfica.
    """
    monthly = _monthly_capacity_frame(user_transactions, context["income_monthly"])
    capacity_now = _safe_number(monthly["capacidad_inversion"].mean())

    if context["has_investment"]:
        message = (
            f"{context['name']}, tu perfil ya está listo para una conversación de crecimiento.\n\n"
            f"Tu saldo total es de {_format_currency(context['total_balance'])} y tu score actual es {context['score']}. "
            "La curva de balance neto muestra que puedes sostener una estrategia más constante y menos reactiva."
        )
        y_field     = "balance_neto"
        chart_title = "Tendencia de balance neto"
    else:
        message = (
            f"{context['name']}, todavía no veo un portafolio activo, pero sí una base útil para empezar.\n\n"
            f"Tu capacidad promedio de inversión ronda **{_format_currency(capacity_now)} al mes**. "
            "Con ese espacio podemos arrancar una rutina simple y después subir el nivel con objetivos más ambiciosos."
        )
        y_field     = "capacidad_inversion"
        chart_title = "Capacidad de inversión mensual"

    chart = _style_figure(
        px.line(
            monthly,
            x="month", y=y_field,
            markers=True,
            title=chart_title,
            color_discrete_sequence=PLOTLY_SCALE,
        )
    )

    return {
        "message": message,
        "options": ["📊 Analizar mis Gastos", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts":  [chart],
        "metrics": _kpi_metrics(context),
        "table":   monthly[["month", "gasto_observado", "capacidad_inversion"]].reset_index(drop=True),
        "intent":  "rendimientos",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_support_payload(context: dict, user_transactions: pd.DataFrame, user_input: str) -> dict:
    """
    Router interno de soporte: detecta el sub-tipo de problema y delega
    al builder especializado correspondiente.

    Sub-flujos disponibles:
        card_block  → pasos para bloquear tarjeta robada/perdida.
        charge      → guía para disputar un cargo no reconocido.
        security    → hardening de cuenta (NIP, contraseña, alertas).
        generic     → respuesta conversacional open-ended.
    """
    text = (user_input or "").strip().lower()
    if any(kw in text for kw in CARD_BLOCK_KEYWORDS):
        return _build_card_block_payload(context)
    if any(kw in text for kw in CHARGE_KEYWORDS):
        return _build_charge_payload(context, user_transactions)
    if any(kw in text for kw in SECURITY_KEYWORDS):
        return _build_security_payload(context)
    return _build_generic_help_payload(context)


def _build_card_block_payload(context: dict) -> dict:
    message = (
        f"{context['name']}, vamos a proteger tu cuenta de inmediato.\n\n"
        "1. Abre la tarjeta afectada y selecciona la opción para bloquearla temporalmente.\n"
        "2. Revisa tus movimientos más recientes para identificar cualquier cargo no reconocido.\n"
        "3. Si la tarjeta está extraviada o comprometida, solicita reposición y cambia tu NIP desde seguridad.\n"
        "4. Si quieres, te conecto con un asesor para cerrar el caso contigo en tiempo real."
    )
    return {
        "message": message,
        "options": ["🔒 Bloquear Tarjeta", "🔍 Ver movimientos recientes", "🆘 Contactar Asesor"],
        "charts":  [],
        "metrics": _support_metrics(context, "Protección activa"),
        "table":   None,
        "intent":  "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_charge_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    pending_cases = int((user_transactions["estatus"].astype(str) != "completada").sum())
    intl          = int(user_transactions["es_internacional"].sum())
    message = (
        f"{context['name']}, te ayudo a revisar ese cargo paso a paso.\n\n"
        "1. Confirma el comercio, monto y fecha para descartar una preautorización o un cargo recurrente.\n"
        "2. Si no lo reconoces, bloquea tu tarjeta temporalmente para evitar nuevos intentos.\n"
        "3. Levanta la aclaración desde ayuda o con un asesor para dejar trazabilidad del caso.\n"
        f"4. Detecté **{pending_cases}** transacciones no completadas y **{intl}** movimientos internacionales recientes; "
        "eso hace razonable priorizar la revisión hoy."
    )
    return {
        "message": message,
        "options": ["🔒 Bloquear Tarjeta", "📋 Levantar Aclaración", "🆘 Contactar Asesor"],
        "charts":  [],
        "metrics": _support_metrics(context, "Aclaración sugerida"),
        "table":   None,
        "intent":  "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_security_payload(context: dict) -> dict:
    message = (
        f"{context['name']}, puedo ayudarte a reforzar tu seguridad en minutos.\n\n"
        "1. Actualiza tu contraseña y confirma que tu correo y celular de recuperación estén vigentes.\n"
        "2. Cambia tu NIP si compartiste o expusiste la tarjeta.\n"
        "3. Activa alertas de movimiento para compras, retiros y accesos.\n"
        "4. Si viste algo sospechoso en la app, te conviene hablar con un asesor para revisar sesiones activas."
    )
    return {
        "message": message,
        "options": ["🔑 Cambiar NIP", "🔔 Activar Alertas", "🆘 Contactar Asesor"],
        "charts":  [],
        "metrics": _support_metrics(context, "Seguridad recomendada"),
        "table":   None,
        "intent":  "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_generic_help_payload(context: dict) -> dict:
    message = (
        f"{context['name']}, estoy aquí para resolverlo contigo.\n\n"
        "Cuéntame qué necesitas y te daré pasos concretos, ya sea para revisar un cargo, bloquear una tarjeta, "
        "entender tus finanzas o encontrar la mejor siguiente acción dentro de Hey Banco."
    )
    return {
        "message": message,
        "options": ["📊 Analizar mis Gastos", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts":  [],
        "metrics": _support_metrics(context, "Acompañamiento activo"),
        "table":   None,
        "intent":  "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _maintenance_payload(user_id: str, failed_source: str) -> dict:
    """
    Payload de emergencia: garantiza que el UI siempre reciba el dict de 7 llaves
    incluso cuando todos los datos fallan. Sin esto, un error en carga de CSV
    rompe la app con un KeyError en app_mobile.py.
    """
    context = _empty_context(user_id)
    context["status"] = "Mantenimiento"
    return {
        "message": (
            "HAVI está en mantenimiento del sistema.\n\n"
            f"La fuente afectada es **{failed_source}**. Intenta de nuevo en unos minutos y retomamos desde aquí."
        ),
        "options": DEFAULT_OPTIONS,
        "charts":  [],
        "metrics": _kpi_metrics(context),
        "table":   None,
        "intent":  "soporte",
        "context": context,
    }


# ===========================================================================
# HELPERS DE ANÁLISIS (Pandas)
# ===========================================================================

def _top_categories_frame(user_transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Top 5 categorías de gasto por monto total.

    Pipeline Pandas:
        1. Filtra solo operaciones de salida (OUTGOING_OPERATIONS).
        2. Descarta NaN y la categoría "transferencia" (no es gasto real).
        3. Agrupa por categoria_mcc y suma montos.
        4. Ordena descendente y toma las 5 primeras.
    """
    cats = (
        user_transactions
        .loc[user_transactions["tipo_operacion"].isin(OUTGOING_OPERATIONS)]
        .loc[lambda df: df["categoria_mcc"].notna()]
        .loc[lambda df: df["categoria_mcc"] != "transferencia"]
        .groupby("categoria_mcc", as_index=False)["monto"]
        .sum()
        .sort_values("monto", ascending=False)
        .head(5)
        .rename(columns={"categoria_mcc": "categoria", "monto": "monto_total"})
    )
    return cats.reset_index(drop=True)


def _top_spending_category(user_transactions: pd.DataFrame) -> str:
    """Devuelve el nombre de la categoría con mayor gasto acumulado."""
    cats = _top_categories_frame(user_transactions)
    if cats.empty:
        return "Sin datos"
    return str(cats.iloc[0]["categoria"])


def _monthly_capacity_frame(user_transactions: pd.DataFrame, income_monthly: float) -> pd.DataFrame:
    """
    Calcula capacidad de inversión mes a mes.

    Columnas resultantes:
        month              → YYYY-MM
        gasto_observado    → suma de salidas ese mes
        ingreso_mensual    → constante = income_monthly (del perfil del usuario)
        capacidad_inversion→ ingreso - gasto
        balance_neto       → cumsum de capacidad (ahorro acumulado teórico)
    """
    outgoing = (
        user_transactions
        .loc[user_transactions["tipo_operacion"].isin(OUTGOING_OPERATIONS)]
        .groupby("month", as_index=False)["monto"]
        .sum()
        .rename(columns={"monto": "gasto_observado"})
        .sort_values("month")
    )
    if outgoing.empty:
        outgoing = pd.DataFrame({"month": ["Sin datos"], "gasto_observado": [0.0]})

    outgoing["ingreso_mensual"]    = income_monthly
    outgoing["capacidad_inversion"]= outgoing["ingreso_mensual"] - outgoing["gasto_observado"]
    outgoing["balance_neto"]       = outgoing["capacidad_inversion"].cumsum()
    return outgoing.reset_index(drop=True)


# ===========================================================================
# HELPERS DE MÉTRICAS Y FORMATO
# ===========================================================================

def _kpi_metrics(context: dict) -> list[dict]:
    """
    Métricas principales para la banda superior (saldo, score, utilización).
    La utilización se normaliza: si está en [0,1] se multiplica por 100 para mostrar %.
    """
    util = context["utilization_average"]
    util_pct = util * 100 if util <= 1 else util
    return [
        _metric("Saldo Total",   _format_currency(context["total_balance"]), context["status"],  "positive"),
        _metric("Score Buró",    str(int(_safe_number(context["score"]))),    context["tier"],    "info"),
        _metric("Utilización",   f"{util_pct:.1f}%",                         "Nivel actual",
                "negative" if util_pct >= 60 else "positive"),
    ]


def _support_metrics(context: dict, delta: str) -> list[dict]:
    """Métricas de soporte: identificación del cliente + cashback disponible."""
    return [
        _metric("Cliente",    context["name"],                       delta,                    "info"),
        _metric("Score Buró", str(context["score"]),                 context["tier"],           "info"),
        _metric("Cashback",   _format_currency(context["cashback_total"]), "Beneficio disponible", "positive"),
    ]


def _estimate_score_drop(context: dict) -> int:
    """
    Estimación heurística del impacto en score buró al cancelar cuenta.
    Factores: utilización de crédito, antigüedad de cuenta y tier del usuario.
    Rango acotado entre 8 y 28 puntos para mantener la estimación creíble.
    """
    util_factor  = context["utilization_average"] * 10 if context["utilization_average"] <= 1 else context["utilization_average"] / 10
    age_factor   = 4 if context["account_age_days"] > 365 else 2
    tier_factor  = 4 if "pro" in context["tier"].lower() else 2
    return max(8, min(28, int(round(6 + util_factor + age_factor + tier_factor))))


def _status_tone(status: str) -> str:
    """Mapea el string de satisfacción del CSV a una clase de color ('positive'|'negative'|'info')."""
    low = status.lower()
    if "alta" in low:
        return "positive"
    if "baja" in low:
        return "negative"
    return "info"


def _empty_context(user_id: str) -> dict:
    """Contexto vacío/seguro para cuando el usuario no existe en el CSV."""
    return {
        "user_id":            user_id,
        "name":               "Alex" if user_id == DEFAULT_USER_ID else user_id,
        "tier":               "Hey Banco",
        "status":             "Sin datos",
        "status_tone":        "info",
        "age":                0,
        "city":               "Sin datos",
        "score":              0,
        "income_monthly":     0.0,
        "total_balance":      0.0,
        "cashback_total":     0.0,
        "total_amount":       0.0,
        "top_category":       "Sin datos",
        "has_investment":     False,
        "credit_limit_total": 0.0,
        "utilization_average":0.0,
        "account_age_days":   0,
        "preferred_rate":     0.0,
        "new_user":           False,
        "ui_tone":            "neutral",
    }


def _metric(label: str, value: str, delta: str | None, tone: str) -> dict:
    """Constructor de un dict de métrica — mantiene el contrato con el renderer de app_mobile.py."""
    return {"label": label, "value": value, "delta": delta, "tone": tone}


def _format_currency(value: float | int, decimals: int = 2) -> str:
    return f"${_safe_number(value):,.{decimals}f} MXN"


def _safe_number(value: object) -> float:
    """Convierte cualquier valor a float; devuelve 0.0 para None o NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _style_figure(figure):
    """
    Aplica el tema visual Hey Banco a todas las figuras Plotly.
    Fondo transparente para que encaje en dark mode y light mode sin cambios.
    """
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "#fbf8f2"},   # texto claro para dark mode
        margin={"l": 16, "r": 16, "t": 56, "b": 16},
        title={"font": {"size": 18}},
        legend_title_text="",
    )
    figure.update_xaxes(showgrid=False, color="#fbf8f2")
    figure.update_yaxes(gridcolor="#49494e", color="#fbf8f2")
    return figure