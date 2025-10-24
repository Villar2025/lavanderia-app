import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
from pytz import timezone
import time
import pandas as pd
from io import BytesIO

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
    "Secado": 80,  # ✅ nombre exacto que pediste
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
    'venta_registrada': False
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- INTERFAZ ---
st.title("🧺 Sistema de Ventas - Lavandería")

menu = st.sidebar.selectbox(
    "Menú principal",
    ["Registrar venta", "Ver registros", "Registrar encargo", "Ver encargos"]
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

    # ✅ Filtros por fecha
    st.subheader("📆 Filtrar ventas por rango de fechas")
    start_date = st.date_input("Fecha inicio", value=date.today().replace(day=1))
    end_date = st.date_input("Fecha fin", value=date.today())

    try:
        response = supabase.table("ventas").select("*").order("fecha", desc=True).execute()
        registros = response.data

        if registros:
            df = pd.DataFrame(registros)
            df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)

            # ✅ Incluir el último día completo
            mask = (df["fecha"] >= pd.to_datetime(start_date)) & (df["fecha"] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
            df_filtrado = df.loc[mask]

            st.dataframe(df_filtrado)

            # ✅ Corte del período
            st.subheader("📊 Corte de ventas del período seleccionado")
            total_ventas = df_filtrado["total"].sum()
            cantidad_ventas = len(df_filtrado)
            promedio = df_filtrado["total"].mean() if cantidad_ventas > 0 else 0

            st.markdown(f"**Total de ventas:** ${total_ventas:.2f}")
            st.markdown(f"**Cantidad de ventas:** {cantidad_ventas}")
            st.markdown(f"**Promedio por venta:** ${promedio:.2f}")

            # ✅ Descargas
            st.subheader("📥 Descargar reporte")
            csv = df_filtrado.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📁 Descargar CSV",
                data=csv,
                file_name="reporte_ventas_filtrado.csv",
                mime="text/csv"
            )

            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Ventas")
                st.download_button(
                    label="📊 Descargar Excel",
                    data=output.getvalue(),
                    file_name="reporte_ventas_filtrado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
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
    st.markdown(f"**Total encargo (kilos × $22): ${total_enc:.2f}**")

    dinero_enc = st.number_input("Dinero entregado por el cliente (encargo)", min_value=0.0, step=1.0)
    cambio_enc = round(max(dinero_enc - total_enc, 0.0), 2)
    st.markdown(f"**💵 Cambio a entregar: ${cambio_enc:.2f}**")

    if st.button("✅ Registrar encargo"):
        # Validaciones
        if not vendedor_enc.strip():
            st.warning("Ingresa el nombre del vendedor.")
        elif not cliente_enc.strip():
            st.warning("Ingresa el nombre del cliente.")
        elif kilos <= 0:
            st.warning("Ingresa los kilos pesados (mayor a 0).")
        elif dinero_enc < total_enc:
            st.error(f"Dinero insuficiente para el encargo. Faltan ${total_enc - dinero_enc:.2f}")
        else:
            try:
                data = {
                    "fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                    "vendedor": vendedor_enc.strip(),
                    "cliente": cliente_enc.strip(),
                    "kilos": float(kilos),
                    "total": float(total_enc),
                    "dinero": float(dinero_enc),
                    "cambio": float(cambio_enc),
                    "estado": "En espera"
                }
                supabase.table("encargos_kilos").insert(data).execute()
                st.success("✅ Encargo registrado en la base de datos (estado: En espera).")
            except Exception as e:
                st.error(f"Error al guardar el encargo: {e}")

# ========================
# ===== VER ENCARGOS  ====
# ========================
elif menu == "Ver encargos":
    st.header("📋 Encargos (kilos)")

    # Filtros
    st.subheader("📆 Filtrar encargos por rango de fechas")
    start_date_e = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="enc_start")
    end_date_e = st.date_input("Fecha fin", value=date.today(), key="enc_end")

    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "En espera", "Entregado"])

    try:
        response = supabase.table("encargos_kilos").select("*").order("fecha", desc=True).execute()
        registros_e = response.data

        if registros_e:
            df_e = pd.DataFrame(registros_e)
            # Conversión de fecha
            if "fecha" in df_e.columns:
                df_e["fecha"] = pd.to_datetime(df_e["fecha"]).dt.tz_localize(None)

            # Filtro por fechas (incluye día fin completo)
            mask_e = (df_e["fecha"] >= pd.to_datetime(start_date_e)) & (df_e["fecha"] < pd.to_datetime(end_date_e) + pd.Timedelta(days=1))
            df_e = df_e.loc[mask_e]

            # Filtro por estado
            if estado_filtro != "Todos" and "estado" in df_e.columns:
                df_e = df_e[df_e["estado"] == estado_filtro]

            st.dataframe(df_e)

            # ✅ Totales del período (igual estilo que ventas)
            st.subheader("📊 Totales de encargos del período")
            total_importe = float(df_e["total"].sum()) if "total" in df_e.columns else 0.0
            total_kilos = float(df_e["kilos"].sum()) if "kilos" in df_e.columns else 0.0
            cantidad_enc = int(len(df_e))
            st.markdown(f"**Kilos totales:** {total_kilos:.2f} kg")
            st.markdown(f"**Cantidad de encargos:** {cantidad_enc}")
            st.markdown(f"**Total de ventas del período:** ${total_importe:.2f}")

            # Descargar
            st.subheader("📥 Descargar reporte (encargos)")
            csv_e = df_e.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📁 Descargar CSV (encargos)",
                data=csv_e,
                file_name="reporte_encargos_filtrado.csv",
                mime="text/csv"
            )

            try:
                output_e = BytesIO()
                with pd.ExcelWriter(output_e, engine="xlsxwriter") as writer:
                    df_e.to_excel(writer, index=False, sheet_name="Encargos")
                st.download_button(
                    label="📊 Descargar Excel (encargos)",
                    data=output_e.getvalue(),
                    file_name="reporte_encargos_filtrado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception:
                st.info("Para exportar a Excel en la nube, agrega 'XlsxWriter' a requirements.txt.")

            # Marcar como entregado
            st.subheader("✅ Marcar encargo como entregado")
            pendientes = df_e[df_e["estado"] == "En espera"] if "estado" in df_e.columns else pd.DataFrame()
            if not pendientes.empty and "id" in pendientes.columns:
                opciones = pendientes["id"].astype(str).tolist()
                encargo_sel = st.selectbox("Selecciona el ID del encargo en espera", opciones)
                if st.button("Marcar como entregado"):
                    try:
                        supabase.table("encargos_kilos").update({"estado": "Entregado"}).eq("id", int(encargo_sel)).execute()
                        st.success(f"Encargo {encargo_sel} marcado como Entregado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar el encargo: {e}")
            else:
                st.info("No hay encargos en espera en el rango/estado seleccionado.")

        else:
            st.info("Aún no hay encargos registrados.")
    except Exception as e:
        st.error(f"Error al obtener los encargos: {e}")

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
                    # 🔁 Reiniciar ambas tablas vía RPC (sin delete())
                    supabase.rpc("reset_ventas").execute()
                    supabase.rpc("reset_encargos_kilos").execute()

                    time.sleep(1)
                    st.success("✅ Se eliminaron todos los registros y se reiniciaron los IDs de **ventas** y **encargos_kilos**.")
                    st.session_state.modo_admin = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al reiniciar la base de datos: {e}")

