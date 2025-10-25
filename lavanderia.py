import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
from pytz import timezone
import time
import pandas as pd
from io import BytesIO
from collections import Counter

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Lavandería", layout="wide")

# --- CONEXIÓN A SUPABASE ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PRODUCTOS ---
lavadoras_secadoras = {
    "Lavadora 16 kg": 140,
    "Lavadora 9 kg": 85,
    "Lavadora 4 kg": 50,
    "Secadora 9 kg (15 minutos)": 30,
    "Secadora 9 kg (30 minutos)": 60,
    "Secado": 80,
}
detergentes = {
    "1 medida de jabón": 10,
    "1 medida de suavizante": 10,
    "1 medida de desmugrante": 15
}
bolsas = {
    "1 bolsa chica": 5,
    "1 bolsa mediana": 6,
    "1 bolsa grande": 7
}

# --- INICIALIZAR SESSION_STATE ---
defaults = {
    'seleccionados': {},
    'nombre': "",
    'apellido': "",
    'vendedor': "",
    'dinero': 0.0,
    'total': 0.0,
    'run_id': 0,
    'resumen_dia': {
        "Lavadoras y Secadoras": {},
        "Detergentes": {},
        "Bolsas": {}
    },
    'total_dia': 0.0,
    'venta_registrada': False,
    # claves para reseteo de "Ver encargos"
    'encargo_selector': "— Selecciona —",
    'reset_after_save': False,
    'last_saved_id': None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- INTERFAZ ---
st.title("🧺 Sistema de Ventas - Lavandería")

menu = st.sidebar.selectbox(
    "Menú principal",
    ["Registrar venta", "Ver registros", "Registrar encargo", "Ver encargos", "Resumen de uso"]  # 👈 agregado
)

# =========================
# ===== REGISTRAR VENTA ===
# =========================
if menu == "Registrar venta":
    st.session_state.vendedor = st.text_input("👤 Nombre del empleado / vendedor", value=st.session_state.vendedor)
    st.session_state.nombre = st.text_input("Nombre del cliente", value=st.session_state.nombre)
    st.session_state.apellido = st.text_input("Apellido del cliente", value=st.session_state.apellido)

    st.write("Selecciona los productos que desea el cliente:")
    seleccionados = {}

    def producto_input(productos, key_suffix=""):
        for producto, precio in productos.items():
            key = f"{producto}{key_suffix}_run{st.session_state.run_id}"
            cantidad = st.number_input(f"{producto} (${precio})", min_value=0, step=1, value=0, key=key)
            if cantidad > 0:
                seleccionados[producto] = cantidad
            elif producto in seleccionados:
                del seleccionados[producto]

    with st.expander("🧺 Lavadoras y Secadoras", expanded=True):
        producto_input(lavadoras_secadoras)
    with st.expander("🧴 Detergentes", expanded=True):
        producto_input(detergentes, "_det")
    with st.expander("🛍️ Bolsas", expanded=True):
        producto_input(bolsas, "_bol")

    # --- CALCULAR VENTA ---
    if st.button("💰 Calcular venta"):
        if not seleccionados:
            st.warning("Selecciona al menos un producto.")
        elif not st.session_state.nombre.strip() or not st.session_state.apellido.strip():
            st.warning("Ingresa el nombre y apellido del cliente.")
        elif not st.session_state.vendedor.strip():
            st.warning("Ingresa el nombre del vendedor.")
        else:
            st.session_state.seleccionados = seleccionados.copy()
            total = sum(
                (lavadoras_secadoras.get(p) or detergentes.get(p) or bolsas.get(p)) * c
                for p, c in st.session_state.seleccionados.items()
            )
            st.session_state.total = total
            st.session_state.venta_registrada = False
            st.success(f"Total calculado: ${total:.2f}")

    # --- MOSTRAR RESUMEN ---
    if st.session_state.total > 0:
        st.markdown(f"### 🧾 Resumen de la venta para {st.session_state.nombre} {st.session_state.apellido}")
        st.markdown(f"**Vendedor:** {st.session_state.vendedor}")
        st.write("---")

        def mostrar_categoria(nombre_cat, productos_cat):
            cat_seleccionados = {p: c for p, c in st.session_state.seleccionados.items() if p in productos_cat}
            if cat_seleccionados:
                st.markdown(f"**{nombre_cat}**")
                col1, col2, col3, col4 = st.columns([3,1,1,1])
                col1.markdown("**Producto**")
                col2.markdown("**Cantidad**")
                col3.markdown("**Precio Unitario**")
                col4.markdown("**Subtotal**")
                st.write("---")
                for p, c in cat_seleccionados.items():
                    precio = productos_cat[p]
                    subtotal = precio * c
                    col1, col2, col3, col4 = st.columns([3,1,1,1])
                    col1.write(p)
                    col2.write(c)
                    col3.write(f"${precio}")
                    col4.write(f"${subtotal}")
                st.write("---")

        mostrar_categoria("🧺 Lavadoras y Secadoras", lavadoras_secadoras)
        mostrar_categoria("🧴 Detergentes", detergentes)
        mostrar_categoria("🛍️ Bolsas", bolsas)

        st.markdown(f"**💰 Total: ${st.session_state.total:.2f}**")

        st.session_state.dinero = st.number_input(
            "Dinero entregado por el cliente:",
            min_value=0.0, step=1.0, value=st.session_state.dinero, key="dinero_input"
        )

        if st.button("✅ Calcular cambio y registrar venta"):
            if st.session_state.dinero < st.session_state.total:
                st.error(f"Dinero insuficiente. Faltan ${st.session_state.total - st.session_state.dinero:.2f}")
            else:
                cambio = st.session_state.dinero - st.session_state.total
                st.success(f"💵 Cambio a entregar: ${cambio:.2f}")

                if not st.session_state.venta_registrada:
                    try:
                        data = {
                            "fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                            "vendedor": st.session_state.vendedor,
                            "cliente": f"{st.session_state.nombre} {st.session_state.apellido}",
                            "productos": st.session_state.seleccionados,
                            "total": st.session_state.total,
                            "cambio": cambio
                        }
                        supabase.table("ventas").insert(data).execute()
                        st.success("✅ Venta registrada en la base de datos.")
                    except Exception as e:
                        st.error(f"Error al guardar en la base de datos: {e}")

                    for p, c in st.session_state.seleccionados.items():
                        if p in lavadoras_secadoras:
                            cat = "Lavadoras y Secadoras"
                        elif p in detergentes:
                            cat = "Detergentes"
                        else:
                            cat = "Bolsas"
                        st.session_state.resumen_dia[cat][p] = st.session_state.resumen_dia[cat].get(p, 0) + c
                    st.session_state.total_dia += st.session_state.total
                    st.session_state.venta_registrada = True
                else:
                    st.info("Esta venta ya fue registrada.")

    # --- NUEVA VENTA ---
    def reiniciar_todo():
        st.session_state.nombre = ""
        st.session_state.apellido = ""
        st.session_state.vendedor = ""
        st.session_state.dinero = 0.0
        st.session_state.total = 0.0
        st.session_state.seleccionados = {}
        st.session_state.venta_registrada = False
        st.session_state.run_id += 1

    st.write("---")
    st.button("🆕 Nueva venta", on_click=reiniciar_todo)

    # --- RESUMEN DEL DÍA ---
    st.write("---")
    st.markdown("## 📊 Resumen acumulado del día")

    total_general = 0.0
    for categoria, productos in st.session_state.resumen_dia.items():
        if productos:
            st.markdown(f"**{categoria}**")
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown("**Producto**")
            col2.markdown("**Cantidad total**")
            col3.markdown("**Monto total**")
            st.write("---")
            for p, c in productos.items():
                if p in lavadoras_secadoras:
                    precio = lavadoras_secadoras[p]
                elif p in detergentes:
                    precio = detergentes[p]
                else:
                    precio = bolsas[p]
                subtotal = precio * c
                total_general += subtotal
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(p)
                col2.write(c)
                col3.write(f"${subtotal:.2f}")
            st.write("---")

    st.markdown(f"### 💰 Total generado en el día: **${total_general:.2f}**")

# ==========================
# ===== VER REGISTROS  =====
# ==========================
elif menu == "Ver registros":
    st.header("📋 Ventas registradas en la base de datos")

    st.subheader("📆 Filtrar ventas por rango de fechas")
    start_date = st.date_input("Fecha inicio", value=date.today().replace(day=1))
    end_date = st.date_input("Fecha fin", value=date.today())

    try:
        response = supabase.table("ventas").select("*").order("fecha", desc=True).execute()
        registros = response.data

        if registros:
            df = pd.DataFrame(registros)
            df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)

            mask = (df["fecha"] >= pd.to_datetime(start_date)) & (df["fecha"] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
            df_filtrado = df.loc[mask]

            st.dataframe(df_filtrado)

            st.subheader("📊 Corte de ventas del período seleccionado")
            total_ventas = df_filtrado["total"].sum()
            cantidad_ventas = len(df_filtrado)
            promedio = df_filtrado["total"].mean() if cantidad_ventas > 0 else 0

            st.markdown(f"**Total de ventas:** ${total_ventas:.2f}")
            st.markdown(f"**Cantidad de ventas:** {cantidad_ventas}")
            st.markdown(f"**Promedio por venta:** ${promedio:.2f}")

            st.subheader("📥 Descargar reporte")
            csv = df_filtrado.to_csv(index=False).encode("utf-8")
            st.download_button("📁 Descargar CSV", data=csv, file_name="reporte_ventas_filtrado.csv", mime="text/csv")

            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Ventas")
                st.download_button("📊 Descargar Excel", data=output.getvalue(),
                                   file_name="reporte_ventas_filtrado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Para exportar a Excel en la nube, agrega 'XlsxWriter' a requirements.txt.")

        else:
            st.info("Aún no hay ventas registradas.")
    except Exception as e:
        st.error(f"Error al obtener los registros: {e}")

# ============================
# ===== REGISTRAR ENCARGO ====
# ============================
elif menu == "Registrar encargo":
    st.header("📦 Registrar encargo (kilos a $22/kg)")

    vendedor_enc = st.text_input("👤 Nombre del empleado / vendedor (encargo)", value=st.session_state.vendedor)
    cliente_enc = st.text_input("Nombre del cliente (encargo)")
    kilos = st.number_input("Kilos pesados", min_value=0.0, step=0.1)

    PRECIO_KILO = 22
    total_enc = round(kilos * PRECIO_KILO, 2)
    st.markdown(f"**Total encargo (kilos × ${PRECIO_KILO}/kg): ${total_enc:.2f}**")

    st.write("---")
    pago_estado = st.radio("Estado del pago", ["Pagado", "Pendiente"], horizontal=True, index=1)

    dinero_recibido = 0.0
    cambio_enc = 0.0
    if pago_estado == "Pagado":
        dinero_recibido = st.number_input("💳 ¿Con cuánto paga?", min_value=0.0, step=1.0, value=0.0,
                                          help="Ingresa el efectivo recibido.")
        if kilos > 0:
            cambio_enc = max(dinero_recibido - total_enc, 0.0)
            st.markdown(f"**💵 Cambio a entregar:** ${cambio_enc:.2f}")

    if st.button("✅ Registrar encargo"):
        if not vendedor_enc.strip():
            st.warning("Ingresa el nombre del vendedor.")
        elif not cliente_enc.strip():
            st.warning("Ingresa el nombre del cliente.")
        elif kilos <= 0:
            st.warning("Ingresa los kilos pesados (mayor a 0).")
        elif pago_estado == "Pagado" and dinero_recibido < total_enc:
            st.error(f"El monto recibido (${dinero_recibido:.2f}) no cubre el total (${total_enc:.2f}).")
        else:
            try:
                if pago_estado == "Pagado":
                    dinero_db = float(dinero_recibido)
                    cambio_db = float(cambio_enc)
                    pago_fecha = datetime.now(timezone("America/Mexico_City")).isoformat()
                else:
                    dinero_db = 0.0
                    cambio_db = 0.0
                    pago_fecha = None

                data = {
                    "fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                    "vendedor": vendedor_enc.strip(),
                    "cliente": cliente_enc.strip(),
                    "kilos": float(kilos),
                    "total": float(total_enc),
                    "dinero": float(dinero_db),
                    "cambio": float(cambio_db),
                    "estado": "En espera",
                    "uso_lavadoras": {},
                    "uso_secadoras": {},
                    "detergentes_usados": {},
                    "bolsas_usadas": {},
                    "pago_estado": pago_estado,
                    "pago_fecha": pago_fecha
                }
                supabase.table("encargos_kilos").insert(data).execute()
                st.success("✅ Encargo registrado.")
            except Exception as e:
                st.error(f"Error al guardar el encargo: {e}")

# ========================
# ===== VER ENCARGOS  ====
# ========================
elif menu == "Ver encargos":
    st.header("📋 Encargos (kilos)")

    # --- Limpieza tras guardar (antes de crear widgets) ---
    if st.session_state.get("reset_after_save") and st.session_state.get("last_saved_id"):
        enc_id = str(st.session_state["last_saved_id"])
        for prefix in ["lav16_", "lav9_", "lav4_", "sec15_", "sec30_",
                       "detj_", "dets_", "detd_", "bolc_", "bolm_", "bolg_", "pago_"]:
            st.session_state.pop(prefix + enc_id, None)
        st.session_state["encargo_selector"] = "— Selecciona —"
        st.session_state["reset_after_save"] = False
        st.session_state["last_saved_id"] = None

    st.subheader("📆 Filtrar encargos por rango de fechas")
    start_date_e = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="enc_start")
    end_date_e = st.date_input("Fecha fin", value=date.today(), key="enc_end")

    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "En espera", "Entregado"])

    try:
        response = supabase.table("encargos_kilos").select("*").order("fecha", desc=True).execute()
        registros_e = response.data

        if registros_e:
            df_e = pd.DataFrame(registros_e)
            if "fecha" in df_e.columns:
                df_e["fecha"] = pd.to_datetime(df_e["fecha"]).dt.tz_localize(None)

            mask_e = (df_e["fecha"] >= pd.to_datetime(start_date_e)) & (df_e["fecha"] < pd.to_datetime(end_date_e) + pd.Timedelta(days=1))
            df_e = df_e.loc[mask_e]

            if estado_filtro != "Todos" and "estado" in df_e.columns:
                df_e = df_e[df_e["estado"] == estado_filtro]

            st.dataframe(df_e)

            st.subheader("📊 Totales de encargos del período")
            total_importe = float(df_e["total"].sum()) if "total" in df_e.columns else 0.0
            total_kilos = float(df_e["kilos"].sum()) if "kilos" in df_e.columns else 0.0
            cantidad_enc = int(len(df_e))
            st.markdown(f"**Kilos totales:** {total_kilos:.2f} kg")
            st.markdown(f"**Cantidad de encargos:** {cantidad_enc}")
            st.markdown(f"**Total de ventas del período:** ${total_importe:.2f}")

            st.write("---")
            st.subheader("🧰 Completar uso de máquinas/consumibles y pago")

            if not df_e.empty and "id" in df_e.columns:
                ids_str = df_e["id"].astype(str).tolist()
                opciones = ["— Selecciona —"] + ids_str

                encargo_id_sel = st.selectbox("Selecciona el ID del encargo", opciones, key="encargo_selector")

                if encargo_id_sel != "— Selecciona —":
                    encargo_row = df_e[df_e["id"].astype(str) == encargo_id_sel].iloc[0].to_dict()

                    uso_lav = encargo_row.get("uso_lavadoras") or {}
                    uso_sec = encargo_row.get("uso_secadoras") or {}
                    det_us  = encargo_row.get("detergentes_usados") or {}
                    bol_us  = encargo_row.get("bolsas_usadas") or {}

                    # --- keys únicas por encargo ---
                    k_lav16 = f"lav16_{encargo_id_sel}"
                    k_lav9  = f"lav9_{encargo_id_sel}"
                    k_lav4  = f"lav4_{encargo_id_sel}"
                    k_sec15 = f"sec15_{encargo_id_sel}"
                    k_sec30 = f"sec30_{encargo_id_sel}"
                    k_det_j = f"detj_{encargo_id_sel}"
                    k_det_s = f"dets_{encargo_id_sel}"
                    k_det_d = f"detd_{encargo_id_sel}"
                    k_bol_c = f"bolc_{encargo_id_sel}"
                    k_bol_m = f"bolm_{encargo_id_sel}"
                    k_bol_g = f"bolg_{encargo_id_sel}"
                    k_pago  = f"pago_{encargo_id_sel}"

                    # inicializar defaults antes de crear widgets
                    def init_key(key, default_val):
                        if key not in st.session_state:
                            st.session_state[key] = default_val

                    init_key(k_lav16, int(uso_lav.get("Lavadora 16 kg", 0)))
                    init_key(k_lav9,  int(uso_lav.get("Lavadora 9 kg",  0)))
                    init_key(k_lav4,  int(uso_lav.get("Lavadora 4 kg",  0)))
                    init_key(k_sec15, int(uso_sec.get("Secadora 9 kg (15 minutos)", 0)))
                    init_key(k_sec30, int(uso_sec.get("Secadora 9 kg (30 minutos)", 0)))
                    init_key(k_det_j, int(det_us.get("1 medida de jabón", 0)))
                    init_key(k_det_s, int(det_us.get("1 medida de suavizante", 0)))
                    init_key(k_det_d, int(det_us.get("1 medida de desmugrante", 0)))
                    init_key(k_bol_c, int(bol_us.get("1 bolsa chica",   0)))
                    init_key(k_bol_m, int(bol_us.get("1 bolsa mediana", 0)))
                    init_key(k_bol_g, int(bol_us.get("1 bolsa grande",  0)))
                    init_key(k_pago,  0.0)

                    # --- Lavadoras ---
                    st.markdown("**Lavadoras usadas**")
                    colL1, colL2, colL3 = st.columns(3)
                    lav16 = colL1.number_input("Lavadora 16 kg (cantidad)", min_value=0, step=1, key=k_lav16)
                    lav9  = colL2.number_input("Lavadora 9 kg (cantidad)",  min_value=0, step=1, key=k_lav9)
                    lav4  = colL3.number_input("Lavadora 4 kg (cantidad)",  min_value=0, step=1, key=k_lav4)

                    # --- Secadoras ---
                    st.markdown("**Secadoras usadas**")
                    colS1, colS2 = st.columns(2)
                    sec15 = colS1.number_input("Secadora 9 kg (15 min)", min_value=0, step=1, key=k_sec15)
                    sec30 = colS2.number_input("Secadora 9 kg (30 min)", min_value=0, step=1, key=k_sec30)

                    # --- Detergentes ---
                    st.markdown("**Detergentes usados**")
                    colD1, colD2, colD3 = st.columns(3)
                    det_jabon = colD1.number_input("Medidas de jabón",       min_value=0, step=1, key=k_det_j)
                    det_suav  = colD2.number_input("Medidas de suavizante",  min_value=0, step=1, key=k_det_s)
                    det_desm  = colD3.number_input("Medidas de desmugrante", min_value=0, step=1, key=k_det_d)

                    # --- Bolsas ---
                    st.markdown("**Bolsas usadas**")
                    colB1, colB2, colB3 = st.columns(3)
                    bol_ch = colB1.number_input("Bolsas chicas",   min_value=0, step=1, key=k_bol_c)
                    bol_md = colB2.number_input("Bolsas medianas", min_value=0, step=1, key=k_bol_m)
                    bol_gr = colB3.number_input("Bolsas grandes",  min_value=0, step=1, key=k_bol_g)

                    st.write("---")
                    total_encargo = float(encargo_row.get("total", 0.0))
                    pago_estado_actual = (encargo_row.get("pago_estado") or "Pendiente")
                    st.markdown(f"**Estado de pago actual:** {pago_estado_actual} &nbsp;&nbsp;|&nbsp;&nbsp; **Total:** ${total_encargo:.2f}")

                    # Si pendiente, permitir cobrar ahora SIN reasignar el session_state del widget
                    dinero_cobrar = 0.0
                    if pago_estado_actual == "Pendiente":
                        dinero_cobrar = st.number_input(
                            "💳 Monto recibido ahora",
                            min_value=0.0, step=1.0,
                            value=st.session_state.get(k_pago, 0.0),
                            key=k_pago
                        )
                        cambio_preview = max(dinero_cobrar - total_encargo, 0.0)
                        st.markdown(f"**💵 Cambio a entregar (previo):** ${cambio_preview:.2f}")
                        st.caption("¿Cubre el total? " + ("Sí" if dinero_cobrar >= total_encargo else "No, queda pendiente"))

                    col_bt1, col_bt2 = st.columns(2)
                    if col_bt1.button("💾 Guardar uso / pago", key=f"guardar_uso_pago_{encargo_id_sel}"):
                        try:
                            update_data = {
                                "uso_lavadoras": {
                                    "Lavadora 16 kg": int(st.session_state[k_lav16]),
                                    "Lavadora 9 kg":  int(st.session_state[k_lav9]),
                                    "Lavadora 4 kg":  int(st.session_state[k_lav4]),
                                },
                                "uso_secadoras": {
                                    "Secadora 9 kg (15 minutos)": int(st.session_state[k_sec15]),
                                    "Secadora 9 kg (30 minutos)": int(st.session_state[k_sec30]),
                                },
                                "detergentes_usados": {
                                    "1 medida de jabón":       int(st.session_state[k_det_j]),
                                    "1 medida de suavizante":  int(st.session_state[k_det_s]),
                                    "1 medida de desmugrante": int(st.session_state[k_det_d]),
                                },
                                "bolsas_usadas": {
                                    "1 bolsa chica":  int(st.session_state[k_bol_c]),
                                    "1 bolsa mediana":int(st.session_state[k_bol_m]),
                                    "1 bolsa grande": int(st.session_state[k_bol_g]),
                                },
                            }

                            # Registrar pago si estaba pendiente y se capturó dinero
                            if pago_estado_actual == "Pendiente" and dinero_cobrar > 0:
                                recibido = float(dinero_cobrar)
                                nuevo_cambio = max(recibido - total_encargo, 0.0)
                                update_data.update({
                                    "pago_estado": "Pagado" if recibido >= total_encargo else "Pendiente",
                                    "pago_fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                                    "dinero": recibido,
                                    "cambio": float(nuevo_cambio),
                                })

                            supabase.table("encargos_kilos").update(update_data).eq("id", int(encargo_id_sel)).execute()

                            # ▶️ Guardar ID y levantar bandera de reseteo, luego rerun (esto limpia todos los widgets a 0)
                            st.session_state["last_saved_id"] = encargo_id_sel
                            st.session_state["reset_after_save"] = True
                            st.success("Cambios guardados. Limpiando campos…")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar cambios: {e}")

                    if col_bt2.button("✅ Marcar como entregado", key=f"marcar_entregado_{encargo_id_sel}"):
                        try:
                            supabase.table("encargos_kilos").update({"estado": "Entregado"}).eq("id", int(encargo_id_sel)).execute()
                            st.success(f"Encargo {encargo_id_sel} marcado como Entregado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar el encargo: {e}")
                else:
                    st.info("Selecciona un ID de encargo para capturar su uso y/o pago.")
            else:
                st.info("No hay encargos para editar en el rango/estado seleccionado.")

            st.subheader("📥 Descargar reporte (encargos)")
            csv_e = df_e.to_csv(index=False).encode("utf-8")
            st.download_button("📁 Descargar CSV (encargos)", data=csv_e, file_name="reporte_encargos_filtrado.csv", mime="text/csv")

            try:
                output_e = BytesIO()
                with pd.ExcelWriter(output_e, engine="xlsxwriter") as writer:
                    df_e.to_excel(writer, index=False, sheet_name="Encargos")
                st.download_button("📊 Descargar Excel (encargos)", data=output_e.getvalue(),
                                   file_name="reporte_encargos_filtrado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Para exportar a Excel en la nube, agrega 'XlsxWriter' a requirements.txt.")
        else:
            st.info("Aún no hay encargos registrados.")
    except Exception as e:
        st.error(f"Error al obtener los encargos: {e}")

