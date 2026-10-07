import base64
import hmac
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image

import store
from config import DIAS, MEDIOS_PAGO, TIPOS_INCIDENCIA, TIPOS_LAVADO, TIPOS_VEHICULO, ESTADOS_INCIDENCIA
from models.demanda import entrenar_modelo_demanda, predecir_proxima_semana
from models.liquidacion import resumen_por_trabajador
from models.segmentacion import segmentar_clientes
from store import ReglaDeNegocio

st.set_page_config(page_title="LavaSmart - AquaBrillo", page_icon=Image.open(Path(__file__).parent / "assets" / "logo.png"), layout="wide")

store.asegurar_catalogos()

ROLES = {"operador": "Operador", "dueno": "Dueño"}

# Dos roles: el dueño tiene TODO lo del operador y además lo suyo (superconjunto).
PAGINAS_OPERADOR = [
    ("Registrar servicio", "edit_document"),
    ("Asistencia", "badge"),
    ("Incidencias", "warning"),
    ("Caja del día", "point_of_sale"),
]
PAGINAS_DUENO = PAGINAS_OPERADOR + [
    ("Liquidación", "payments"),
    ("Dashboard", "dashboard"),
    ("Tarifas y configuración", "sell"),
    ("Personal", "engineering"),
    ("Predicción de demanda", "trending_up"),
    ("Segmentación de clientes", "groups"),
]

AVISO_SIMULADO = (
    "Datos **simulados** (generate_data.py). Los gráficos de este módulo son **ilustrativos**: "
    "AquaBrillo todavía no tiene un histórico real digitalizado."
)

# ---------------------------------------------------------------------------
# Paleta: azul marino (agua profunda) + aqua. Verde/ámbar/rojo solo para estados.
# ---------------------------------------------------------------------------
NAVY = "#0B2545"
NAVY_2 = "#13315C"
ACCENT = "#0891B2"
AQUA = "#22D3EE"
SUCCESS = "#059669"
DANGER = "#E11D48"
WARNING = "#D97706"
GRAY = "#64748B"

# ---------------------------------------------------------------------------
# Imágenes: logo y foto de fondo del login (carpeta assets/), incrustadas en base64
# ---------------------------------------------------------------------------
ASSETS = Path(__file__).parent / "assets"


