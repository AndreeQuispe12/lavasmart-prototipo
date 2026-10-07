"""Liquidación del personal de AquaBrillo (funciones puras: reciben DataFrames).

- Destajo: % de lo COBRADO. El porcentaje (50 / 40) está congelado en cada lavado
  (lavados.porcentaje_destajo), NO se lee de la configuración: si el dueño cambia el
  porcentaje, los pagos ya devengados no se reescriben.
- Fijo: sueldo diario por cada día con asistencia autorizada, menos el descuento que
  el dueño anotó a mano ese día.
- Devengar no es pagar: el devengado se calcula todos los días; el pago es un registro
  aparte (liquidaciones.csv) que cierra un periodo.
"""
import pandas as pd

COLUMNAS_DEVENGADO = ["fecha", "trabajador", "modalidad", "autos", "cobrado", "devengado"]


def devengado_diario(lavados: pd.DataFrame, asistencia: pd.DataFrame, trabajadores: pd.DataFrame, desde: str, hasta: str) -> pd.DataFrame:
    """Devengado por trabajador y día entre `desde` y `hasta` (fechas ISO, inclusive)."""
    entregados = lavados[(lavados["estado"] == "entregado") & lavados["fecha_entrega"].between(desde, hasta)]
    presentes = asistencia[
        (asistencia["estado"] == "Presente") & asistencia["autorizado"] & asistencia["fecha"].between(desde, hasta)
    ]

    filas = []
    for _, t in trabajadores.iterrows():
        if t["modalidad"] == "Destajo":
            propios = entregados[entregados["trabajador"] == t["trabajador"]]
            for fecha, g in propios.groupby("fecha_entrega"):
                filas.append(
                    {
                        "fecha": fecha,
                        "trabajador": t["trabajador"],
                        "modalidad": "Destajo",
                        "autos": len(g),
                        "cobrado": g["monto_cobrado"].sum(),
                        "devengado": (g["monto_cobrado"] * g["porcentaje_destajo"].fillna(0) / 100).sum(),
                    }
                )
        else:
            for _, a in presentes[presentes["trabajador"] == t["trabajador"]].iterrows():
                dia = entregados[(entregados["trabajador"] == t["trabajador"]) & (entregados["fecha_entrega"] == a["fecha"])]
                filas.append(
                    {
                        "fecha": a["fecha"],
                        "trabajador": t["trabajador"],
                        "modalidad": "Fijo",
                        "autos": len(dia),
                        "cobrado": dia["monto_cobrado"].sum(),
                        "devengado": max(t["sueldo_diario"] - a["descuento"], 0),
                    }
                )

    df = pd.DataFrame(filas, columns=COLUMNAS_DEVENGADO)
    df["devengado"] = df["devengado"].astype(float).round(2)
    return df.sort_values(["fecha", "trabajador"]).reset_index(drop=True)


def marcar_pagados(devengado: pd.DataFrame, liquidaciones: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna `pagado`: el día cae dentro de una liquidación ya cerrada."""
    df = devengado.copy()
    df["pagado"] = False
    for _, liq in liquidaciones.iterrows():
        cubierto = (
            (df["trabajador"] == liq["trabajador"])
            & (df["fecha"] >= liq["fecha_desde"])
            & (df["fecha"] <= liq["fecha_hasta"])
        )
        df.loc[cubierto, "pagado"] = True
    return df


def resumen_por_trabajador(devengado_con_pago: pd.DataFrame, trabajadores: pd.DataFrame) -> pd.DataFrame:
    """Una fila por trabajador activo: autos, cobrado, devengado, ya pagado y pendiente."""
    filas = []
    for _, t in trabajadores.iterrows():
        d = devengado_con_pago[devengado_con_pago["trabajador"] == t["trabajador"]]
        pagado = d.loc[d["pagado"], "devengado"].sum()
        filas.append(
            {
                "trabajador": t["trabajador"],
                "modalidad": t["modalidad"],
                "frecuencia_pago": t["frecuencia_pago"],
                "autos": int(d["autos"].sum()),
                "cobrado": round(d["cobrado"].sum(), 2),
                "devengado": round(d["devengado"].sum(), 2),
                "pagado": round(pagado, 2),
                "pendiente": round(d["devengado"].sum() - pagado, 2),
            }
        )
    return pd.DataFrame(filas)