# ============================
# ===== RESUMEN DE USO (A) ===
# ============================
elif menu == "Resumen de uso":
    st.header("📊 Resumen de uso — Ventas vs Encargos (al vuelo)")

    # Filtros de fecha
    st.subheader("📆 Selecciona rango de fechas")
    start_date_u = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="uso_start")
    end_date_u = st.date_input("Fecha fin", value=date.today(), key="uso_end")
    st.caption("El cálculo se hace al vuelo a partir de las tablas. No se guarda nada en la base de datos.")

    # Helpers
    def sumar_dicts_en_col(serie_dicts):
        """Suma todas las claves de una serie con dicts -> Counter"""
        c = Counter()
        if serie_dicts is None:
            return c
        for d in serie_dicts:
            if isinstance(d, dict):
                for k, v in d.items():
                    try:
                        c[k] += int(v or 0)
                    except Exception:
                        pass
        return c

    # Orden de ítems por sección
    items_lav = ["Lavadora 16 kg", "Lavadora 9 kg", "Lavadora 4 kg"]
    items_sec = ["Secadora 9 kg (15 minutos)", "Secadora 9 kg (30 minutos)", "Secado"]
    items_det = ["1 medida de jabón", "1 medida de suavizante", "1 medida de desmugrante"]
    items_bol = ["1 bolsa chica", "1 bolsa mediana", "1 bolsa grande"]

    try:
        # ---------- VENTAS ----------
        ventas = supabase.table("ventas").select("*").order("fecha", desc=True).execute().data or []
        df_v = pd.DataFrame(ventas) if ventas else pd.DataFrame()
        if not df_v.empty and "fecha" in df_v.columns:
            df_v["fecha"] = pd.to_datetime(df_v["fecha"]).dt.tz_localize(None)
            mask_v = (df_v["fecha"] >= pd.to_datetime(start_date_u)) & (df_v["fecha"] < pd.to_datetime(end_date_u) + pd.Timedelta(days=1))
            df_v = df_v.loc[mask_v]

        cnt_lav_v = Counter(); cnt_sec_v = Counter(); cnt_det_v = Counter(); cnt_bol_v = Counter()
        if not df_v.empty and "productos" in df_v.columns:
            for d in df_v["productos"]:
                if isinstance(d, dict):
                    for item, qty in d.items():
                        try:
                            qty = int(qty or 0)
                        except Exception:
                            qty = 0
                        if item in items_lav:
                            cnt_lav_v[item] += qty
                        elif item in items_sec:
                            cnt_sec_v[item] += qty
                        elif item in items_det:
                            cnt_det_v[item] += qty
                        elif item in items_bol:
                            cnt_bol_v[item] += qty

        # ---------- ENCARGOS ----------
        encargos = supabase.table("encargos_kilos").select("*").order("fecha", desc=True).execute().data or []
        df_eu = pd.DataFrame(encargos) if encargos else pd.DataFrame()
        if not df_eu.empty and "fecha" in df_eu.columns:
            df_eu["fecha"] = pd.to_datetime(df_eu["fecha"]).dt.tz_localize(None)
            mask_eu = (df_eu["fecha"] >= pd.to_datetime(start_date_u)) & (df_eu["fecha"] < pd.to_datetime(end_date_u) + pd.Timedelta(days=1))
            df_eu = df_eu.loc[mask_eu]

        cnt_lav_e = sumar_dicts_en_col(df_eu["uso_lavadoras"]) if not df_eu.empty and "uso_lavadoras" in df_eu.columns else Counter()
        cnt_sec_e = sumar_dicts_en_col(df_eu["uso_secadoras"]) if not df_eu.empty and "uso_secadoras" in df_eu.columns else Counter()
        cnt_det_e = sumar_dicts_en_col(df_eu["detergentes_usados"]) if not df_eu.empty and "detergentes_usados" in df_eu.columns else Counter()
        cnt_bol_e = sumar_dicts_en_col(df_eu["bolsas_usadas"]) if not df_eu.empty and "bolsas_usadas" in df_eu.columns else Counter()

        # ---------- Construcción de tablas por sección ----------
        def make_df(seccion_nombre, items, cnt_v, cnt_e):
            rows = []
            for it in items:
                v = int(cnt_v.get(it, 0))
                e = int(cnt_e.get(it, 0))
                rows.append({"Ítem": it, "Por ventas": v, "Por encargos": e, "Total": v + e})
            df = pd.DataFrame(rows)
            st.write(f"### {seccion_nombre}")
            st.dataframe(df, use_container_width=True)
            st.markdown(f"**Total {seccion_nombre.lower()}:** {int(df['Total'].sum())}")
            return df

        df_lav = make_df("🧺 Lavadoras", items_lav, cnt_lav_v, cnt_lav_e)
        df_sec = make_df("🔥 Secadoras", items_sec, cnt_sec_v, cnt_sec_e)
        df_det = make_df("🧴 Detergentes", items_det, cnt_det_v, cnt_det_e)
        df_bol = make_df("🛍️ Bolsas", items_bol, cnt_bol_v, cnt_bol_e)

        # ---------- Resumen general (métricas rápidas) ----------
        st.write("---")
        colA, colB, colC = st.columns(3)
        colA.metric("🔧 Total por ventas", int(df_lav["Por ventas"].sum() + df_sec["Por ventas"].sum() + df_det["Por ventas"].sum() + df_bol["Por ventas"].sum()))
        colB.metric("📦 Total por encargos", int(df_lav["Por encargos"].sum() + df_sec["Por encargos"].sum() + df_det["Por encargos"].sum() + df_bol["Por encargos"].sum()))
        colC.metric("🧮 Total general", int(df_lav["Total"].sum() + df_sec["Total"].sum() + df_det["Total"].sum() + df_bol["Total"].sum()))

        # ---------- Descarga CSV combinado ----------
        st.write("---")
        st.subheader("📥 Descargar CSV (resumen de uso: ventas vs encargos)")
        df_export = pd.concat([
            df_lav.assign(Categoría="Lavadoras"),
            df_sec.assign(Categoría="Secadoras"),
            df_det.assign(Categoría="Detergentes"),
            df_bol.assign(Categoría="Bolsas"),
        ], axis=0)[["Categoría", "Ítem", "Por ventas", "Por encargos", "Total"]]
        csv_export = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📁 Descargar CSV (uso por ítem)",
            data=csv_export,
            file_name="resumen_uso_ventas_encargos.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"Error al generar el resumen: {e}")

