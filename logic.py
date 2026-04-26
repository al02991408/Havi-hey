from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_DIR = Path(__file__).resolve().parent / "data"
MASTER_CLIENTS_PATH = DATA_DIR / "base_maestra_clientes.csv"
PRODUCTS_PATH = DATA_DIR / "hey_productos.csv"
TRANSACTIONS_PATH = DATA_DIR / "hey_transacciones.csv"
USER_TRANSACTIONS_PATH = DATA_DIR / "hey_transacciones_usr_00001.csv"

DEFAULT_USER_ID = "USR-00001"
DEFAULT_OPTIONS = ["📊 Analizar mis Gastos", "📈 Empezar a Invertir", "🛡️ Configurar Seguridad"]
PLOTLY_SCALE = ["#8b6f43", "#964831", "#2b497d", "#546436"]

OUTGOING_OPERATIONS = {
    "compra",
    "transf_salida",
    "retiro_cajero",
    "pago_servicio",
    "pago_credito",
    "cargo_recurrente",
    "abono_inversion",
}

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
SECURITY_KEYWORDS = ("seguridad", "nip", "contraseña", "contrasena", "app", "acceso", "login")
SUPPORT_KEYWORDS = CARD_BLOCK_KEYWORDS + CHARGE_KEYWORDS + SECURITY_KEYWORDS + (
    "soporte",
    "ayuda",
    "problema",
    "error",
    "asesor",
    "humano",
)


@st.cache_data(show_spinner=False)
def load_master_clients() -> tuple[pd.DataFrame | None, str | None]:
    try:
        dataframe = pd.read_csv(MASTER_CLIENTS_PATH, encoding="utf-8")
        numeric_columns = [
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
        for column in numeric_columns:
            if column in dataframe.columns:
                dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)
        return dataframe, None
    except Exception:
        return None, "base maestra"


@st.cache_data(show_spinner=False)
def load_products() -> tuple[pd.DataFrame | None, str | None]:
    try:
        dataframe = pd.read_csv(
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
        for column in ("saldo_actual", "limite_credito", "utilizacion_pct", "tasa_interes_anual"):
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)
        return dataframe, None
    except Exception:
        return None, "productos"


