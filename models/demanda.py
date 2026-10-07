"""Modelo de predicción de demanda para LavaSmart.

Usa un RandomForestRegressor para estimar cuántos vehículos llegarán por día según
el día de la semana y si es feriado. El clima se quitó: no hay una fuente real de
clima en el sistema, y entrenar con un dato inventado engaña.
"""
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from config import DIAS, es_feriado

COLUMNAS_X = ["dia_semana_cod", "feriado_cod"]


def preparar_datos_diarios(lavados: pd.DataFrame) -> pd.DataFrame:
    """Cuenta los autos que ingresaron cada día (una fila de `lavados` = un auto)."""
    diario = lavados.groupby("fecha_ingreso").size().reset_index(name="cantidad_autos")
    fechas = pd.to_datetime(diario["fecha_ingreso"])
    diario["dia_semana_cod"] = fechas.dt.weekday
    diario["feriado_cod"] = [int(es_feriado(f)) for f in fechas]
    return diario


def entrenar_modelo_demanda(lavados: pd.DataFrame):
    """Entrena el modelo de regresión con el historial de lavados."""
    diario = preparar_datos_diarios(lavados)
    modelo = RandomForestRegressor(n_estimators=200, random_state=42)
    modelo.fit(diario[COLUMNAS_X], diario["cantidad_autos"])
    return modelo, diario


def predecir_proxima_semana(modelo, feriados=None) -> pd.DataFrame:
    """Autos esperados cada día de la semana. `feriados` = nombres de días marcados como feriado."""
    feriados = feriados or []
    X = pd.DataFrame(
        [[i, int(dia in feriados)] for i, dia in enumerate(DIAS)],
        columns=COLUMNAS_X,
    )
    pred = modelo.predict(X).clip(min=0).round(1)
    return pd.DataFrame({"dia_semana": DIAS, "prediccion_autos": pred})