# --- ADMIN: REINICIAR BASE DE DATOS ---
st.sidebar.write("---")
st.sidebar.markdown("### 🔧 Herramientas de administración")

if st.sidebar.button("🧹 Eliminar todos los registros y reiniciar IDs"):
    st.session_state.modo_admin = True

if "modo_admin" in st.session_state and st.session_state.modo_admin:
    st.warning("⚠️ Esta acción eliminará **todos los registros** de ventas y encargos, y **reiniciará los IDs** de ambas tablas (usando RPC).")
    password = st.text_input("Introduce la contraseña de administrador:", type="password", key="admin_pass")
    confirmar = st.checkbox("Confirmo que deseo eliminar todos los registros permanentemente.")

    if st.button("🚨 Confirmar eliminación"):
        if password != "LavanderiaFerro!":
            st.error("❌ Contraseña incorrecta.")
        elif not confirmar:
            st.warning("Debes marcar la casilla de confirmación para continuar.")
        else:
            with st.spinner("Eliminando registros y reiniciando secuencias..."):
                try:
                    supabase.rpc("reset_ventas").execute()
                    supabase.rpc("reset_encargos_kilos").execute()
                    time.sleep(1)
                    st.success("✅ Se eliminaron todos los registros y se reiniciaron los IDs de **ventas** y **encargos_kilos**.")
                    st.session_state.modo_admin = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al reiniciar la base de datos: {e}")