@st.cache_data(show_spinner=False)
def load_user_transactions(user_id: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        preferred_path = USER_TRANSACTIONS_PATH if user_id == DEFAULT_USER_ID and USER_TRANSACTIONS_PATH.exists() else TRANSACTIONS_PATH
        chunks: list[pd.DataFrame] = []
        for chunk in pd.read_csv(
            preferred_path,
            encoding="utf-8",
            usecols=[
                "user_id",
                "fecha_hora",
                "tipo_operacion",
                "monto",
                "categoria_mcc",
                "estatus",
                "es_internacional",
            ],
            chunksize=100_000,
        ):
            filtered = chunk if preferred_path == USER_TRANSACTIONS_PATH else chunk.loc[chunk["user_id"] == user_id].copy()
            if not filtered.empty:
                chunks.append(filtered)

        dataframe = (
            pd.concat(chunks, ignore_index=True)
            if chunks
            else pd.DataFrame(
                columns=[
                    "user_id",
                    "fecha_hora",
                    "tipo_operacion",
                    "monto",
                    "categoria_mcc",
                    "estatus",
                    "es_internacional",
                ]
            )
        )
        dataframe["monto"] = pd.to_numeric(dataframe["monto"], errors="coerce").fillna(0.0)
        dataframe["es_internacional"] = dataframe["es_internacional"].fillna(False).astype(bool)
        if not dataframe.empty:
            dataframe["month"] = dataframe["fecha_hora"].astype(str).str.slice(0, 7)
        else:
            dataframe["month"] = pd.Series(dtype="object")
        return dataframe, None
    except Exception:
        return None, "transacciones"


def analyze_interaction(user_input: str, user_id: str = DEFAULT_USER_ID) -> dict:
    try:
        master_clients, master_error = load_master_clients()
        products, products_error = load_products()
        user_transactions, tx_error = load_user_transactions(user_id)
        failed_source = master_error or products_error or tx_error

        if failed_source or master_clients is None or products is None or user_transactions is None:
            return _maintenance_payload(user_id, failed_source or "datos")

        context = get_user_context(user_id, master_clients, products, user_transactions)
        intent = _detect_intent(user_input, context)

        if intent == "onboarding":
            return _build_onboarding_payload(context)
        if intent == "retention":
            return _build_retention_payload(context, products)
        if intent == "rendimientos":
            return _build_rendimientos_payload(context, user_transactions)
        if intent == "finanzas":
            return _build_finanzas_payload(context, user_transactions)
        return _build_support_payload(context, user_transactions, user_input)
    except Exception:
        return _maintenance_payload(user_id, "sistema")


def get_user_context(
    user_id: str,
    master_clients: pd.DataFrame,
    products: pd.DataFrame,
    user_transactions: pd.DataFrame,
) -> dict:
    row = master_clients.loc[master_clients["user_id"] == user_id]
    if row.empty:
        return _empty_context(user_id)

    client = row.iloc[0]
    user_products = products.loc[products["user_id"] == user_id].copy()
    top_category = _top_spending_category(user_transactions)
    has_investment = bool(
        user_products["tipo_producto"].astype(str).str.contains("inversion", case=False, na=False).any()
    )
    preferred_rate = _safe_number(user_products["tasa_interes_anual"].replace(0, pd.NA).dropna().min())

    return {
        "user_id": user_id,
        "name": "Alex" if user_id == DEFAULT_USER_ID else user_id,
        "tier": "Hey Pro" if bool(client.get("es_hey_pro")) else "Hey Banco",
        "status": str(client.get("satisfaccion_cliente", "Neutral")),
        "status_tone": _status_tone(str(client.get("satisfaccion_cliente", "Neutral"))),
        "age": int(_safe_number(client.get("edad"))),
        "city": str(client.get("ciudad", "Sin datos")),
        "score": int(_safe_number(client.get("score_buro"))),
        "income_monthly": _safe_number(client.get("ingreso_mensual_mxn")),
        "total_balance": _safe_number(client.get("saldo_total")),
        "cashback_total": _safe_number(client.get("cashback_total")),
        "total_amount": _safe_number(client.get("monto_total")),
        "top_category": top_category,
        "has_investment": has_investment,
        "credit_limit_total": _safe_number(client.get("limite_credito_total")),
        "utilization_average": _safe_number(client.get("utilizacion_promedio")),
        "account_age_days": int(_safe_number(client.get("antiguedad_dias"))),
        "preferred_rate": preferred_rate,
        "new_user": bool(_safe_number(client.get("antiguedad_dias")) <= 45),
        "ui_tone": "neutral",
    }


def _build_onboarding_payload(context: dict) -> dict:
    context = {**context, "ui_tone": "positive"}
    table = pd.DataFrame(
        [
            {"herramienta": "Analizar mis Gastos", "qué verás": "Patrones, alertas y oportunidades", "estado": "Listo"},
            {"herramienta": "Empezar a Invertir", "qué verás": "Capacidad mensual y ruta sugerida", "estado": "Disponible"},
            {"herramienta": "Configurar Seguridad", "qué verás": "Bloqueos, alertas y control de accesos", "estado": "Recomendado"},
            {"herramienta": "Centro de Ayuda", "qué verás": "Soporte guiado y escalamiento humano", "estado": "Activo"},
        ]
    )

    return {
        "message": (
            "¡Bienvenido al Universo Hey! Soy HAVI, tu asistente de inteligencia financiera. "
            "He preparado un tour por tus nuevas herramientas para que tomes el control de tu dinero hoy mismo.\n\n"
            "Puedo ayudarte a entender tus gastos, activar tu ruta de inversión, configurar seguridad "
            "y resolver dudas con respuestas accionables en lenguaje natural."
        ),
        "options": ["📊 Analizar mis Gastos", "📈 Empezar a Invertir", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts": [],
        "metrics": [
            _metric("Saldo disponible", _format_currency(0), "Listo para empezar", "positive"),
            _metric("Meta sugerida", _format_currency(0), "Define tu primer objetivo", "info"),
            _metric("Alertas activas", "0", "Cobertura inicial", "positive"),
        ],
        "table": table,
        "intent": "onboarding",
        "context": context,
    }


def _build_retention_payload(context: dict, products: pd.DataFrame) -> dict:
    user_products = products.loc[products["user_id"] == context["user_id"]].copy()
    preferred_rate = context["preferred_rate"] or _safe_number(user_products["tasa_interes_anual"].replace(0, pd.NA).dropna().min())
    estimated_score_drop = _estimate_score_drop(context)
    comparison = pd.DataFrame(
        {
            "escenario": ["Cancelar hoy", "Conservar beneficios"],
            "impacto": [
                context["cashback_total"] + estimated_score_drop,
                max(context["cashback_total"] * 1.2, 150.0),
            ],
            "lectura": ["Pérdidas", "Valor retenido"],
        }
    )

    chart = _style_figure(
        px.bar(
            comparison,
            x="escenario",
            y="impacto",
            color="escenario",
            title="Loss Comparison",
            color_discrete_sequence=["#fa94ae", "#00b478"],
            text_auto=".2f",
        )
    )

    context = {**context, "ui_tone": "negative"}
    rate_detail = f" La tasa preferencial actual que estás aprovechando ronda {preferred_rate:.2f}%." if preferred_rate else ""

    message = (
        f"{context['name']}, lamento que consideres dejarnos. Antes de proceder, detecté que tienes "
        f"${context['cashback_total']:.2f} de cashback sin utilizar y tu estatus Hey Pro te otorga una tasa "
        f"preferencial que perderías hoy.{rate_detail}\n\n"
        f"Si cierras tu cuenta hoy, también podrías ver una presión estimada de {estimated_score_drop} puntos "
        "en tu historial por reducir antigüedad y modificar tu utilización reportada. Puedo ayudarte a revisar "
        "alternativas antes de que tomes la decisión final."
    )

    return {
        "message": message,
        "options": ["💬 Hablar con un Humano", "🎁 Ver Beneficios Pro", "⚙️ Continuar Proceso"],
        "charts": [chart],
        "metrics": [
            _metric("Cashback en riesgo", _format_currency(context["cashback_total"]), "Se pierde al cerrar", "negative"),
            _metric("Impacto estimado", f"-{estimated_score_drop} pts", "Score Buró potencial", "negative"),
            _metric("Score actual", str(context["score"]), "Mantener cuenta ayuda a estabilidad", "positive"),
        ],
        "table": None,
        "intent": "retention",
        "context": context,
    }


def _build_finanzas_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    top_categories = _top_categories_frame(user_transactions)
    compare_frame = pd.DataFrame(
        {
            "concepto": ["Ingreso mensual", "Gasto observado"],
            "valor": [context["income_monthly"], context["total_amount"]],
        }
    )
    spend_ratio = context["total_amount"] / context["income_monthly"] if context["income_monthly"] else 0.0

    charts = [
        _style_figure(
            px.bar(
                compare_frame,
                x="concepto",
                y="valor",
                title="Ingreso mensual vs gasto observado",
                color="concepto",
                color_discrete_sequence=PLOTLY_SCALE,
                text_auto=".2s",
            )
        )
    ]
    if not top_categories.empty:
        charts.append(
            _style_figure(
                px.bar(
                    top_categories,
                    x="categoria",
                    y="monto_total",
                    title="Top 5 categorías de gasto",
                    color="categoria",
                    color_discrete_sequence=PLOTLY_SCALE,
                    text_auto=".2s",
                )
            )
        )

    opportunity_category = top_categories.iloc[0]["categoria"] if not top_categories.empty else context["top_category"]
    message = (
        f"{context['name']}, revisé tus movimientos y veo una oportunidad clara para optimizar tu dinero.\n\n"
        f"Hoy estás concentrando más gasto en **{opportunity_category}**. Tu flujo observado suma "
        f"{_format_currency(context['total_amount'])} frente a un ingreso mensual de "
        f"{_format_currency(context['income_monthly'])}, así que tu ritmo actual ya corre {spend_ratio:.1f}x "
        "sobre tu ingreso mensual. Si quieres, el siguiente paso natural es recortar esa categoría o mover ese "
        "excedente a una ruta de inversión."
    )

    return {
        "message": message,
        "options": ["📈 Empezar a Invertir", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts": charts,
        "metrics": _kpi_metrics(context),
        "table": top_categories,
        "intent": "finanzas",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_rendimientos_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    monthly_capacity = _monthly_capacity_frame(user_transactions, context["income_monthly"])
    capacity_now = _safe_number(monthly_capacity["capacidad_inversion"].mean())

    if context["has_investment"]:
        message = (
            f"{context['name']}, tu perfil ya está listo para una conversación de crecimiento.\n\n"
            f"Tu saldo total es de {_format_currency(context['total_balance'])} y tu score actual es {context['score']}. "
            "La curva de balance neto muestra que puedes sostener una estrategia más constante y menos reactiva."
        )
        y_field = "balance_neto"
        chart_title = "Tendencia de balance neto"
    else:
        message = (
            f"{context['name']}, todavía no veo un portafolio activo, pero sí una base útil para empezar.\n\n"
            f"Tu capacidad promedio de inversión ronda {_format_currency(capacity_now)} al mes. Con ese espacio, "
            "podemos arrancar una rutina simple y después subir el nivel con objetivos más ambiciosos."
        )
        y_field = "capacidad_inversion"
        chart_title = "Capacidad de inversión"

    chart = _style_figure(
        px.line(
            monthly_capacity,
            x="month",
            y=y_field,
            markers=True,
            title=chart_title,
            color_discrete_sequence=PLOTLY_SCALE,
        )
    )

    return {
        "message": message,
        "options": ["📊 Analizar mis Gastos", "🛡️ Configurar Seguridad", "🆘 Centro de Ayuda"],
        "charts": [chart],
        "metrics": _kpi_metrics(context),
        "table": monthly_capacity[["month", "gasto_observado", "capacidad_inversion"]].reset_index(drop=True),
        "intent": "rendimientos",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_support_payload(
    context: dict,
    user_transactions: pd.DataFrame,
    user_input: str,
) -> dict:
    text = (user_input or "").strip().lower()
    if any(keyword in text for keyword in CARD_BLOCK_KEYWORDS):
        return _build_card_block_payload(context)
    if any(keyword in text for keyword in CHARGE_KEYWORDS):
        return _build_charge_payload(context, user_transactions)
    if any(keyword in text for keyword in SECURITY_KEYWORDS):
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
        "options": ["Bloquear Tarjeta", "Ver movimientos recientes", "Contactar Asesor"],
        "charts": [],
        "metrics": _support_metrics(context, "Protección activa"),
        "table": None,
        "intent": "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _build_charge_payload(context: dict, user_transactions: pd.DataFrame) -> dict:
    pending_cases = int((user_transactions["estatus"].astype(str) != "completada").sum())
    intl = int(user_transactions["es_internacional"].sum())
    message = (
        f"{context['name']}, te ayudo a revisar ese cargo paso a paso.\n\n"
        "1. Confirma el comercio, monto y fecha para descartar una preautorización o un cargo recurrente.\n"
        "2. Si no lo reconoces, bloquea tu tarjeta temporalmente para evitar nuevos intentos.\n"
        "3. Levanta la aclaración desde ayuda o con un asesor para dejar trazabilidad del caso.\n"
        f"4. Detecté {pending_cases} transacciones no completadas y {intl} movimientos internacionales recientes; "
        "eso hace razonable priorizar la revisión hoy."
    )
    return {
        "message": message,
        "options": ["Bloquear Tarjeta", "Levantar Aclaración", "Contactar Asesor"],
        "charts": [],
        "metrics": _support_metrics(context, "Aclaración sugerida"),
        "table": None,
        "intent": "soporte",
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
        "options": ["Cambiar NIP", "Activar Alertas", "Contactar Asesor"],
        "charts": [],
        "metrics": _support_metrics(context, "Seguridad recomendada"),
        "table": None,
        "intent": "soporte",
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
        "charts": [],
        "metrics": _support_metrics(context, "Acompañamiento activo"),
        "table": None,
        "intent": "soporte",
        "context": {**context, "ui_tone": "neutral"},
    }


def _maintenance_payload(user_id: str, failed_source: str) -> dict:
    context = _empty_context(user_id)
    context["status"] = "Mantenimiento"
    return {
        "message": (
            "HAVI está en mantenimiento del sistema.\n\n"
            f"La fuente afectada es {failed_source}. Intenta de nuevo en unos minutos y retomamos desde aquí."
        ),
        "options": DEFAULT_OPTIONS,
        "charts": [],
        "metrics": _kpi_metrics(context),
        "table": None,
        "intent": "soporte",
        "context": context,
    }


def _top_categories_frame(user_transactions: pd.DataFrame) -> pd.DataFrame:
    categories = (
        user_transactions.loc[user_transactions["tipo_operacion"].isin(OUTGOING_OPERATIONS)]
        .loc[lambda frame: frame["categoria_mcc"].notna()]
        .loc[lambda frame: frame["categoria_mcc"] != "transferencia"]
        .groupby("categoria_mcc", as_index=False)["monto"]
        .sum()
        .sort_values("monto", ascending=False)
        .head(5)
        .rename(columns={"categoria_mcc": "categoria", "monto": "monto_total"})
    )
    return categories.reset_index(drop=True)


def _top_spending_category(user_transactions: pd.DataFrame) -> str:
    categories = _top_categories_frame(user_transactions)
    if categories.empty:
        return "Sin datos"
    return str(categories.iloc[0]["categoria"])


def _monthly_capacity_frame(user_transactions: pd.DataFrame, income_monthly: float) -> pd.DataFrame:
    outgoing = (
        user_transactions.loc[user_transactions["tipo_operacion"].isin(OUTGOING_OPERATIONS)]
        .groupby("month", as_index=False)["monto"]
        .sum()
        .rename(columns={"monto": "gasto_observado"})
        .sort_values("month")
    )
    if outgoing.empty:
        outgoing = pd.DataFrame({"month": ["Sin datos"], "gasto_observado": [0.0]})
    outgoing["ingreso_mensual"] = income_monthly
    outgoing["capacidad_inversion"] = outgoing["ingreso_mensual"] - outgoing["gasto_observado"]
    outgoing["balance_neto"] = outgoing["capacidad_inversion"].cumsum()
    return outgoing.reset_index(drop=True)


def _detect_intent(user_input: str, context: dict) -> str:
    text = (user_input or "").strip().lower()
    if not text or text == "inicio" or context.get("new_user") or any(keyword in text for keyword in ONBOARDING_KEYWORDS):
        return "onboarding"
    if any(keyword in text for keyword in RETENTION_KEYWORDS):
        return "retention"
    if any(keyword in text for keyword in INVESTMENT_KEYWORDS):
        return "rendimientos"
    if any(keyword in text for keyword in FINANCE_KEYWORDS):
        return "finanzas"
    if any(keyword in text for keyword in SUPPORT_KEYWORDS):
        return "soporte"
    return "soporte"


def _kpi_metrics(context: dict) -> list[dict]:
    utilization = context["utilization_average"] * 100 if context["utilization_average"] <= 1 else context["utilization_average"]
    return [
        _metric("Saldo Total", _format_currency(context["total_balance"]), context["status"], "positive"),
        _metric("Score Buró", str(int(_safe_number(context["score"]))), context["tier"], "info"),
        _metric("Utilización", f"{utilization:.1f}%", "Nivel actual", "negative" if utilization >= 60 else "positive"),
    ]


def _support_metrics(context: dict, delta: str) -> list[dict]:
    return [
        _metric("Cliente", context["name"], delta, "info"),
        _metric("Score Buró", str(context["score"]), context["tier"], "info"),
        _metric("Cashback", _format_currency(context["cashback_total"]), "Beneficio disponible", "positive"),
    ]


def _estimate_score_drop(context: dict) -> int:
    utilization_factor = context["utilization_average"] * 10 if context["utilization_average"] <= 1 else context["utilization_average"] / 10
    age_factor = 4 if context["account_age_days"] > 365 else 2
    tier_factor = 4 if "pro" in context["tier"].lower() else 2
    return max(8, min(28, int(round(6 + utilization_factor + age_factor + tier_factor))))


def _status_tone(status: str) -> str:
    lowered = status.lower()
    if "alta" in lowered:
        return "positive"
    if "baja" in lowered:
        return "negative"
    return "info"


def _empty_context(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "name": "Alex" if user_id == DEFAULT_USER_ID else user_id,
        "tier": "Hey Banco",
        "status": "Sin datos",
        "status_tone": "info",
        "age": 0,
        "city": "Sin datos",
        "score": 0,
        "income_monthly": 0.0,
        "total_balance": 0.0,
        "cashback_total": 0.0,
        "total_amount": 0.0,
        "top_category": "Sin datos",
        "has_investment": False,
        "credit_limit_total": 0.0,
        "utilization_average": 0.0,
        "account_age_days": 0,
        "preferred_rate": 0.0,
        "new_user": False,
        "ui_tone": "neutral",
    }


def _metric(label: str, value: str, delta: str | None, tone: str) -> dict:
    return {"label": label, "value": value, "delta": delta, "tone": tone}


def _format_currency(value: float | int, decimals: int = 2) -> str:
    return f"${_safe_number(value):,.{decimals}f} MXN"


def _safe_number(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _style_figure(figure):
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "#212023"},
        margin={"l": 16, "r": 16, "t": 56, "b": 16},
        title={"font": {"size": 18}},
        legend_title_text="",
    )
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="#eeeef0")
    return figure
