# LavaSmart — Prototipo Streamlit (validación con el dueño)

Prototipo en Streamlit + CSV del sistema LavaSmart para **AquaBrillo**, lavadero de autos en Lima.
Proyecto del curso Innovación y Transformación Digital (UTP, 2026 Ciclo 2).

## Propósito de este prototipo
Mostrar al dueño y al profesor cómo se vería el sistema final. NO es el sistema final.
- Sistema final (ya diseñado): Next.js en Vercel + PostgreSQL en Supabase (RLS), ML batch semanal.
- Este prototipo debe reproducir el **flujo y las reglas de negocio reales**, aunque use CSV.
- Toda decisión de diseño debe parecerse a lo que el dueño ve en su cuaderno hoy.

## Reglas de negocio (obligatorias)

**Precios**
- Precio = tipo de vehículo × tipo de lavado (tabla de tarifas, no se escribe a mano).
- Vehículos: sedán, station wagon, SUV, camioneta.
- Lavados: completo, por dentro, por fuera, encerado, motor.
- Una visita puede tener varios servicios; el total es la suma (ej. completo + encerado en camioneta = S/ 45; completo sedán S/ 20, camioneta S/ 25).
- Las tarifas actuales son de ejemplo: el dueño las reemplaza luego por las reales.
- Congelar el precio: guardar `precio_cobrado` en cada detalle; subir una tarifa NO cambia reportes pasados.

**Clientes**
- Se identifican por la **placa** (normalizada: mayúsculas, sin espacios/guiones). Un cliente = un vehículo.
- La placa es dato personal (Ley N.° 29733): es **seudonimización, NO anonimización**. Nunca escribir "sin datos personales" en la app ni en textos.

**Cobro**
- Se cobra **al entregar el auto**. El lavado se registra en dos momentos: ingreso y entrega.
- Medios de pago: solo **efectivo** y **Yape**.
- Si el pago queda incompleto, el cliente NO vuelve a cancelar; el saldo se anota solo para calcular el destajo.
- Un auto en proceso (cobrado 0, no entregado) **no es deuda**. Estados de pago: `sin_cobrar` (no entregado), `incompleto`, `completo`. Toda consulta de saldos filtra por lavados entregados.
- La caja del día agrupa por fecha de **entrega**, en hora de Lima (America/Lima).

**Personal**
- Un solo lavador por vehículo.
- **Destajo**: 50 % de lo *cobrado* si marcó asistencia a las 8:05 o antes (hora de referencia 8:00, tolerancia 5 min); 40 % si llegó después. La regla vale todo el día y para todos. Guardar el porcentaje en el lavado al asignarlo (dato congelado).
- No se puede asignar un auto a un lavador **sin asistencia registrada** ese día.
- **Sueldo fijo**: el monto lo asigna el dueño. Si llega tarde, el descuento en soles lo ingresa el dueño a mano, y el dueño decide si lo deja trabajar ese día.
- **Frecuencia de pago**: fijos = semanal siempre; destajo = diario o semanal (elige el trabajador). Devengar no es pagar: la liquidación calcula todos los días, pero el pago sale cuando se entrega el dinero.
- Una liquidación cerrada no se modifica.

**Incidencias**
- Rayones al secar, aspirado no hecho, objetos faltantes.
- Se asocian siempre a la placa y, si se identifica, al lavado. Un reclamo tardío queda sin lavado asociado.

**Roles**
- **Operador**: recibe autos, registra, cobra, marca asistencia, anota incidencias.
- **Dueño**: todo lo del operador + tarifas, configuración, liquidación, dashboard y ML.
- Los lavadores NO usan el sistema.

**Datos**
- Sin borrados físicos: usar un campo `activo` o estado, no eliminar filas.
- Los totales no se guardan: se calculan sumando detalles.

## Tareas pendientes de alinear (en este orden)
1. Registro en dos momentos (ingreso → entrega con cobro).
2. Precio automático por tabla de tarifas + varios servicios por visita.
3. Liquidación con destajo 50/40 según hora de marcación, sobre lo cobrado, con frecuencia diaria/semanal.
4. Asistencia que alimenta la liquidación y bloquea asignar sin asistencia.
5. Estados de pago y saldos correctos (`sin_cobrar` no es deuda).
6. Dos roles (operador/dueño) con pestañas según el rol.
7. Incidencias ligadas a placa y lavado.

## Correcciones obligatorias de seguridad y texto
- **No subir credenciales al repo.** Sacar usuario/contraseña de `config.py`: leerlos de variables de entorno o `st.secrets` (`.streamlit/secrets.toml` va en `.gitignore`) y dejar un `secrets.toml.example` sin valores reales.
- Reemplazar cualquier frase tipo "sin guardar datos personales" por seudonimización.
- El clima en el modelo de demanda no tiene fuente real: quitarlo o marcarlo claramente como dato simulado.
- Los datos de `generate_data.py` son simulados: indicar en la interfaz que los gráficos de demanda y segmentación son **ilustrativos**.
- Usar solo placas inventadas. Nunca datos reales de clientes.

## Modelos de ML (se mantienen)
- Demanda: `RandomForestRegressor` (autos esperados por día).
- Segmentación: `KMeans` sobre RFM (recencia, frecuencia, monto) usando la placa como identificador.

## Cómo correr
```
pip install -r requirements.txt
python generate_data.py
streamlit run app.py
```

## Forma de trabajar
- Español casual en comentarios y mensajes; textos de la interfaz en español.
- Avanza por tu cuenta tarea por tarea y al final de cada una resume en 2-3 líneas qué cambiaste.
- Cambia la interfaz lo mínimo necesario: estilo simple, botones grandes, badges de color para pagos incompletos e incidencias abiertas.
- Antes de borrar o reestructurar archivos grandes, avisa.
- Si una regla de este archivo choca con lo que ves en el código, gana este archivo.
