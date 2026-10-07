"""Modelo de segmentación de clientes para LavaSmart.

Calcula variables RFM (Recencia, Frecuencia, Monto) por placa y agrupa con K-Means.
La placa es seudonimización, NO anonimización: sigue siendo dato personal (Ley N.° 29733).
Recibe solo lavados ENTREGADOS; el monto es lo realmente cobrado.
"""
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def calcular_rfm(entregados: pd.DataFrame) -> pd.DataFrame:
    """Recencia, frecuencia y monto cobrado total por placa."""
    df = entregados.copy()
    df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"])
    hoy = df["fecha_entrega"].max()

    return (
        df.groupby("placa")
        .agg(
            recencia=("fecha_entrega", lambda x: (hoy - x.max()).days),
            frecuencia=("fecha_entrega", "count"),
            monto=("monto_cobrado", "sum"),
        )
        .reset_index()
    )


def segmentar_clientes(entregados: pd.DataFrame, n_clusters: int = 3) -> pd.DataFrame:
    """Agrupa a los clientes en segmentos usando K-Means sobre variables RFM."""
    rfm = calcular_rfm(entregados)
    X_scaled = StandardScaler().fit_transform(rfm[["recencia", "frecuencia", "monto"]])

    modelo = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    rfm["cluster"] = modelo.fit_predict(X_scaled)

    # Nombra los clusters según su gasto promedio (de mayor a menor)
    resumen = rfm.groupby("cluster")[["recencia", "frecuencia", "monto"]].mean()
    orden = resumen.sort_values("monto", ascending=False).index.tolist()
    nombres = ["Cliente VIP", "Cliente frecuente", "Cliente ocasional"][: len(orden)]
    rfm["segmento"] = rfm["cluster"].map(dict(zip(orden, nombres)))

    return rfm
