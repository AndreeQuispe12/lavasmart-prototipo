"""Capa de datos del prototipo: lee/escribe los CSV y hace cumplir las reglas del negocio.

En el sistema final esto lo hacen PostgreSQL (vistas, restricciones, disparadores) y RLS.
Aquí cada función lleva al lado la regla que protege, para que se vea la correspondencia.

Convenciones: fechas en ISO (YYYY-MM-DD), horas "HH:MM", todo en hora de Lima. Nada se borra.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    CONFIG_DEFECTO,
    MEDIOS_PAGO,
    TARIFAS_EJEMPLO,
    TIPOS_LAVADO,
    TIPOS_VEHICULO,
    TRABAJADORES_EJEMPLO,
)
from models.liquidacion import devengado_diario, marcar_pagados

DATA = Path(__file__).parent / "data"
LIMA = timezone(timedelta(hours=-5))  # Perú no tiene horario de verano

COLUMNAS = {
    "tarifas": ["tipo_vehiculo", "tipo_lavado", "precio"],
    "trabajadores": ["trabajador", "modalidad", "sueldo_diario", "frecuencia_pago", "activo"],
    "configuracion": ["clave", "valor"],
    "clientes": ["placa", "nombre", "telefono"],
    "lavados": [
        "id_lavado", "placa", "tipo_vehiculo", "fecha_ingreso", "hora_ingreso", "trabajador",
        "porcentaje_destajo", "estado", "fecha_entrega", "hora_entrega", "monto_cobrado", "metodo_pago",
    ],
    "detalle_lavado": ["id_lavado", "tipo_lavado", "precio_cobrado"],
    "asistencia": [
        "fecha", "trabajador", "estado", "hora_entrada", "hora_referencia",
        "tolerancia_minutos", "autorizado", "descuento",
    ],
    "incidencias": ["id_incidencia", "fecha", "placa", "id_lavado", "trabajador", "tipo_incidencia", "descripcion", "estado"],
    "liquidaciones": ["id_liquidacion", "trabajador", "fecha_desde", "fecha_hasta", "monto", "fecha_pago"],
}
ENTERAS = {
    "lavados": ["id_lavado"],
    "detalle_lavado": ["id_lavado"],
    "incidencias": ["id_incidencia", "id_lavado"],
    "liquidaciones": ["id_liquidacion"],
    "asistencia": ["tolerancia_minutos"],
}
DECIMALES = {
    "tarifas": ["precio"],
    "trabajadores": ["sueldo_diario"],
    "lavados": ["porcentaje_destajo", "monto_cobrado"],
    "detalle_lavado": ["precio_cobrado"],
    "asistencia": ["descuento"],
    "liquidaciones": ["monto"],
}
BOOLEANAS = {"trabajadores": ["activo"], "asistencia": ["autorizado"]}


class ReglaDeNegocio(Exception):
    """Se intentó algo que las reglas del dueño no permiten. El mensaje va tal cual a la pantalla."""


# ---------------------------------------------------------------------------
# Lectura / escritura de CSV
# ---------------------------------------------------------------------------
def leer(nombre: str) -> pd.DataFrame:
    ruta = DATA / f"{nombre}.csv"
    if ruta.exists():
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    else:
        df = pd.DataFrame(columns=COLUMNAS[nombre], dtype=str)
    for c in DECIMALES.get(nombre, []):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ENTERAS.get(nombre, []):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in BOOLEANAS.get(nombre, []):
        df[c] = df[c] == "True"
    return df


def guardar(nombre: str, df: pd.DataFrame) -> None:
    DATA.mkdir(exist_ok=True)
    df[COLUMNAS[nombre]].to_csv(DATA / f"{nombre}.csv", index=False)


def agregar(nombre: str, fila: dict) -> None:
    """Añade una fila al final del CSV (los campos que falten quedan vacíos)."""
    DATA.mkdir(exist_ok=True)
    ruta = DATA / f"{nombre}.csv"
    pd.DataFrame([fila], columns=COLUMNAS[nombre]).to_csv(ruta, mode="a", header=not ruta.exists(), index=False)


def siguiente_id(nombre: str, col: str) -> int:
    df = leer(nombre)
    return 1 if df.empty else int(df[col].max()) + 1


def ahora_lima() -> datetime:
    return datetime.now(LIMA)


def hoy_lima() -> str:
    return ahora_lima().strftime("%Y-%m-%d")


def asegurar_catalogos() -> None:
    """Crea tarifas, trabajadores y configuración con valores de ejemplo si todavía no existen."""
    if not (DATA / "tarifas.csv").exists():
        filas = [
            {"tipo_vehiculo": v, "tipo_lavado": l, "precio": TARIFAS_EJEMPLO[l][v]}
            for l in TIPOS_LAVADO
            for v in TIPOS_VEHICULO
        ]
        guardar("tarifas", pd.DataFrame(filas))
    if not (DATA / "trabajadores.csv").exists():
        guardar("trabajadores", pd.DataFrame(TRABAJADORES_EJEMPLO).assign(activo=True))
    if not (DATA / "configuracion.csv").exists():
        guardar("configuracion", pd.DataFrame(list(CONFIG_DEFECTO.items()), columns=["clave", "valor"]))


# ---------------------------------------------------------------------------
# Catálogos y configuración
# ---------------------------------------------------------------------------
def configuracion() -> dict:
    valores = dict(CONFIG_DEFECTO)
    valores.update(dict(leer("configuracion")[["clave", "valor"]].itertuples(index=False)))
    return {
        "hora_referencia": valores["hora_referencia"],
        "tolerancia_minutos": int(valores["tolerancia_minutos"]),
        "pct_destajo_puntual": float(valores["pct_destajo_puntual"]),
        "pct_destajo_tarde": float(valores["pct_destajo_tarde"]),
    }


def guardar_configuracion(cfg: dict) -> None:
    guardar("configuracion", pd.DataFrame([(k, str(v)) for k, v in cfg.items()], columns=["clave", "valor"]))


def matriz_tarifas() -> pd.DataFrame:
    """Tarifas como matriz: filas = tipo de lavado, columnas = tipo de vehículo."""
    t = leer("tarifas")
    return t.pivot(index="tipo_lavado", columns="tipo_vehiculo", values="precio").loc[TIPOS_LAVADO, TIPOS_VEHICULO]


def guardar_matriz_tarifas(matriz: pd.DataFrame) -> None:
    filas = [
        {"tipo_vehiculo": v, "tipo_lavado": l, "precio": float(matriz.loc[l, v])}
        for l in TIPOS_LAVADO
        for v in TIPOS_VEHICULO
    ]
    guardar("tarifas", pd.DataFrame(filas))


def trabajadores_activos() -> pd.DataFrame:
    t = leer("trabajadores")
    return t[t["activo"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Placa y clientes (un cliente = un vehículo, identificado por la placa)
# ---------------------------------------------------------------------------
def normalizar_placa(texto: str) -> str:
    """Mayúsculas, sin espacios ni guiones. Es dato personal (Ley N.° 29733)."""
    placa = re.sub(r"[^A-Z0-9]", "", (texto or "").upper())
    if not 5 <= len(placa) <= 7:
        raise ReglaDeNegocio("La placa debe tener entre 5 y 7 letras o números.")
    return placa


def guardar_cliente(placa: str, nombre: str, telefono: str) -> None:
    """Nombre y teléfono son opcionales; si no hay ninguno no se crea fila."""
    nombre, telefono = nombre.strip(), telefono.strip()
    if not (nombre or telefono):
        return
    clientes = leer("clientes")
    clientes = clientes[clientes["placa"] != placa]
    guardar("clientes", pd.concat([clientes, pd.DataFrame([{"placa": placa, "nombre": nombre, "telefono": telefono}])]))


# ---------------------------------------------------------------------------
# Precio (tipo de vehículo × tipo de lavado, varios servicios se suman)
# ---------------------------------------------------------------------------
def precio_servicios(tipo_vehiculo: str, servicios: list) -> dict:
    t = leer("tarifas")
    t = t[t["tipo_vehiculo"] == tipo_vehiculo].set_index("tipo_lavado")["precio"]
    return {s: float(t[s]) for s in servicios}


# ---------------------------------------------------------------------------
# Asistencia
# ---------------------------------------------------------------------------
def _minutos(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def es_puntual(fila_asistencia) -> bool:
    """Puntual = marcó a la hora de referencia + tolerancia (valores congelados en la fila)."""
    limite = _minutos(fila_asistencia["hora_referencia"]) + int(fila_asistencia["tolerancia_minutos"])
    return _minutos(fila_asistencia["hora_entrada"]) <= limite


def marcar_asistencia(trabajador: str, fecha: str, estado: str, hora_entrada: str = "") -> str:
    """Registra asistencia. Devuelve un aviso si requiere decisión del dueño."""
    asistencia = leer("asistencia")
    if ((asistencia["fecha"] == fecha) & (asistencia["trabajador"] == trabajador)).any():
        raise ReglaDeNegocio(f"{trabajador} ya tiene asistencia registrada el {fecha}.")

    cfg = configuracion()
    t = leer("trabajadores").set_index("trabajador").loc[trabajador]
    fila = {
        "fecha": fecha,
        "trabajador": trabajador,
        "estado": estado,
        "hora_entrada": "" if estado == "Falta" else hora_entrada,
        # Dato congelado: la hora y la tolerancia vigentes ESE día.
        "hora_referencia": cfg["hora_referencia"],
        "tolerancia_minutos": cfg["tolerancia_minutos"],
        "autorizado": False,
        "descuento": 0,
    }
    aviso = ""
    if estado == "Presente":
        puntual = es_puntual(fila)
        # El sueldo fijo que llega tarde necesita la decisión del dueño; el destajo siempre trabaja.
        fila["autorizado"] = puntual or t["modalidad"] == "Destajo"
        if not fila["autorizado"]:
            aviso = f"{trabajador} llegó tarde (sueldo fijo): el dueño debe decidir si lo deja trabajar y cuánto descuenta."
    agregar("asistencia", fila)
    return aviso


def decidir_fijo_tardio(trabajador: str, fecha: str, autorizado: bool, descuento: float) -> None:
    """El dueño decide si el fijo tardío trabaja y cuánto se le descuenta (monto a mano)."""
    if descuento < 0:
        raise ReglaDeNegocio("El descuento no puede ser negativo.")
    if _dia_cerrado(trabajador, fecha):
        raise ReglaDeNegocio("Ese día ya está en una liquidación cerrada y no se modifica.")
    a = leer("asistencia")
    fila = (a["fecha"] == fecha) & (a["trabajador"] == trabajador)
    a.loc[fila, ["autorizado", "descuento"]] = [autorizado, float(descuento)]
    guardar("asistencia", a)


def lavadores_disponibles(fecha: str) -> pd.DataFrame:
    """Trabajadores activos con asistencia 'Presente' y autorizada ese día (regla: sin asistencia no se asigna)."""
    a = leer("asistencia")
    ok = a[(a["fecha"] == fecha) & (a["estado"] == "Presente") & a["autorizado"]]
    t = trabajadores_activos()
    return t[t["trabajador"].isin(ok["trabajador"])].reset_index(drop=True)


def porcentaje_destajo(trabajador: str, fecha: str):
    """50 % si marcó puntual, 40 % si no; None para sueldo fijo. Vale todo el día."""
    t = leer("trabajadores").set_index("trabajador").loc[trabajador]
    if t["modalidad"] == "Fijo":
        return None
    a = leer("asistencia")
    fila = a[(a["fecha"] == fecha) & (a["trabajador"] == trabajador)]
    if fila.empty or fila.iloc[0]["estado"] != "Presente":
        raise ReglaDeNegocio(f"{trabajador} no tiene asistencia registrada hoy: primero se marca entrada, después se reciben autos.")
    cfg = configuracion()
    return cfg["pct_destajo_puntual"] if es_puntual(fila.iloc[0]) else cfg["pct_destajo_tarde"]


# ---------------------------------------------------------------------------
# Lavados: ingreso (sin cobro) y entrega (con cobro)
# ---------------------------------------------------------------------------
def registrar_ingreso(placa: str, tipo_vehiculo: str, servicios: list, trabajador: str, nombre: str = "", telefono: str = "") -> int:
    placa = normalizar_placa(placa)
    if not servicios:
        raise ReglaDeNegocio("Elige al menos un servicio.")
    if not trabajador:
        raise ReglaDeNegocio("Elige el lavador (un lavador por vehículo).")

    lavados = leer("lavados")
    if ((lavados["placa"] == placa) & (lavados["estado"] == "en proceso")).any():
        raise ReglaDeNegocio(f"{placa} ya está en proceso. Entrégalo antes de registrar otro ingreso.")

    ahora = ahora_lima()
    fecha = ahora.strftime("%Y-%m-%d")
    pct = porcentaje_destajo(trabajador, fecha)  # también valida que haya asistencia
    if trabajador not in lavadores_disponibles(fecha)["trabajador"].values:
        raise ReglaDeNegocio(f"{trabajador} no está autorizado para trabajar hoy.")

    precios = precio_servicios(tipo_vehiculo, servicios)
    id_lavado = siguiente_id("lavados", "id_lavado")
    agregar(
        "lavados",
        {
            "id_lavado": id_lavado,
            "placa": placa,
            "tipo_vehiculo": tipo_vehiculo,
            "fecha_ingreso": fecha,
            "hora_ingreso": ahora.strftime("%H:%M"),
            "trabajador": trabajador,
            "porcentaje_destajo": pct,  # congelado
            "estado": "en proceso",
            "monto_cobrado": 0,  # al ingresar nunca se cobra
        },
    )
    for servicio, precio in precios.items():
        agregar("detalle_lavado", {"id_lavado": id_lavado, "tipo_lavado": servicio, "precio_cobrado": precio})  # congelado
    guardar_cliente(placa, nombre, telefono)
    return id_lavado


def registrar_entrega(id_lavado: int, monto_cobrado: float, metodo_pago: str) -> None:
    lavados = leer("lavados")
    fila = lavados["id_lavado"] == id_lavado
    if not fila.any() or lavados.loc[fila, "estado"].iloc[0] != "en proceso":
        raise ReglaDeNegocio("Ese lavado no está en proceso.")
    total = v_lavado().set_index("id_lavado").loc[id_lavado, "total"]
    if metodo_pago not in MEDIOS_PAGO:
        raise ReglaDeNegocio("El medio de pago es efectivo o Yape.")
    if not 0 < monto_cobrado <= total:
        raise ReglaDeNegocio(f"El monto cobrado debe ser mayor que 0 y no pasar de S/ {total:.2f}.")

    ahora = ahora_lima()
    lavados.loc[fila, ["estado", "fecha_entrega", "hora_entrega", "monto_cobrado", "metodo_pago"]] = [
        "entregado", ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M"), float(monto_cobrado), metodo_pago,
    ]
    guardar("lavados", lavados)


def v_lavado() -> pd.DataFrame:
    """Equivalente a la vista v_lavado: el total se CALCULA sumando el detalle, no se guarda.

    estado_pago: 'sin_cobrar' si no está entregado (un auto en proceso no es deuda),
    'incompleto' si entregado con saldo, 'completo' si entregado y saldado.
    """
    lav = leer("lavados")
    total = leer("detalle_lavado").groupby("id_lavado")["precio_cobrado"].sum()
    lav["total"] = lav["id_lavado"].map(total).fillna(0.0).astype(float)
    entregado = lav["estado"] == "entregado"
    lav["saldo"] = (lav["total"] - lav["monto_cobrado"]).where(entregado, 0.0).round(2)
    lav["estado_pago"] = np.where(~entregado, "sin_cobrar", np.where(lav["saldo"] <= 0, "completo", "incompleto"))
    return lav


def caja_dia(fecha: str) -> pd.DataFrame:
    """Equivalente a v_caja_dia: lo cobrado ese día por medio de pago, según la fecha de ENTREGA."""
    lav = leer("lavados")
    dia = lav[(lav["estado"] == "entregado") & (lav["fecha_entrega"] == fecha)]
    caja = dia.groupby("metodo_pago")["monto_cobrado"].sum().reindex(MEDIOS_PAGO, fill_value=0.0)
    return caja.reset_index().rename(columns={"metodo_pago": "medio", "monto_cobrado": "cobrado"})


# ---------------------------------------------------------------------------
# Incidencias (siempre ancladas a la placa; al lavado solo si se identifica)
# ---------------------------------------------------------------------------
def registrar_incidencia(placa: str, id_lavado, tipo: str, descripcion: str, trabajador: str = "") -> None:
    placa = normalizar_placa(placa)
    if pd.notna(id_lavado):
        lav = leer("lavados").set_index("id_lavado")
        if int(id_lavado) not in lav.index or lav.loc[int(id_lavado), "placa"] != placa:
            raise ReglaDeNegocio("Ese lavado no corresponde a la placa indicada.")
        trabajador = lav.loc[int(id_lavado), "trabajador"]
    agregar(
        "incidencias",
        {
            "id_incidencia": siguiente_id("incidencias", "id_incidencia"),
            "fecha": hoy_lima(),
            "placa": placa,
            "id_lavado": id_lavado if pd.notna(id_lavado) else "",
            "trabajador": trabajador,
            "tipo_incidencia": tipo,
            "descripcion": descripcion.strip(),
            "estado": "abierta",
        },
    )


def cambiar_estado_incidencia(id_incidencia: int, estado: str) -> None:
    inc = leer("incidencias")
    inc.loc[inc["id_incidencia"] == id_incidencia, "estado"] = estado
    guardar("incidencias", inc)


# ---------------------------------------------------------------------------
# Liquidación: devengar no es pagar
# ---------------------------------------------------------------------------
def _dia_cerrado(trabajador: str, fecha: str) -> bool:
    liq = leer("liquidaciones")
    return bool(((liq["trabajador"] == trabajador) & (liq["fecha_desde"] <= fecha) & (liq["fecha_hasta"] >= fecha)).any())


def devengado(desde: str, hasta: str) -> pd.DataFrame:
    return marcar_pagados(
        devengado_diario(v_lavado(), leer("asistencia"), trabajadores_activos(), desde, hasta),
        leer("liquidaciones"),
    )


def registrar_pago(trabajador: str, desde: str, hasta: str) -> float:
    """Cierra el periodo del trabajador con lo devengado. Una liquidación cerrada no se toca."""
    liq = leer("liquidaciones")
    traslape = liq[(liq["trabajador"] == trabajador) & (liq["fecha_desde"] <= hasta) & (liq["fecha_hasta"] >= desde)]
    if not traslape.empty:
        raise ReglaDeNegocio(f"El periodo se cruza con una liquidación ya cerrada de {trabajador}.")
    dev = devengado(desde, hasta)
    monto = round(float(dev.loc[dev["trabajador"] == trabajador, "devengado"].sum()), 2)
    if monto <= 0:
        raise ReglaDeNegocio("No hay nada devengado en ese periodo.")
    agregar(
        "liquidaciones",
        {
            "id_liquidacion": siguiente_id("liquidaciones", "id_liquidacion"),
            "trabajador": trabajador,
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "monto": monto,
            "fecha_pago": hoy_lima(),
        },
    )
    return monto
