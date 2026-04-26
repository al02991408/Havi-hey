"""
Segmentación de Clientes mediante Manifold Learning (UMAP)

DESCRIPCIÓN: Pipeline de Machine Learning para identificar arquetipos conductuales
             y optimizar estrategias de conversión para Chatbots bancarios.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import umap
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# =================================================================
# CONFIGURACIÓN DE RUTAS (Cambiar por el nombre de tu archivo local)
# =================================================================
INPUT_FILE = "base_maestra_clientes.csv" 
OUTPUT_FILE = "segmentos_potencial_pro.csv"

# =================================================================
# FASE 1: INGENIERÍA DE DATOS Y PREPROCESAMIENTO
# =================================================================
print("Cargando y procesando datos...")
df_base = pd.read_csv(INPUT_FILE)

# Imputación de valores nulos: Asumimos 0 para variables transaccionales vacías
cols_financieras = [
    'saldo_total', 'limite_credito_total', 'utilizacion_promedio', 'n_productos_activos_calc', 
    'n_productos_cancelados', 'n_transacciones', 'monto_total', 'ticket_promedio', 
    'monto_maximo', 'cashback_total', 'n_transacciones_no_procesadas', 
    'pct_transacciones_internacionales', 'pct_patron_atipico_tx', 'pct_transacciones_no_procesadas'
]
df_base[cols_financieras] = df_base.reindex(columns=cols_financieras).fillna(0)

# Ingeniería de variables (Feature Engineering)
# Transformación logarítmica para reducir el sesgo de la inactividad
df_base['log_dias_login'] = np.log1p(df_base['dias_desde_ultimo_login'])
df_base['es_canal_app'] = np.where(df_base['preferencia_canal'].str.lower() == 'app', 1, 0)
df_base['indice_digital'] = df_base['usa_hey_shop'] + df_base['es_hey_pro'] + df_base['es_canal_app']
df_base['densidad_productos'] = df_base['num_productos_activos'] / 5.0

# Codificación Ordinal (Nivel Educativo)
mapa_educacion = {
    'Ninguno': 0, 'Primaria': 1, 'Secundaria': 2, 'Preparatoria': 3,
    'Licenciatura': 4, 'Maestria': 5, 'Doctorado': 6
}
df_base['nivel_educativo_num'] = df_base['nivel_educativo'].map(mapa_educacion).fillna(0)

# Estandarización de tipos booleanos
cols_bool = ['es_hey_pro', 'nomina_domiciliada', 'recibe_remesas', 'usa_hey_shop', 'tiene_seguro', 'patron_uso_atipico']
for col in cols_bool:
    if col in df_base.columns: 
        df_base[col] = df_base[col].astype(int)

# One-Hot Encoding para variables categóricas nominales
df_encoded = pd.get_dummies(df_base, columns=['canal_apertura', 'sexo'], drop_first=True)

# Selección de características (Filtro de Target Leakage y variables no numéricas)
cols_excluir = [
    'user_id', 'ciudad', 'estado', 'ocupacion', 'idioma_preferido', 'nivel_educativo', 
    'preferencia_canal', 'dias_desde_ultimo_login', 'satisfaccion_1_10', 'n_conversaciones', 
    'total_mensajes', 'total_negativos', 'total_positivos', 'total_neutrales', 
    'score_sentimiento_promedio', 'pct_mensajes_negativos', 'pct_mensajes_positivos', 'satisfaccion_cliente'
]
X_features = df_encoded.drop(columns=[c for c in cols_excluir if c in df_encoded.columns])

# =================================================================
# FASE 2: MACHINE LEARNING (DIMENSIONALITY REDUCTION & CLUSTERING)
# =================================================================
print("Ejecutando Pipeline: Escalado -> UMAP -> K-Means...")

# 1. Escalado robusto para algoritmos basados en distancia
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_features)

# 2. Reducción de dimensionalidad no lineal (Manifold Learning)
reductor_umap = umap.UMAP(n_neighbors=20, min_dist=0.0, n_components=3, random_state=42)
X_umap = reductor_umap.fit_transform(X_scaled)

# 3. Agrupamiento K-Means (Optimizado en 7 arquetipos)
n_clusters = 7
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
df_base['arquetipo_id'] = kmeans.fit_predict(X_umap)

# =================================================================
# FASE 3: PERFILAMIENTO Y ANÁLISIS ESTADÍSTICO
# =================================================================
perfil_arquetipos = df_base.groupby('arquetipo_id').agg(
    volumen=('user_id', 'count'),
    edad_promedio=('edad', 'mean'),
    ingreso_mediano=('ingreso_mensual_mxn', 'median'),
    pct_hey_pro=('es_hey_pro', 'mean'),
    ticket_promedio=('ticket_promedio', 'median'),
    dias_inactivo=('dias_desde_ultimo_login', 'median')
).round(2)

print("\n--- PERFIL DE LOS ARQUETIPOS ENCONTRADOS ---")
print(perfil_arquetipos)

# =================================================================
# FASE 4: VISUALIZACIÓN INTERACTIVA (PLOTLY)
# =================================================================
df_visual = pd.DataFrame(X_umap, columns=['UMAP_1', 'UMAP_2', 'UMAP_3'])
df_visual['ingreso_real'] = df_base['ingreso_mensual_mxn'].values
df_visual['es_hey_pro_str'] = df_base['es_hey_pro'].astype(str).values
df_visual['arquetipo'] = df_base['arquetipo_id'].astype(str).values

# Gráfica 3D con menús de actualización
fig = px.scatter_3d(
    df_visual, x='UMAP_1', y='UMAP_2', z='UMAP_3',
    color='es_hey_pro_str',
    title="Análisis Topológico: Segmentación de Clientes",
    opacity=0.7
)

# Añadir Centroides
centroides = kmeans.cluster_centers_
fig.add_trace(go.Scatter3d(
    x=centroides[:, 0], y=centroides[:, 1], z=centroides[:, 2],
    mode='markers', marker=dict(size=8, color='black', symbol='cross'),
    name='Centroides de Arquetipos'
))

fig.show()

# =================================================================
# FASE 5: ESTRATEGIA DE NEGOCIO (IDENTIFICACIÓN DE LEADS)
# =================================================================
# Objetivo: Clientes de alto valor (Arquetipo 3) que aún no son PRO
print("\nGenerando lista de leads para conversión...")

df_objetivo = df_base[(df_base['arquetipo_id'] == 3) & (df_base['es_hey_pro'] == 0)].copy()

columnas_lead = ['user_id', 'ingreso_mensual_mxn', 'ticket_promedio', 'num_productos_activos']
lista_leads = df_objetivo[columnas_lead]

# Exportación final
lista_leads.to_csv(OUTPUT_FILE, index=False)
print(f"Éxito: Se identificaron {len(lista_leads)} prospectos de alto valor.")
print(f"Archivo exportado: {OUTPUT_FILE}")