"""Constantes compartidas por app.py, store.py y generate_data.py.

Aquí NO hay credenciales: los usuarios se leen de st.secrets (ver
.streamlit/secrets.toml.example).
"""

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

TIPOS_VEHICULO = ["sedán", "station wagon", "SUV", "camioneta"]
TIPOS_LAVADO = ["completo", "por dentro", "por fuera", "encerado", "motor"]

# Tarifas de EJEMPLO: el dueño las reemplaza por las reales desde la pantalla de tarifas.
# (completo sedán = 20, completo camioneta = 25, completo + encerado camioneta = 45)
TARIFAS_EJEMPLO = {
    "completo": {"sedán": 20, "station wagon": 22, "SUV": 24, "camioneta": 25},
    "por dentro": {"sedán": 12, "station wagon": 13, "SUV": 14, "camioneta": 15},
    "por fuera": {"sedán": 10, "station wagon": 11, "SUV": 12, "camioneta": 13},
    "encerado": {"sedán": 15, "station wagon": 17, "SUV": 18, "camioneta": 20},
    "motor": {"sedán": 15, "station wagon": 15, "SUV": 18, "camioneta": 18},
}

# Valores iniciales de la configuración (el dueño los cambia desde la app).
CONFIG_DEFECTO = {
    "hora_referencia": "08:00",
    "tolerancia_minutos": "5",
    "pct_destajo_puntual": "50",
    "pct_destajo_tarde": "40",
}

# modalidad: "Destajo" o "Fijo". sueldo_diario solo aplica a los fijos.
# frecuencia_pago: los fijos siempre "semanal"; los de destajo "diario" o "semanal".
TRABAJADORES_EJEMPLO = [
    {"trabajador": "Carlos", "modalidad": "Destajo", "sueldo_diario": 0, "frecuencia_pago": "diario"},
    {"trabajador": "Luis", "modalidad": "Destajo", "sueldo_diario": 0, "frecuencia_pago": "semanal"},
    {"trabajador": "Miguel", "modalidad": "Fijo", "sueldo_diario": 40, "frecuencia_pago": "semanal"},
    {"trabajador": "José", "modalidad": "Destajo", "sueldo_diario": 0, "frecuencia_pago": "diario"},
    {"trabajador": "Pedro", "modalidad": "Fijo", "sueldo_diario": 40, "frecuencia_pago": "semanal"},
]

MEDIOS_PAGO = ["efectivo", "Yape"]

TIPOS_INCIDENCIA = ["Rayón al secar", "Aspirado no hecho", "Objeto faltante", "Otro"]
ESTADOS_INCIDENCIA = ["abierta", "en proceso", "resuelta"]

# Feriados nacionales de fecha fija en Perú (mes, día). Los móviles (Semana Santa) no están.
FERIADOS_FIJOS = {
    (1, 1), (5, 1), (6, 29), (7, 23), (7, 28), (7, 29),
    (8, 6), (8, 30), (10, 8), (11, 1), (12, 8), (12, 9), (12, 25),
}


def es_feriado(fecha) -> bool:
    return (fecha.month, fecha.day) in FERIADOS_FIJOS
