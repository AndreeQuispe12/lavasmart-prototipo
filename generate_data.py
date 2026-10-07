"""Genera datos SIMULADOS para poder demostrar el prototipo mientras AquaBrillo no tiene
historial digitalizado. Placas inventadas (prefijo TST), nada de clientes reales.

OJO: borra y vuelve a crear lavados, detalle, asistencia, incidencias, clientes y
liquidaciones. Los catálogos (tarifas, trabajadores, configuración) solo se crean si no
existen, así no pisa lo que el dueño haya editado.
"""
import random
from datetime import timedelta

import numpy as np
import pandas as pd

import store
from config import DIAS, TIPOS_INCIDENCIA, TIPOS_VEHICULO, es_feriado

random.seed(42)
np.random.seed(42)

DIAS_HISTORIAL = 90
PLACAS = [f"TST{100 + i}" for i in range(60)]
PESOS_PLACAS = [1 / (i + 1) ** 0.7 for i in range(len(PLACAS))]  # unos pocos clientes vuelven mucho
PESOS_VEHICULO = [0.45, 0.2, 0.2, 0.15]

store.asegurar_catalogos()
tarifas = store.leer("tarifas").set_index(["tipo_vehiculo", "tipo_lavado"])["precio"]
trabajadores = store.trabajadores_activos().set_index("trabajador")
cfg = store.configuracion()
vehiculo_de = {p: random.choices(TIPOS_VEHICULO, PESOS_VEHICULO)[0] for p in PLACAS}

lavados, detalle, asistencias, incidencias = [], [], [], []
id_lavado = 0
fin = store.ahora_lima().date() - timedelta(days=1)  # el historial termina ayer; hoy queda limpio para la demo

for offset in range(DIAS_HISTORIAL):
    fecha = fin - timedelta(days=DIAS_HISTORIAL - 1 - offset)
    f = fecha.isoformat()
    dia = DIAS[fecha.weekday()]

    # --- Asistencia: casi todos puntuales, algunos tarde, pocas faltas
    disponibles = {}
    for nombre, t in trabajadores.iterrows():
        r = random.random()
        if r < 0.05:
            asistencias.append(dict(fecha=f, trabajador=nombre, estado="Falta", hora_entrada="",
                                    hora_referencia=cfg["hora_referencia"], tolerancia_minutos=cfg["tolerancia_minutos"],
                                    autorizado=False, descuento=0))
            continue
        minutos = random.randint(470, 485) if r < 0.85 else random.randint(487, 520)  # 7:50-8:05 / 8:07-8:40
        hora = f"{minutos // 60:02d}:{minutos % 60:02d}"
        fila = dict(fecha=f, trabajador=nombre, estado="Presente", hora_entrada=hora,
                    hora_referencia=cfg["hora_referencia"], tolerancia_minutos=cfg["tolerancia_minutos"],
                    autorizado=True, descuento=0)
        puntual = store.es_puntual(fila)
        if t["modalidad"] == "Fijo" and not puntual:
            fila["autorizado"] = random.random() < 0.8  # el dueño casi siempre lo deja trabajar
            fila["descuento"] = random.choice([5, 10]) if fila["autorizado"] else 0
        asistencias.append(fila)
        if fila["autorizado"]:
            pct = None if t["modalidad"] == "Fijo" else (cfg["pct_destajo_puntual"] if puntual else cfg["pct_destajo_tarde"])
            disponibles[nombre] = pct

    if not disponibles:
        continue

    # --- Lavados del día
    base = 8 + (6 if dia in ("Sábado", "Domingo") else 0) + (3 if es_feriado(fecha) else 0)
    for _ in range(max(1, int(np.random.normal(base, 2)))):
        id_lavado += 1
        placa = random.choices(PLACAS, PESOS_PLACAS)[0]
        vehiculo = vehiculo_de[placa]
        servicios = random.choices(
            [["completo"], ["por dentro"], ["por fuera"], ["completo", "encerado"], ["motor"]],
            [0.45, 0.15, 0.15, 0.15, 0.10],
        )[0]
        precios = {s: float(tarifas[(vehiculo, s)]) for s in servicios}
        total = sum(precios.values())
        lavador = random.choice(list(disponibles))
        cobrado = total if random.random() < 0.9 else max(total - random.choice([2, 3, 5]), 1)  # ~10 % paga incompleto
        hora_in = f"{random.randint(8, 17):02d}:{random.choice(['00', '15', '30', '45'])}"
        h, m = int(hora_in[:2]), int(hora_in[3:])
        hora_out = f"{min(h + 1, 18):02d}:{m:02d}"

        lavados.append(dict(
            id_lavado=id_lavado, placa=placa, tipo_vehiculo=vehiculo, fecha_ingreso=f, hora_ingreso=hora_in,
            trabajador=lavador, porcentaje_destajo=disponibles[lavador], estado="entregado",
            fecha_entrega=f, hora_entrega=hora_out, monto_cobrado=cobrado,
            metodo_pago=random.choices(["efectivo", "Yape"], [0.6, 0.4])[0],
        ))
        for s, p in precios.items():
            detalle.append(dict(id_lavado=id_lavado, tipo_lavado=s, precio_cobrado=p))

        if random.random() < 0.06:
            incidencias.append(dict(
                id_incidencia=len(incidencias) + 1, fecha=f, placa=placa, id_lavado=id_lavado, trabajador=lavador,
                tipo_incidencia=random.choice(TIPOS_INCIDENCIA), descripcion="Incidencia simulada para pruebas.",
                estado=random.choices(["abierta", "en proceso", "resuelta"], [0.3, 0.2, 0.5])[0],
            ))

# Dos reclamos tardíos: el cliente vuelve días después y no se identifica el lavado
for placa in random.sample(PLACAS, 2):
    incidencias.append(dict(
        id_incidencia=len(incidencias) + 1, fecha=fin.isoformat(), placa=placa, id_lavado="", trabajador="",
        tipo_incidencia="Objeto faltante", descripcion="Reclamo tardío simulado, sin lavado identificado.", estado="abierta",
    ))

store.guardar("lavados", pd.DataFrame(lavados))
store.guardar("detalle_lavado", pd.DataFrame(detalle))
store.guardar("asistencia", pd.DataFrame(asistencias))
store.guardar("incidencias", pd.DataFrame(incidencias))
store.guardar("clientes", pd.DataFrame(columns=store.COLUMNAS["clientes"]))
store.guardar("liquidaciones", pd.DataFrame(columns=store.COLUMNAS["liquidaciones"]))

print(f"Generados {len(lavados)} lavados ({len(detalle)} servicios), {len(asistencias)} asistencias, {len(incidencias)} incidencias")