@st.cache_resource
def _datauri(nombre: str, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode((ASSETS / nombre).read_bytes()).decode()


def logo_img(tam: int = 40) -> str:
    return (
        f'<img src="{_datauri("logo.png", "image/png")}" width="{tam}" height="{tam}" '
        f'style="border-radius:{tam // 4}px;background:#FFFFFF;display:block;object-fit:cover;" alt="LavaSmart">'
    )


# ---------------------------------------------------------------------------
# Estilos globales
# ---------------------------------------------------------------------------
st.markdown(f"""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" />
<link rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />

<style>
html, body, [data-testid="stAppViewContainer"] {{ font-family: 'Inter', 'Source Sans', sans-serif; }}
[data-testid="stAppViewContainer"] {{ background: linear-gradient(180deg, #EEF6FA 0%, #F7FAFC 320px); }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2rem; max-width: 1280px; }}

.material-symbols-outlined {{
    font-family: 'Material Symbols Outlined'; font-weight: normal; font-style: normal; font-size: 22px;
    line-height: 1; letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap;
    word-wrap: normal; direction: ltr; -webkit-font-smoothing: antialiased; vertical-align: middle;
}}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {NAVY} 0%, {NAVY_2} 100%); }}
[data-testid="stSidebar"] * {{ color: #CBD9E6; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.10); }}
[data-testid="stSidebar"] button[kind="secondary"] {{
    background-color: transparent !important; border: none !important; color: #B7CADB !important;
    text-align: left !important; justify-content: flex-start !important; font-weight: 500 !important;
    box-shadow: none !important; min-height: 2.8rem !important; font-size: 0.97rem !important; border-radius: 10px !important;
}}
[data-testid="stSidebar"] button[kind="secondary"]:hover {{ background-color: rgba(255,255,255,0.08) !important; color: #FFFFFF !important; }}
[data-testid="stSidebar"] button[kind="primary"] {{
    background: linear-gradient(90deg, rgba(34,211,238,0.28), rgba(34,211,238,0.06)) !important;
    border: none !important; border-left: 3px solid {AQUA} !important; color: #FFFFFF !important;
    text-align: left !important; justify-content: flex-start !important; font-weight: 600 !important;
    box-shadow: none !important; min-height: 2.8rem !important; font-size: 0.97rem !important; border-radius: 10px !important;
}}
[data-testid="stSidebar"] button[kind="tertiary"] {{
    color: #B7CADB !important; border: 1px solid rgba(255,255,255,0.18) !important; justify-content: center !important;
    border-radius: 10px !important;
}}
.ls-user {{
    display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px;
    background: rgba(255,255,255,0.07); margin-bottom:12px;
}}
.ls-user-avatar {{
    width:34px; height:34px; border-radius:50%; background: linear-gradient(135deg, {AQUA}, {ACCENT});
    display:flex; align-items:center; justify-content:center; font-weight:800; color:{NAVY} !important; flex-shrink:0;
}}

/* ---------- Encabezado de página ---------- */
.ls-banner {{
    display:flex; align-items:center; gap:16px; padding:20px 26px; border-radius:18px; margin-bottom:22px;
    background: linear-gradient(120deg, {NAVY} 0%, {NAVY_2} 55%, {ACCENT} 130%);
    box-shadow: 0 8px 24px rgba(11,37,69,0.18); position:relative; overflow:hidden;
}}
.ls-banner::after {{
    content:""; position:absolute; right:-40px; top:-60px; width:220px; height:220px; border-radius:50%;
    background: radial-gradient(circle, rgba(34,211,238,0.35), rgba(34,211,238,0) 70%);
}}
.ls-banner-icon {{
    width:48px; height:48px; border-radius:14px; background: rgba(255,255,255,0.14);
    display:flex; align-items:center; justify-content:center; color:#FFFFFF; flex-shrink:0;
}}
.ls-banner-icon .material-symbols-outlined {{ font-size:26px; }}
.ls-banner-title {{ font-size:22px; font-weight:800; color:#FFFFFF; margin:0; line-height:1.2; }}
.ls-banner-sub {{ font-size:13.5px; color:#B9D6E8; margin:2px 0 0 0; }}
.ls-banner-fecha {{ margin-left:auto; text-align:right; color:#DFF3FA; font-size:13px; font-weight:600; z-index:1; }}
.ls-banner-fecha small {{ display:block; color:#9CC4DA; font-weight:500; }}

/* ---------- Tarjetas / KPI ---------- */
.ls-card {{
    background:#FFFFFF; border:1px solid #E3EDF3; border-radius:16px; padding:16px 18px;
    box-shadow: 0 2px 10px rgba(11,37,69,0.06); display:flex; align-items:center; gap:14px; margin-bottom:8px;
}}
.ls-kpi {{ border-left-width:5px; border-left-style:solid; transition: transform .15s ease, box-shadow .15s ease; }}
.ls-kpi:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(11,37,69,0.10); }}
.ls-card-icon {{
    width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center;
    font-size:20px; flex-shrink:0;
}}
.ls-card-label {{ font-size:11.5px; color:#64748B; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; }}
.ls-card-value {{ font-size:24px; font-weight:800; color:{NAVY}; line-height:1.15; }}

.ls-section-title {{
    font-size:15px; font-weight:800; color:{NAVY}; margin:30px 0 14px 0; padding-left:12px;
    border-left:4px solid {AQUA}; letter-spacing:0.01em;
}}

/* ---------- Estado vacío ---------- */
.ls-vacio {{
    display:flex; flex-direction:column; align-items:center; gap:6px; padding:30px 20px; border-radius:16px;
    background:#FFFFFF; border:2px dashed #CFE3EE; color:#64748B; text-align:center; margin:6px 0 12px 0;
}}
.ls-vacio .ls-vacio-icono {{
    width:56px; height:56px; border-radius:50%; background:#E6F5FA; color:{ACCENT};
    display:flex; align-items:center; justify-content:center;
}}
.ls-vacio .material-symbols-outlined {{ font-size:28px; }}
.ls-vacio b {{ color:{NAVY}; font-size:15px; }}

/* ---------- Formularios y botones ---------- */
.stButton > button, .stFormSubmitButton > button {{
    min-height: 3rem; font-size: 1.02rem; font-weight: 600; border-radius: 12px; transition: all .15s ease;
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {ACCENT} 0%, #0E7490 100%); border: none; color:#FFFFFF;
    box-shadow: 0 4px 12px rgba(8,145,178,0.30);
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
    box-shadow: 0 6px 16px rgba(8,145,178,0.42); transform: translateY(-1px); color:#FFFFFF;
}}
.stButton > button[kind="primary"]:disabled {{ background:#B8CDD8; box-shadow:none; }}
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {{ border-radius: 10px !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 2px solid #E3EDF3; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 700; font-size: 1rem; padding: 12px 20px; }}
.stTabs [aria-selected="true"] {{ color: {ACCENT}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {ACCENT}; height: 3px; }}
[data-testid="stAlert"] {{ border-radius: 12px; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid #E3EDF3; }}
[data-testid="stExpander"] {{ border-radius: 12px; background:#FFFFFF; }}

/* ---------- Badges y tablas HTML ---------- */
.ls-badge {{ display:inline-block; padding:3px 11px; border-radius:999px; font-size:12.5px; font-weight:700; white-space:nowrap; }}
table.ls-tabla {{
    width:100%; border-collapse:separate; border-spacing:0; font-size:14px; background:#FFFFFF;
    border:1px solid #E3EDF3; border-radius:14px; overflow:hidden; box-shadow:0 2px 10px rgba(11,37,69,0.05);
}}
table.ls-tabla th {{
    text-align:left; color:#FFFFFF; background:{NAVY}; font-size:11.5px; text-transform:uppercase;
    letter-spacing:0.05em; padding:11px 12px;
}}
table.ls-tabla td {{ padding:10px 12px; border-bottom:1px solid #EEF4F8; color:#1E293B; }}
table.ls-tabla tr:nth-child(even) td {{ background:#F6FAFC; }}
table.ls-tabla tr:last-child td {{ border-bottom:none; }}
</style>
""", unsafe_allow_html=True)


def icon_span(nombre: str) -> str:
    return f'<span class="material-symbols-outlined">{nombre}</span>'


def kpi_card(label, value, icon="insights", accent=ACCENT):
    st.markdown(
        f"""
        <div class="ls-card ls-kpi" style="border-left-color:{accent};">
            <div class="ls-card-icon" style="background-color:{accent}1A; color:{accent};">
                {icon_span(icon)}
            </div>
            <div>
                <div class="ls-card-label">{label}</div>
                <div class="ls-card-value">{value}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(texto: str):
    st.markdown(f'<div class="ls-section-title">{texto}</div>', unsafe_allow_html=True)


def estado_vacio(titulo: str, detalle: str = "", icono: str = "inbox"):
    st.markdown(
        f"""
        <div class="ls-vacio">
            <div class="ls-vacio-icono">{icon_span(icono)}</div>
            <b>{titulo}</b>
            <span>{detalle}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def encabezado(titulo: str, subtitulo: str, icono: str, fecha_txt: str, dia_txt: str):
    st.markdown(
        f"""
        <div class="ls-banner">
            <div class="ls-banner-icon">{icon_span(icono)}</div>
            <div style="z-index:1;">
                <p class="ls-banner-title">{titulo}</p>
                <p class="ls-banner-sub">{subtitulo}</p>
            </div>
            <div class="ls-banner-fecha">{dia_txt}<small>{fecha_txt}</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )




# ---------------------------------------------------------------------------
# Utilidades de interfaz
# ---------------------------------------------------------------------------
def soles(x) -> str:
    return f"S/ {x:,.2f}"


def badge(texto: str, color: str) -> str:
    return f'<span class="ls-badge" style="background-color:{color}1A;color:{color};">{escape(texto)}</span>'


BADGE_PAGO = {
    "sin_cobrar": (GRAY, "sin cobrar"),
    "incompleto": (WARNING, "incompleto"),
    "completo": (SUCCESS, "completo"),
}
BADGE_INCIDENCIA = {"abierta": DANGER, "en proceso": WARNING, "resuelta": SUCCESS}


def badge_pago(estado: str) -> str:
    color, texto = BADGE_PAGO[estado]
    return badge(texto, color)


def tabla(df: pd.DataFrame, columnas_html=()):
    """Tabla con badges. Todo lo que no sea una columna de badges se escapa (evita inyectar HTML)."""
    d = df.copy()
    for c in d.columns:
        if c not in columnas_html:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else escape(str(v)))
    st.markdown(d.to_html(escape=False, index=False, classes="ls-tabla", border=0), unsafe_allow_html=True)


def grafico(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")


def flash(tipo: str, texto: str):
    """Mensaje que sobrevive al st.rerun() que dispara cada callback."""
    st.session_state["flash"] = (tipo, texto)


def mostrar_flash():
    mensaje = st.session_state.pop("flash", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])


def es_dueno() -> bool:
    return st.session_state.get("rol") == "dueno"


# ---------------------------------------------------------------------------
# Login: usuarios y claves salen de st.secrets (.streamlit/secrets.toml, fuera del repo)
# ---------------------------------------------------------------------------
def usuarios_configurados() -> dict:
    try:
        return {u: dict(datos) for u, datos in st.secrets["usuarios"].items()}
    except Exception:
        return {}


def pantalla_login():
    usuarios = usuarios_configurados()
    # Solo en el login: foto de fondo a pantalla completa y la tarjeta del formulario al centro
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(rgba(11,37,69,0.15), rgba(11,37,69,0.15)),
                        url("{_datauri('fondo_login.jpg', 'image/jpeg')}") center / cover no-repeat fixed;
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        .block-container {{ padding-top: 6vh; }}
        .st-key-login_card {{
            background: #FFFFFF; border-radius: 22px; padding: 32px 34px 24px 34px;
            box-shadow: 0 24px 60px rgba(5,20,45,0.50);
        }}
        [data-testid="stForm"] {{ border: none; padding: 0; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, centro, _ = st.columns([1, 1, 1])
    with centro:
        with st.container(key="login_card"):
            st.markdown(
                f"""
                <div style="display:flex;flex-direction:column;align-items:center;text-align:center;gap:6px;margin:6px 0 14px 0;">
                    {logo_img(84)}
                    <div style="font-size:28px;font-weight:800;color:{NAVY};line-height:1.1;margin-top:6px;">LavaSmart</div>
                    <div style="font-size:13.5px;color:{GRAY};">Gestión inteligente para AquaBrillo</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not usuarios:
                st.error("Faltan los usuarios. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y complétalo.")
                return
            with st.form("form_login"):
                usuario = st.text_input("Usuario", placeholder="operador o dueno")
                clave = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Ingresar", width="stretch", type="primary"):
                    datos = usuarios.get(usuario)
                    esperada = str((datos or {}).get("clave", ""))
                    if datos and esperada and hmac.compare_digest(clave.encode(), esperada.encode()) and datos.get("rol") in ROLES:
                        st.session_state.autenticado = True
                        st.session_state.usuario = usuario
                        st.session_state.nombre = str(datos.get("nombre") or usuario.capitalize())
                        st.session_state.rol = datos["rol"]
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos")
            st.caption("Prototipo de validación · los datos mostrados son simulados.")


if not st.session_state.get("autenticado"):
    pantalla_login()
    st.stop()

paginas = PAGINAS_DUENO if es_dueno() else PAGINAS_OPERADOR
if st.session_state.get("pagina_activa") not in [p for p, _ in paginas]:
    st.session_state.pagina_activa = paginas[0][0]

# ---------------------------------------------------------------------------
# Sidebar: las pestañas dependen del rol
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;padding:6px 0 20px 0;">
            {logo_img(42)}
            <div>
                <div style="font-size:18px;font-weight:800;color:#FFFFFF;line-height:1.1;">LavaSmart</div>
                <div style="font-size:11.5px;color:#7FA3BD;">AquaBrillo</div>
            </div>
        </div>
        <div class="ls-user">
            <div class="ls-user-avatar">{escape(st.session_state.nombre[:1].upper())}</div>
            <div>
                <div style="font-size:14px;color:#FFFFFF;font-weight:700;line-height:1.2;">{escape(st.session_state.nombre)}</div>
                <div style="font-size:12px;color:#7FA3BD;">Rol: {ROLES[st.session_state.rol]}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Cerrar sesión", icon=":material/logout:", width="stretch", type="tertiary"):
        for k in ("autenticado", "usuario", "nombre", "rol", "pagina_activa"):
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("<hr style='margin:16px 0;'>", unsafe_allow_html=True)

    for nombre, icono in paginas:
        activo = st.session_state.pagina_activa == nombre
        if st.button(
            nombre,
            icon=f":material/{icono}:",
            key=f"nav_{nombre}",
            width="stretch",
            type="primary" if activo else "secondary",
        ):
            st.session_state.pagina_activa = nombre
            st.rerun()

pagina = st.session_state.pagina_activa

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
SUBTITULOS = {
    "Registrar servicio": "Recibe el auto al ingresar y cóbralo al entregarlo",
    "Asistencia": "Quién llegó, a qué hora y qué porcentaje le toca",
    "Incidencias": "Reclamos y problemas, siempre ligados a la placa",
    "Caja del día": "Lo cobrado hoy en efectivo y Yape",
    "Liquidación": "Lo que se devenga cada día y lo que ya se pagó",
    "Dashboard": "El pulso del negocio de un vistazo",
    "Tarifas y configuración": "Precios y reglas de puntualidad",
    "Personal": "Modalidad de pago y altas del equipo",
    "Predicción de demanda": "Cuántos autos esperar la próxima semana",
    "Segmentación de clientes": "Quiénes son tus clientes más valiosos",
}
_f = date.fromisoformat(store.hoy_lima())
encabezado(
    pagina,
    SUBTITULOS.get(pagina, ""),
    dict(paginas)[pagina],
    f"{_f.day} de {MESES[_f.month - 1]} de {_f.year}",
    DIAS[_f.weekday()],
)
mostrar_flash()

hoy = store.hoy_lima()

# ---------------------------------------------------------------------------
# Registrar servicio: dos momentos (ingreso sin cobro → entrega con cobro)
# ---------------------------------------------------------------------------
if pagina == "Registrar servicio":
    tab_ingreso, tab_entrega = st.tabs(["1 · Ingreso del auto", "2 · Entrega y cobro"])

    # ----- Momento 1: ingreso. Nunca se cobra aquí.
    with tab_ingreso:
        disponibles = store.lavadores_disponibles(hoy)
        if disponibles.empty:
            st.warning("Nadie tiene asistencia autorizada hoy. Primero se marca entrada en **Asistencia**, después se reciben autos.")

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Placa del vehículo", placeholder="ABC123", key="ing_placa")
            st.selectbox("Tipo de vehículo", TIPOS_VEHICULO, key="ing_vehiculo")
        with c2:
            st.multiselect("Servicios (se suman)", TIPOS_LAVADO, key="ing_servicios")
            st.selectbox("Lavador (uno por vehículo)", disponibles["trabajador"].tolist(), key="ing_lavador")

        with st.expander("Datos del cliente (opcionales)"):
            st.text_input("Nombre", key="ing_nombre")
            st.text_input("Teléfono", key="ing_telefono")

        precios = store.precio_servicios(st.session_state.ing_vehiculo, st.session_state.ing_servicios)
        total_ingreso = sum(precios.values())
        if precios:
            detalle = " + ".join(f"{s} {soles(p)}" for s, p in precios.items())
            st.info(f"**Total a cobrar al entregar: {soles(total_ingreso)}** — {detalle}")
        else:
            st.info("Elige uno o más servicios para ver el precio.")

        def _ingresar():
            s = st.session_state
            try:
                id_lavado = store.registrar_ingreso(
                    s.ing_placa, s.ing_vehiculo, s.ing_servicios, s.ing_lavador, s.ing_nombre, s.ing_telefono
                )
            except ReglaDeNegocio as e:
                flash("error", str(e))
                return
            flash("success", f"Ingreso #{id_lavado} registrado: {store.normalizar_placa(s.ing_placa)}. Se cobra al entregar.")
            for k in ("ing_placa", "ing_servicios", "ing_nombre", "ing_telefono"):
                s[k] = "" if k != "ing_servicios" else []

        st.button("Registrar ingreso", type="primary", width="stretch", on_click=_ingresar, disabled=disponibles.empty)

    # ----- Momento 2: entrega. Aquí se cobra.
    with tab_entrega:
        lav = store.v_lavado()
        en_proceso = lav[lav["estado"] == "en proceso"].sort_values("id_lavado")
        if en_proceso.empty:
            estado_vacio("No hay autos en proceso", "Cuando registres un ingreso, aparecerá aquí para entregarlo y cobrarlo.", "local_car_wash")
        else:
            etiquetas = {
                int(r["id_lavado"]): f"{r['placa']} · {r['tipo_vehiculo']} · {r['trabajador']} · ingresó {r['hora_ingreso']}"
                for _, r in en_proceso.iterrows()
            }
            id_sel = st.selectbox("Auto a entregar", list(etiquetas), format_func=etiquetas.get, key="ent_id")
            fila = en_proceso[en_proceso["id_lavado"] == id_sel].iloc[0]
            servicios = store.leer("detalle_lavado")
            servicios = servicios[servicios["id_lavado"] == id_sel]
            st.write("**Servicios:** " + ", ".join(f"{r.tipo_lavado} ({soles(r.precio_cobrado)})" for r in servicios.itertuples()))
            st.markdown(f"### Total: {soles(fila['total'])}")

            c1, c2 = st.columns(2)
            with c1:
                monto = st.number_input(
                    "Monto cobrado (S/)", min_value=0.0, max_value=float(fila["total"]), value=float(fila["total"]),
                    step=1.0, key=f"ent_monto_{id_sel}",
                )
            with c2:
                metodo = st.radio("Medio de pago", MEDIOS_PAGO, horizontal=True, key=f"ent_metodo_{id_sel}")
            if monto < fila["total"]:
                st.warning(
                    f"Pago incompleto: saldo {soles(fila['total'] - monto)}. El cliente no vuelve a pagar; "
                    "el saldo solo se anota para calcular el destajo."
                )

            def _entregar():
                try:
                    store.registrar_entrega(id_sel, monto, metodo)
                except ReglaDeNegocio as e:
                    flash("error", str(e))
                    return
                flash("success", f"Entregado {fila['placa']}: {soles(monto)} en {metodo}.")

            st.button("Entregar y cobrar", type="primary", width="stretch", on_click=_entregar)

            section_title("Autos en proceso")
            vista = en_proceso.assign(estado_pago=en_proceso["estado_pago"].map(badge_pago))
            tabla(
                vista[["placa", "tipo_vehiculo", "trabajador", "hora_ingreso", "total", "estado_pago"]]
                .rename(columns={"estado_pago": "pago"})
                .assign(total=lambda d: d["total"].map(soles)),
                columnas_html=("pago",),
            )

# ---------------------------------------------------------------------------
# Asistencia: alimenta el destajo y bloquea asignar autos sin marcar
# ---------------------------------------------------------------------------
elif pagina == "Asistencia":
    st.subheader("Asistencia del personal")
    cfg = store.configuracion()
    st.caption(
        f"Hora de referencia {cfg['hora_referencia']} + {cfg['tolerancia_minutos']} min de tolerancia. "
        f"Destajo: {cfg['pct_destajo_puntual']:.0f} % si marca a tiempo, {cfg['pct_destajo_tarde']:.0f} % si llega después. "
        "El porcentaje se fija con la marcación y dura todo el día."
    )

    activos = store.trabajadores_activos()
    with st.form("form_asistencia"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_asis = st.date_input("Fecha", value=date.fromisoformat(hoy), max_value=date.fromisoformat(hoy))
            trabajador_asis = st.selectbox("Trabajador", activos["trabajador"].tolist())
        with c2:
            estado_asis = st.radio("Estado", ["Presente", "Falta"], horizontal=True)
        with c3:
            hora_entrada = st.time_input("Hora de entrada", value=store.ahora_lima().time().replace(second=0, microsecond=0))
        if st.form_submit_button("Registrar asistencia", type="primary", width="stretch"):
            try:
                aviso = store.marcar_asistencia(
                    trabajador_asis, fecha_asis.isoformat(), estado_asis, hora_entrada.strftime("%H:%M")
                )
                st.success(f"Asistencia registrada: {trabajador_asis} — {estado_asis}")
                if aviso:
                    st.warning(aviso)
            except ReglaDeNegocio as e:
                st.error(str(e))

    section_title("Hoy")
    asis = store.leer("asistencia")
    filas = []
    for _, t in activos.iterrows():
        a = asis[(asis["fecha"] == hoy) & (asis["trabajador"] == t["trabajador"])]
        if a.empty:
            filas.append({"trabajador": t["trabajador"], "modalidad": t["modalidad"], "estado": badge("sin marcar", GRAY),
                          "entrada": "", "puntualidad": "", "puede trabajar": ""})
            continue
        r = a.iloc[0]
        if r["estado"] == "Falta":
            filas.append({"trabajador": t["trabajador"], "modalidad": t["modalidad"], "estado": badge("falta", DANGER),
                          "entrada": "", "puntualidad": "", "puede trabajar": badge("no", GRAY)})
            continue
        puntual = store.es_puntual(r)
        pct = ""
        if t["modalidad"] == "Destajo":
            pct = f" · {cfg['pct_destajo_puntual' if puntual else 'pct_destajo_tarde']:.0f} %"
        filas.append({
            "trabajador": t["trabajador"], "modalidad": t["modalidad"], "estado": badge("presente", SUCCESS),
            "entrada": r["hora_entrada"],
            "puntualidad": badge("puntual" if puntual else "tarde", SUCCESS if puntual else WARNING) + escape(pct),
            "puede trabajar": badge("sí", SUCCESS) if r["autorizado"] else badge("espera al dueño", DANGER),
        })
    tabla(pd.DataFrame(filas), columnas_html=("estado", "puntualidad", "puede trabajar"))

    # Decisión del dueño sobre el sueldo fijo que llega tarde (descuento = monto a mano, no fórmula)
    if es_dueno():
        section_title("Sueldo fijo con tardanza — decide el dueño")
        fijos = activos.loc[activos["modalidad"] == "Fijo", "trabajador"]
        recientes = asis[
            asis["trabajador"].isin(fijos) & (asis["estado"] == "Presente") & (asis["fecha"] >= (date.fromisoformat(hoy) - timedelta(days=7)).isoformat())
        ]
        tardios = recientes[[not store.es_puntual(r) for _, r in recientes.iterrows()]].sort_values("fecha", ascending=False)
        if tardios.empty:
            estado_vacio("Sin tardanzas de fijos", "Nadie con sueldo fijo llegó tarde en los últimos 7 días.", "schedule")
        else:
            claves = [(r["fecha"], r["trabajador"]) for _, r in tardios.iterrows()]
            sel = st.selectbox("Tardanza", claves, format_func=lambda k: f"{k[0]} · {k[1]}")
            r = tardios[(tardios["fecha"] == sel[0]) & (tardios["trabajador"] == sel[1])].iloc[0]
            st.caption(f"Entró a las {r['hora_entrada']} (referencia {r['hora_referencia']} + {r['tolerancia_minutos']} min).")
            c1, c2 = st.columns(2)
            with c1:
                deja = st.checkbox("Lo dejo trabajar ese día", value=bool(r["autorizado"]), key=f"dec_ok_{sel}")
            with c2:
                desc = st.number_input("Descuento (S/)", min_value=0.0, value=float(r["descuento"]), step=1.0, key=f"dec_desc_{sel}", disabled=not deja)
            if st.button("Guardar decisión", type="primary"):
                try:
                    store.decidir_fijo_tardio(sel[1], sel[0], deja, desc if deja else 0.0)
                    st.success("Decisión guardada.")
                except ReglaDeNegocio as e:
                    st.error(str(e))

    section_title("Historial reciente")
    st.dataframe(
        asis.sort_values(["fecha", "trabajador"], ascending=False).head(20)[
            ["fecha", "trabajador", "estado", "hora_entrada", "autorizado", "descuento"]
        ],
        width="stretch",
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Incidencias: siempre con placa; con lavado si se identifica
# ---------------------------------------------------------------------------
elif pagina == "Incidencias":
    st.subheader("Registrar incidencia")
    lav = store.v_lavado()

    c1, c2 = st.columns(2)
    with c1:
        placa_inc = st.text_input("Placa", placeholder="ABC123", key="inc_placa")
        tipo_inc = st.selectbox("Tipo de incidencia", TIPOS_INCIDENCIA, key="inc_tipo")
    with c2:
        try:
            placa_norm = store.normalizar_placa(placa_inc) if placa_inc else ""
        except ReglaDeNegocio:
            placa_norm = ""
        previos = lav[lav["placa"] == placa_norm].sort_values("id_lavado", ascending=False).head(10)
        opciones = [None] + previos["id_lavado"].astype(int).tolist()
        etiquetas = {int(r["id_lavado"]): f"#{int(r['id_lavado'])} · {r['fecha_ingreso']} · {r['trabajador']}" for _, r in previos.iterrows()}
        id_lavado_inc = st.selectbox(
            "Lavado asociado",
            opciones,
            format_func=lambda i: "Sin lavado asociado (reclamo tardío)" if i is None else etiquetas[i],
            key="inc_lavado",
            help="Escribe la placa para ver sus últimos lavados.",
        )
    descripcion_inc = st.text_area("Descripción", key="inc_desc")

    def _registrar_incidencia():
        s = st.session_state
        try:
            store.registrar_incidencia(s.inc_placa, s.inc_lavado if s.inc_lavado is not None else pd.NA, s.inc_tipo, s.inc_desc)
        except ReglaDeNegocio as e:
            flash("error", str(e))
            return
        flash("success", "Incidencia registrada como abierta.")
        s.inc_placa, s.inc_desc = "", ""

    st.button("Registrar incidencia", type="primary", width="stretch", on_click=_registrar_incidencia)

    inc = store.leer("incidencias")
    section_title("Incidencias sin resolver")
    pendientes = inc[inc["estado"] != "resuelta"].sort_values("id_incidencia", ascending=False)
    if pendientes.empty:
        estado_vacio("Todo en orden", "No hay incidencias abiertas.", "verified")
    else:
        vista = pendientes.assign(
            estado=pendientes["estado"].map(lambda e: badge(e, BADGE_INCIDENCIA[e])),
            lavado=pendientes["id_lavado"].map(lambda i: "sin lavado" if pd.isna(i) else f"#{int(i)}"),
        )
        tabla(vista[["id_incidencia", "fecha", "placa", "lavado", "trabajador", "tipo_incidencia", "descripcion", "estado"]], columnas_html=("estado",))

        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            id_cambio = st.selectbox("Cambiar estado de la incidencia", pendientes["id_incidencia"].astype(int).tolist(), format_func=lambda i: f"#{i}")
        with c2:
            nuevo = st.selectbox("Nuevo estado", ESTADOS_INCIDENCIA, index=1)
        with c3:
            st.write("")
            st.write("")
            if st.button("Actualizar"):
                store.cambiar_estado_incidencia(id_cambio, nuevo)
                st.rerun()

    section_title("Incidencias por tipo")
    if not inc.empty:
        por_tipo = inc.groupby("tipo_incidencia").size().reset_index(name="cantidad")
        grafico(px.bar(por_tipo, x="tipo_incidencia", y="cantidad", color_discrete_sequence=[ACCENT]))

# ---------------------------------------------------------------------------
# Caja del día: agrupada por fecha de ENTREGA (hora de Lima)
# ---------------------------------------------------------------------------
elif pagina == "Caja del día":
    st.subheader("Caja del día")
    fecha_caja = st.date_input("Día", value=date.fromisoformat(hoy), max_value=date.fromisoformat(hoy)).isoformat()

    caja = store.caja_dia(fecha_caja)
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Efectivo", soles(caja.loc[caja["medio"] == "efectivo", "cobrado"].sum()), "payments", SUCCESS)
    with c2:
        kpi_card("Yape", soles(caja.loc[caja["medio"] == "Yape", "cobrado"].sum()), "smartphone", ACCENT)
    with c3:
        kpi_card("Total cobrado", soles(caja["cobrado"].sum()), "point_of_sale", ACCENT)

    lav = store.v_lavado()
    dia = lav[(lav["estado"] == "entregado") & (lav["fecha_entrega"] == fecha_caja)].sort_values("hora_entrega")
    section_title("Autos entregados")
    if dia.empty:
        estado_vacio("Sin entregas ese día", "Aún no se cobró ningún auto en esta fecha.", "point_of_sale")
    else:
        vista = dia.assign(
            pago=dia["estado_pago"].map(badge_pago),
            total=dia["total"].map(soles),
            cobrado=dia["monto_cobrado"].map(soles),
            saldo=dia["saldo"].map(soles),
        )
        tabla(vista[["hora_entrega", "placa", "trabajador", "metodo_pago", "total", "cobrado", "saldo", "pago"]], columnas_html=("pago",))
        st.caption("El saldo de un pago incompleto no se cobra después: solo sirve para calcular el destajo.")

# ---------------------------------------------------------------------------
# Liquidación (dueño): devengar no es pagar
# ---------------------------------------------------------------------------
elif pagina == "Liquidación":
    st.subheader("Liquidación del personal")
    st.caption(
        "Destajo: % de lo **cobrado** (el % congelado en cada lavado). Sueldo fijo: monto diario menos el descuento que anotó el dueño. "
        "El devengado se calcula todos los días; el dinero sale cuando se entrega y se registra el pago. "
        "Fijos cobran semanal; destajo, diario o semanal según cada trabajador."
    )
    lunes = date.fromisoformat(hoy) - timedelta(days=date.fromisoformat(hoy).weekday())
    c1, c2 = st.columns(2)
    with c1:
        desde = st.date_input("Desde", value=lunes).isoformat()
    with c2:
        hasta = st.date_input("Hasta", value=date.fromisoformat(hoy)).isoformat()

    activos = store.trabajadores_activos()
    dev = store.devengado(desde, hasta)
    resumen = resumen_por_trabajador(dev, activos)

    st.dataframe(
        resumen.assign(
            cobrado=resumen["cobrado"].map(soles), devengado=resumen["devengado"].map(soles),
            pagado=resumen["pagado"].map(soles), pendiente=resumen["pendiente"].map(soles),
        ),
        width="stretch",
        hide_index=True,
    )
    st.success(f"Pendiente de pago en el periodo: {soles(resumen['pendiente'].sum())}")
    grafico(px.bar(resumen, x="trabajador", y="devengado", color="modalidad", text="devengado",
                   color_discrete_map={"Fijo": GRAY, "Destajo": ACCENT}))

    with st.expander("Detalle diario"):
        st.dataframe(dev, width="stretch", hide_index=True)

    section_title("Registrar pago")
    c1, c2 = st.columns([2, 1])
    with c1:
        quien = st.selectbox("Trabajador", activos["trabajador"].tolist())
    pendiente = float(resumen.loc[resumen["trabajador"] == quien, "pendiente"].iloc[0])
    with c2:
        st.write("")
        st.write("")
        if st.button(f"Pagar {soles(pendiente)}", type="primary", width="stretch", disabled=pendiente <= 0):
            try:
                monto = store.registrar_pago(quien, desde, hasta)
                st.success(f"Pago de {soles(monto)} a {quien} registrado. El periodo {desde} → {hasta} queda cerrado.")
                st.rerun()
            except ReglaDeNegocio as e:
                st.error(str(e))

    section_title("Liquidaciones cerradas (no se modifican)")
    cerradas = store.leer("liquidaciones").sort_values("id_liquidacion", ascending=False)
    st.dataframe(cerradas.assign(monto=cerradas["monto"].map(soles)), width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Dashboard (dueño)
# ---------------------------------------------------------------------------
elif pagina == "Dashboard":
    lav = store.v_lavado()
    inc = store.leer("incidencias")
    asis = store.leer("asistencia")
    semana_desde = (date.fromisoformat(hoy) - timedelta(days=6)).isoformat()

    entregados = lav[lav["estado"] == "entregado"]
    cobrado_hoy = store.caja_dia(hoy)["cobrado"].sum()
    cobrado_semana = entregados.loc[entregados["fecha_entrega"] >= semana_desde, "monto_cobrado"].sum()
    autos_semana = (lav["fecha_ingreso"] >= semana_desde).sum()
    en_proceso = (lav["estado"] == "en proceso").sum()
    abiertas = (inc["estado"] != "resuelta").sum()
    faltas_hoy = ((asis["fecha"] == hoy) & (asis["estado"] == "Falta")).sum()
    saldos_hoy = ((lav["fecha_entrega"] == hoy) & (lav["estado_pago"] == "incompleto")).sum()

    section_title("Hoy")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Cobrado hoy", soles(cobrado_hoy), "payments", SUCCESS)
    with c2:
        kpi_card("Autos en proceso", int(en_proceso), "local_car_wash", ACCENT)
    with c3:
        kpi_card("Pagos incompletos hoy", int(saldos_hoy), "money_off", WARNING if saldos_hoy else GRAY)
    with c4:
        kpi_card("Faltas hoy", int(faltas_hoy), "event_busy", DANGER if faltas_hoy else GRAY)

    section_title("Últimos 7 días")
    c5, c6, c7 = st.columns(3)
    with c5:
        kpi_card("Autos recibidos", int(autos_semana), "directions_car", ACCENT)
    with c6:
        kpi_card("Cobrado", soles(cobrado_semana), "payments", ACCENT)
    with c7:
        kpi_card("Incidencias sin resolver", int(abiertas), "warning", DANGER if abiertas else GRAY)

    section_title("Cobrado por medio de pago (últimos 7 días)")
    por_medio = (
        entregados[entregados["fecha_entrega"] >= semana_desde]
        .groupby(["fecha_entrega", "metodo_pago"])["monto_cobrado"].sum().reset_index()
    )
    if por_medio.empty:
        st.info("Sin cobros en los últimos 7 días.")
    else:
        grafico(px.bar(por_medio, x="fecha_entrega", y="monto_cobrado", color="metodo_pago", barmode="stack",
                       color_discrete_map={"efectivo": ACCENT, "Yape": "#7C3AED"},
                       labels={"fecha_entrega": "Día de entrega", "monto_cobrado": "Cobrado (S/)", "metodo_pago": "Medio"}))

    section_title("Autos recibidos por día")
    por_dia = lav.groupby("fecha_ingreso").size().reset_index(name="autos")
    grafico(px.line(por_dia, x="fecha_ingreso", y="autos", markers=True, color_discrete_sequence=[ACCENT]))

    section_title("Pronóstico y clientes (ilustrativo)")
    st.caption(AVISO_SIMULADO)

    @st.cache_data
    def _prediccion(fechas: pd.DataFrame):
        modelo, _ = entrenar_modelo_demanda(fechas)
        return predecir_proxima_semana(modelo)

    pred = _prediccion(lav[["fecha_ingreso"]])
    manana = DIAS[(date.fromisoformat(hoy).weekday() + 1) % 7]
    autos_manana = pred.loc[pred["dia_semana"] == manana, "prediccion_autos"].iloc[0]
    por_placa = entregados.groupby("placa").size()
    c8, c9 = st.columns(2)
    with c8:
        kpi_card("Autos esperados mañana", f"{autos_manana:.0f}", "trending_up", ACCENT)
    with c9:
        kpi_card("Clientes recurrentes", f"{int((por_placa >= 2).sum())} de {len(por_placa)}", "groups", ACCENT)
        st.caption("Se identifican por placa (seudonimización: la placa sigue siendo dato personal).")

    section_title("Últimos lavados")
    ultimos = lav.sort_values("id_lavado", ascending=False).head(15)
    tabla(
        ultimos.assign(
            pago=ultimos["estado_pago"].map(badge_pago),
            total=ultimos["total"].map(soles),
            cobrado=ultimos["monto_cobrado"].map(soles),
        )[["fecha_ingreso", "placa", "tipo_vehiculo", "trabajador", "estado", "total", "cobrado", "pago"]],
        columnas_html=("pago",),
    )

# ---------------------------------------------------------------------------
# Tarifas y configuración (dueño)
# ---------------------------------------------------------------------------
elif pagina == "Tarifas y configuración":
    st.subheader("Tarifas")
    st.caption(
        "Precio = tipo de vehículo × tipo de lavado. Son tarifas de ejemplo: reemplázalas por las reales. "
        "Cambiarlas **no** toca lo ya cobrado: cada lavado guarda el precio de ese día."
    )
    editada = st.data_editor(
        store.matriz_tarifas(),
        column_config={v: st.column_config.NumberColumn(v, min_value=0.0, step=1.0, format="S/ %.2f", required=True) for v in TIPOS_VEHICULO},
        width="stretch",
        key="editor_tarifas",
    )
    if st.button("Guardar tarifas", type="primary"):
        store.guardar_matriz_tarifas(editada)
        st.success("Tarifas guardadas. Valen para los ingresos nuevos.")

    st.subheader("Asistencia y destajo")
    cfg = store.configuracion()
    with st.form("form_config"):
        c1, c2 = st.columns(2)
        with c1:
            hora_ref = st.time_input("Hora de referencia", value=datetime.strptime(cfg["hora_referencia"], "%H:%M").time())
            tolerancia = st.number_input("Tolerancia (minutos)", min_value=0, max_value=60, value=cfg["tolerancia_minutos"], step=1)
        with c2:
            pct_ok = st.number_input("% destajo si llega a tiempo", min_value=0.0, max_value=100.0, value=cfg["pct_destajo_puntual"], step=1.0)
            pct_tarde = st.number_input("% destajo si llega tarde", min_value=0.0, max_value=100.0, value=cfg["pct_destajo_tarde"], step=1.0)
        if st.form_submit_button("Guardar configuración", type="primary"):
            store.guardar_configuracion({
                "hora_referencia": hora_ref.strftime("%H:%M"), "tolerancia_minutos": int(tolerancia),
                "pct_destajo_puntual": pct_ok, "pct_destajo_tarde": pct_tarde,
            })
            st.success("Configuración guardada. Vale desde las próximas marcaciones; las anteriores conservan lo suyo.")

# ---------------------------------------------------------------------------
# Personal (dueño)
# ---------------------------------------------------------------------------
elif pagina == "Personal":
    st.subheader("Personal")
    st.caption("Sin borrados: para dar de baja a alguien se desmarca «activo». Los fijos cobran semanal; los de destajo, diario o semanal.")
    trab = store.leer("trabajadores")
    editado = st.data_editor(
        trab,
        disabled=["trabajador", "modalidad"],
        column_config={
            "sueldo_diario": st.column_config.NumberColumn("sueldo diario (S/)", min_value=0.0, step=1.0, format="S/ %.2f"),
            "frecuencia_pago": st.column_config.SelectboxColumn("frecuencia de pago", options=["diario", "semanal"], required=True),
            "activo": st.column_config.CheckboxColumn("activo"),
        },
        hide_index=True,
        width="stretch",
        key="editor_personal",
    )
    if st.button("Guardar cambios", type="primary"):
        fijos = editado["modalidad"] == "Fijo"
        if (editado.loc[fijos, "frecuencia_pago"] != "semanal").any():
            st.error("Los trabajadores de sueldo fijo cobran siempre semanal.")
        elif (editado.loc[fijos & editado["activo"], "sueldo_diario"].fillna(0) <= 0).any():
            st.error("Un trabajador de sueldo fijo activo necesita un sueldo diario mayor que 0.")
        else:
            store.guardar("trabajadores", editado)
            st.success("Cambios guardados.")

    section_title("Agregar trabajador")
    with st.form("form_trabajador", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            nombre = st.text_input("Nombre")
        with c2:
            modalidad = st.selectbox("Modalidad", ["Destajo", "Fijo"])
        with c3:
            sueldo = st.number_input("Sueldo diario (solo fijos)", min_value=0.0, step=1.0)
        with c4:
            frecuencia = st.selectbox("Frecuencia de pago (destajo)", ["diario", "semanal"])
        if st.form_submit_button("Agregar", type="primary"):
            nombre = nombre.strip()
            if not nombre:
                st.error("Escribe el nombre.")
            elif nombre in trab["trabajador"].values:
                st.error("Ya existe un trabajador con ese nombre.")
            elif modalidad == "Fijo" and sueldo <= 0:
                st.error("Un fijo necesita sueldo diario mayor que 0.")
            else:
                store.agregar("trabajadores", {
                    "trabajador": nombre, "modalidad": modalidad, "sueldo_diario": sueldo if modalidad == "Fijo" else 0,
                    "frecuencia_pago": "semanal" if modalidad == "Fijo" else frecuencia, "activo": True,
                })
                st.success(f"{nombre} agregado.")
                st.rerun()

# ---------------------------------------------------------------------------
# Predicción de demanda (dueño)
# ---------------------------------------------------------------------------
elif pagina == "Predicción de demanda":
    st.subheader("Predicción de demanda (próxima semana)")
    #st.warning(AVISO_SIMULADO)
    lav = store.leer("lavados")
    dias_feriados = st.multiselect("¿Algún día será feriado?", DIAS)

    if st.button("Entrenar modelo y predecir", type="primary"):
        modelo, _ = entrenar_modelo_demanda(lav)
        prediccion = predecir_proxima_semana(modelo, dias_feriados)
        section_title("Vehículos estimados por día (ilustrativo)")
        grafico(px.bar(prediccion, x="dia_semana", y="prediccion_autos", text="prediccion_autos", color_discrete_sequence=[ACCENT]))
        st.success(f"Total estimado para la semana: {prediccion['prediccion_autos'].sum():.0f} vehículos")
        st.caption("Modelo: RandomForestRegressor sobre autos recibidos por día (día de la semana y feriado).")

# ---------------------------------------------------------------------------
# Segmentación de clientes (dueño)
# ---------------------------------------------------------------------------
elif pagina == "Segmentación de clientes":
    st.subheader("Segmentación de clientes (K-Means)")
    st.warning(AVISO_SIMULADO)
    st.caption("La placa identifica al cliente. Es seudonimización, no anonimización: sigue siendo dato personal (Ley N.° 29733).")
    lav = store.leer("lavados")
    entregados = lav[lav["estado"] == "entregado"]

    if st.button("Ejecutar segmentación", type="primary"):
        if entregados["placa"].nunique() < 3:
            st.error("Se necesitan al menos 3 clientes con lavados entregados.")
        else:
            rfm = segmentar_clientes(entregados)
            grafico(px.scatter(
                rfm, x="recencia", y="frecuencia", size="monto", color="segmento", hover_data=["placa", "monto"],
                labels={"recencia": "Días desde la última visita", "frecuencia": "N° de visitas"},
                color_discrete_map={"Cliente VIP": "#163B52", "Cliente frecuente": ACCENT, "Cliente ocasional": "#94A3B8"},
            ))
            section_title("Resumen por segmento")
            resumen = (
                rfm.groupby("segmento")
                .agg(clientes=("placa", "count"), gasto_promedio=("monto", "mean"), frecuencia_promedio=("frecuencia", "mean"))
                .reset_index()
            )
            st.dataframe(resumen, width="stretch", hide_index=True)
            section_title("Detalle por cliente")
            st.dataframe(rfm.sort_values("monto", ascending=False), width="stretch", hide_index=True)
