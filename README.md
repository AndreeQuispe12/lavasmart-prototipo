# LavaSmart · Prototipo de validación

Prototipo en **Streamlit + CSV** del sistema de gestión operativa de **AquaBrillo**, un lavadero
de autos en Lima, Perú. Sustituye el cuaderno donde hoy se anotan servicios, cobros, asistencia
y reclamos, y muestra cómo se vería el sistema final.

> Proyecto del curso Innovación y Transformación Digital (UTP, 2026-2).
> **Esto no es el sistema final.** El sistema final es Next.js + PostgreSQL (Supabase, con RLS).
> Este prototipo reproduce el *flujo* y las *reglas de negocio* reales, pero guarda en CSV.

## Qué incluye

- **Registro en dos momentos:** ingreso del auto (sin cobro) y entrega (cobro en efectivo o Yape).
- **Precio automático** por tipo de vehículo × tipo de lavado; varios servicios por visita se suman.
- **Asistencia** que alimenta el pago y bloquea asignar autos a quien no marcó entrada.
- **Liquidación** del personal: destajo (50 % / 40 % según puntualidad) y sueldo fijo.
- **Incidencias** ligadas a la placa y, si se identifica, al lavado.
- **Dos roles:** operador y dueño, con pestañas distintas.
- **Dos modelos de ML** (ilustrativos): predicción de demanda y segmentación de clientes.

## Cómo correrlo

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y completa las claves
python generate_data.py                                      # datos SIMULADOS
streamlit run app.py
```

En Windows, si `cp` no existe, copia el archivo a mano o usa `copy`.

### Usuarios y claves

Viven en `.streamlit/secrets.toml`, que **no se sube al repositorio**. Ejemplo:

```toml
[usuarios.dueno]
clave = "tu-clave"
rol = "dueno"                # "operador" o "dueno"
nombre = "Nombre visible"    # opcional; se muestra en la barra lateral

[usuarios.operador]
clave = "otra-clave"
rol = "operador"
nombre = "Nombre visible"
```

El nombre de usuario es lo que va después de `usuarios.`. Reinicia la app tras editar el archivo.

## Pestañas por rol

| Pestaña | Operador | Dueño | Qué hace |
|---|:-:|:-:|---|
| Registrar servicio | ✔ | ✔ | Ingreso (sin cobro) y entrega (cobro) |
| Asistencia | ✔ | ✔ | Marca entrada o falta; el dueño decide sobre fijos con tardanza |
| Incidencias | ✔ | ✔ | Siempre con placa; con lavado si se identifica |
| Caja del día | ✔ | ✔ | Cobranza por medio de pago, por fecha de **entrega** (hora de Lima) |
| Liquidación | | ✔ | Devengado diario, pagos y liquidaciones cerradas |
| Dashboard | | ✔ | Indicadores del día y la semana |
| Tarifas y configuración | | ✔ | Tarifas, hora de referencia, tolerancia y % de destajo |
| Personal | | ✔ | Modalidad, sueldo diario, frecuencia de pago, altas y bajas |
| Predicción de demanda | | ✔ | `RandomForestRegressor` (ilustrativo) |
| Segmentación de clientes | | ✔ | `KMeans` sobre RFM por placa (ilustrativo) |

## Reglas del negocio que hace cumplir

- **Precio** = tipo de vehículo × tipo de lavado. Cada detalle guarda `precio_cobrado`: subir una
  tarifa no cambia los reportes pasados.
- **El total no se guarda:** se calcula sumando los detalles.
- **Cobro al entregar**, nunca al recibir. Solo efectivo y Yape.
- **Estados de pago:** `sin_cobrar` (no entregado, **no es deuda**), `incompleto` y `completo`.
  Si el cliente paga incompleto no vuelve a pagar: el saldo solo sirve para calcular el destajo.
- **Un lavador por vehículo.**
- **Destajo:** 50 % de lo *cobrado* si marcó a las 8:05 o antes, 40 % si llegó después. El
  porcentaje se congela en el lavado al asignarlo.
- **Sueldo fijo:** monto diario; si llega tarde, el dueño decide si trabaja y cuánto se descuenta.
- **Devengar no es pagar:** la liquidación se calcula a diario; el pago es un registro aparte.
  Una liquidación cerrada no se modifica.
- **Sin borrados físicos:** baja lógica con `activo` o estado.

## Datos y privacidad

- `generate_data.py` crea unos 90 días de historial **simulado**, con placas inventadas
  (prefijo `TST`). Vuelve a crear los movimientos cada vez que se ejecuta; las tarifas, los
  trabajadores y la configuración solo se crean si no existen.
- Los CSV de `data/` **no se versionan**: con el uso real contendrían placas.
- La **placa es dato personal** (Ley N.° 29733 del Perú). Usarla como identificador es
  seudonimización, **no** anonimización.
- Los gráficos de demanda y segmentación son **ilustrativos**: se basan en datos simulados.
  El modelo de demanda no usa clima porque no hay una fuente real.

## Estructura

```
app.py              Interfaz Streamlit (login, roles, pestañas)
store.py            Lectura y escritura de CSV + reglas del negocio
config.py           Constantes y valores de ejemplo (sin credenciales)
generate_data.py    Datos simulados
models/             demanda.py · segmentacion.py · liquidacion.py
assets/             logo y fondo del login
data/               CSV (se generan; no se versionan)
.streamlit/         config.toml · secrets.toml.example   (secrets.toml va ignorado)
```

## Hacia el sistema final

Cuando el prototipo esté validado con el dueño, el paso siguiente es migrar a Next.js (Vercel) y
PostgreSQL en Supabase, con la autorización resuelta por RLS y el proceso de analítica semanal en
Python. Las funciones de `store.py` marcan qué parte hará la base de datos (vistas,
restricciones, disparadores).
