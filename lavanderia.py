import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
from pytz import timezone
import time
import pandas as pd
from io import BytesIO
from collections import Counter
from math import ceil

# ========== CONFIG ==========
st.set_page_config(page_title="Lavandería", layout="wide")

SUPABASE_URL = "https://bempjrdqahqqjulatlcb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJlbXBqcmRxYWhxcWp1bGF0bGNiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4NjMyMzEsImV4cCI6MjA3NTQzOTIzMX0.qrx-H5c5mdKJP8RnHoyiETwmbBgx1Yvc8yGmW3NiuiU"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== CATÁLOGOS ==========
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
otros_catalogo = {
    "Suavizante": 22,
    "Pinol": 17,
    "Cloro": 10,
    "Jabón en polvo": 18,
}

# ========== STATE ==========
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
        "Bolsas": {},
        "Otros": {}
    },
    'total_dia': 0.0,
    'venta_registrada': False,
    'encargo_selector': "— Selecciona —",
    'reset_after_save': False,
    'last_saved_id': None,
    'enc_run_id': 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ========== HELPERS ==========
def _prune_zeros_simple(d):
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if isinstance(v, dict):
                sub = _prune_zeros_simple(v)
                if sub:
                    out[k] = sub
            else:
                try:
                    val = float(v)
                    if val != 0.0:
                        out[k] = int(val) if val.is_integer() else val
                except Exception:
                    if v:
                        out[k] = v
        return out
    return {} if d in (None, "") else d

def sumar_dicts_en_col(serie_dicts):
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

def subtotal_otros(dic):
    if not isinstance(dic, dict):
        return 0.0
    total = 0.0
    for k, v in dic.items():
        try:
            cant = int(v or 0)
            precio = float(otros_catalogo.get(k, 0.0))
            total += cant * precio
        except Exception:
            pass
    return float(total)

def precio_efectivo(producto, precio_catalogo):
    if producto == "Secadora 9 kg (30 minutos)":
        return float(precio_catalogo) / 2.0
    return float(precio_catalogo)

# ======= Dinero (ceil global) =======
def ceil_pesos(valor) -> float:
    """Redondea hacia arriba al siguiente peso entero."""
    try:
        return float(ceil(float(valor or 0)))
    except Exception:
        return 0.0

def ceil_cols_df(df, cols):
    if not isinstance(df, pd.DataFrame):
        return df
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).apply(ceil_pesos)
    return df

def money_col(label):
    return st.column_config.NumberColumn(label, format="$%.2f")

# Helpers encargo
def key_for(base: str) -> str:
    return f"{base}_run{st.session_state.enc_run_id}"

def reset_encargo_widgets():
    st.session_state.enc_run_id += 1
    st.session_state.otros_encargo_live = {}

# ========== UI PRINCIPAL ==========
st.title("🧺 Sistema de Ventas - Lavandería")
menu = st.sidebar.selectbox(
    "Menú principal",
    ["Registrar venta", "Ver registros", "Registrar encargo", "Ver encargos", "Resumen de uso", "Administración"]
)

# =========================
# ===== REGISTRAR VENTA ===
# =========================
if menu == "Registrar venta":
    st.session_state.vendedor = st.text_input(
        "👤 Nombre del empleado / vendedor",
        value=st.session_state.vendedor,
        key="vendedor_venta"
    )
    st.session_state.nombre = st.text_input("Nombre del cliente", value=st.session_state.nombre)
    st.session_state.apellido = st.text_input("Apellido del cliente", value=st.session_state.apellido)

    st.write("Selecciona los productos que desea el cliente:")
    seleccionados = {}
    otros_seleccionados = {}

    def producto_input(productos, key_suffix=""):
        for producto, precio in productos.items():
            key = f"{producto}{key_suffix}_run{st.session_state.run_id}"
            cantidad = st.number_input(f"{producto} (${precio})", min_value=0, step=1, value=0, key=key)
            if cantidad > 0:
                seleccionados[producto] = cantidad
            elif producto in seleccionados:
                del seleccionados[producto]

    with st.expander("🧺 Lavadoras y Secadoras", expanded=False):
        producto_input(lavadoras_secadoras)
    with st.expander("🧴 Detergentes", expanded=False):
        producto_input(detergentes, "_det")
    with st.expander("🛍️ Bolsas", expanded=False):
        producto_input(bolsas, "_bol")

    with st.expander("🧪 Otros (productos sueltos)", expanded=False):
        for prod, precio in otros_catalogo.items():
            key = f"otros_{prod}_run{st.session_state.run_id}"
            cant = st.number_input(f"{prod} (${precio})", min_value=0, step=1, value=0, key=key)
            if cant > 0:
                otros_seleccionados[prod] = cant
            elif prod in otros_seleccionados:
                del otros_seleccionados[prod]

    # Calcular
    if st.button("💰 Calcular venta"):
        if not (seleccionados or otros_seleccionados):
            st.warning("Selecciona al menos un producto.")
        elif not st.session_state.nombre.strip() or not st.session_state.apellido.strip():
            st.warning("Ingresa el nombre y apellido del cliente.")
        elif not st.session_state.vendedor.strip():
            st.warning("Ingresa el nombre del vendedor.")
        else:
            st.session_state.seleccionados = seleccionados.copy()
            total = 0.0
            for p, c in st.session_state.seleccionados.items():
                precio = (
                    lavadoras_secadoras.get(p)
                    or detergentes.get(p)
                    or bolsas.get(p)
                    or 0
                )
                total += precio * c
            for p, c in (otros_seleccionados or {}).items():
                total += otros_catalogo.get(p, 0) * c
            st.session_state.total = float(total)
            st.session_state.venta_registrada = False
            st.success(f"Total calculado: ${ceil_pesos(total):,.2f}")

    # Resumen (presentación con ceil)
    if st.session_state.total > 0:
        st.markdown(f"### 🧾 Resumen de la venta para {st.session_state.nombre} {st.session_state.apellido}")
        st.markdown(f"**Vendedor:** {st.session_state.vendedor}")
        st.write("---")

        def mostrar_categoria(nombre_cat, productos_cat, fuente="seleccionados"):
            base = st.session_state.seleccionados if fuente == "seleccionados" else fuente
            cat_seleccionados = {p: c for p, c in base.items() if p in productos_cat}
            if cat_seleccionados:
                st.markdown(f"**{nombre_cat}**")
                col1, col2, col3, col4 = st.columns([3,1,1,1])
                col1.markdown("**Producto**")
                col2.markdown("**Cantidad**")
                col3.markdown("**Precio Unitario**")
                col4.markdown("**Subtotal**")
                st.write("---")
                for p, c in cat_seleccionados.items():
                    precio_cat = productos_cat[p]
                    display_c = c
                    if p == "Secadora 9 kg (30 minutos)":
                        display_c = c * 2
                    display_precio = precio_efectivo(p, precio_cat)
                    subtotal = display_precio * display_c
                    col1, col2, col3, col4 = st.columns([3,1,1,1])
                    col1.write(p)
                    col2.write(display_c)
                    col3.write(f"${ceil_pesos(display_precio):,.2f}")
                    col4.write(f"${ceil_pesos(subtotal):,.2f}")
                st.write("---")

        mostrar_categoria("🧺 Lavadoras y Secadoras", lavadoras_secadoras)
        mostrar_categoria("🧴 Detergentes", detergentes)
        mostrar_categoria("🛍️ Bolsas", bolsas)
        if otros_seleccionados:
            mostrar_categoria("🧪 Otros", otros_catalogo, fuente=otros_seleccionados)

        subtotal_otros_sel = sum(otros_catalogo[p]*c for p, c in (otros_seleccionados or {}).items())
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("🧪 Otros", f"${ceil_pesos(subtotal_otros_sel):,.2f}")
        col_m2.metric("💰 Total", f"${ceil_pesos(st.session_state.total):,.2f}")

        st.session_state.dinero = st.number_input(
            "Dinero entregado por el cliente:",
            min_value=0.0, step=1.0, value=st.session_state.dinero, key="dinero_input"
        )

        if st.button("✅ Calcular cambio y registrar venta"):
            # Ceilar importes ANTES de guardar en BD
            subtotal_otros_sel_ce = ceil_pesos(subtotal_otros_sel)
            total_calc = float(st.session_state.total)
            total_ce = ceil_pesos(total_calc)

            if st.session_state.dinero < total_ce:
                falta = total_ce - st.session_state.dinero
                st.error(f"Dinero insuficiente. Faltan ${ceil_pesos(falta):,.2f}")
            else:
                cambio_raw = st.session_state.dinero - total_ce
                cambio_ce = ceil_pesos(cambio_raw)
                st.success(f"💵 Cambio a entregar: ${cambio_ce:,.2f}")

                if not st.session_state.venta_registrada:
                    try:
                        def split_por_categoria(sel_dict):
                            lav, sec, det, bol = {}, {}, {}, {}
                            for item, qty in (sel_dict or {}).items():
                                if qty and qty > 0:
                                    if item in lavadoras_secadoras:
                                        if item.startswith("Secadora") or item == "Secado":
                                            if item == "Secadora 9 kg (30 minutos)":
                                                sec[item] = int(qty) * 2
                                            else:
                                                sec[item] = int(qty)
                                        else:
                                            lav[item] = int(qty)
                                    elif item in detergentes:
                                        det[item] = int(qty)
                                    elif item in bolsas:
                                        bol[item] = int(qty)
                            return lav, sec, det, bol

                        lav_json, sec_json, det_json, bol_json = split_por_categoria(st.session_state.seleccionados)
                        otros_json = {}
                        if otros_seleccionados:
                            for p, c in otros_seleccionados.items():
                                if c and c > 0:
                                    otros_json[p] = int(c)

                        # Guardar CEILEADO en BD
                        data = {
                            "fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                            "vendedor": st.session_state.vendedor,
                            "cliente": f"{st.session_state.nombre} {st.session_state.apellido}",
                            "lavadoras": lav_json,
                            "secadoras": sec_json,
                            "detergentes": det_json,
                            "bolsas": bol_json,
                            "otros": otros_json,
                            "otros_importe": float(subtotal_otros_sel_ce),
                            "total": float(total_ce),
                            "cambio": float(cambio_ce)
                        }
                        data.pop("venta_sola", None)
                        data.pop("Otros", None)

                        supabase.table("ventas").insert(data).execute()
                        st.success("✅ Venta registrada en la base de datos.")
                    except Exception as e:
                        try:
                            err = getattr(e, "args", [{}])[0]
                            if isinstance(err, dict) and err.get("code") == "428C9":
                                data.pop("venta_sola", None)
                                supabase.table("ventas").insert(data).execute()
                                st.success("✅ Venta registrada (reintento sin 'venta_sola').")
                            else:
                                raise
                        except Exception as e2:
                            st.error(f"Error al guardar en la base de datos: {e2}")

                    # Resumen del día (conteos)
                    for p, c in st.session_state.seleccionados.items():
                        if p in lavadoras_secadoras:
                            cat = "Lavadoras y Secadoras"
                        elif p in detergentes:
                            cat = "Detergentes"
                        elif p in bolsas:
                            cat = "Bolsas"
                        elif p in otros_catalogo:
                            cat = "Otros"
                        else:
                            continue
                        inc = c * 2 if p == "Secadora 9 kg (30 minutos)" else c
                        st.session_state.resumen_dia[cat][p] = st.session_state.resumen_dia[cat].get(p, 0) + inc

                    if otros_seleccionados:
                        for p, c in otros_seleccionados.items():
                            st.session_state.resumen_dia["Otros"][p] = st.session_state.resumen_dia["Otros"].get(p, 0) + c

                    st.session_state.total_dia += ceil_pesos(st.session_state.total)
                    st.session_state.venta_registrada = True
                else:
                    st.info("Esta venta ya fue registrada.")

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

    st.write("---")
    st.markdown("## 📊 Resumen acumulado del día")
    total_general = 0.0
    for categoria, productos in st.session_state.resumen_dia.items():
        if productos:
            st.markdown(f"**{categoria}**")
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown("**Producto**")
            col2.markdown("**Cantidad total**")
            col3.markdown("**Monto total (ceil)**")
            st.write("---")
            for p, c in productos.items():
                if p in lavadoras_secadoras:
                    precio = precio_efectivo(p, lavadoras_secadoras[p])
                elif p in detergentes:
                    precio = detergentes[p]
                elif p in bolsas:
                    precio = bolsas[p]
                elif p in otros_catalogo:
                    precio = otros_catalogo[p]
                else:
                    continue
                subtotal = precio * c
                total_general += subtotal
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(p); col2.write(c); col3.write(f"${ceil_pesos(subtotal):,.2f}")
            st.write("---")
    st.markdown(f"### 💰 Total generado en el día: **${ceil_pesos(total_general):,.2f}**")

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

            if "fecha" in df.columns:
                try:
                    s = pd.to_datetime(df["fecha"], errors="coerce")
                    if hasattr(s.dt, "tz"):
                        df["fecha"] = s.dt.tz_convert(None)
                    else:
                        df["fecha"] = s
                    try:
                        df["fecha"] = df["fecha"].dt.tz_localize(None)
                    except Exception:
                        pass
                except Exception:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

            if "fecha" in df.columns:
                mask = (df["fecha"] >= pd.to_datetime(start_date)) & (df["fecha"] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
                df_filtrado = df.loc[mask].copy()
            else:
                df_filtrado = df.copy()

            # normalizar nombre legado
            if "otros_importes" in df_filtrado.columns and "otros_importe" not in df_filtrado.columns:
                df_filtrado.rename(columns={"otros_importes": "otros_importe"}, inplace=True)

            # asegurar numérico
            for colm in ["otros_importe", "total", "cambio"]:
                if colm in df_filtrado.columns:
                    df_filtrado[colm] = pd.to_numeric(df_filtrado[colm], errors="coerce").fillna(0.0)
                else:
                    df_filtrado[colm] = 0.0

            # venta_sola desde BD o calculada; luego ceil para vista/export
            if "venta_sola" in df_filtrado.columns:
                df_filtrado["venta_sola"] = pd.to_numeric(df_filtrado["venta_sola"], errors="coerce")
                df_filtrado["venta_sola"] = df_filtrado["venta_sola"].fillna(df_filtrado["total"] - df_filtrado["otros_importe"]).astype(float)
            else:
                df_filtrado["venta_sola"] = (df_filtrado["total"] - df_filtrado["otros_importe"]).astype(float)

            # Vista con ceil
            df_view = df_filtrado.copy()
            money_cols = ["venta_sola", "otros_importe", "total", "cambio"]
            df_view = ceil_cols_df(df_view, money_cols)

            columnas_en_orden = [
                "id", "fecha", "vendedor", "cliente",
                "venta_sola", "otros_importe", "total", "cambio",
                "lavadoras", "secadoras", "detergentes", "bolsas", "otros",
            ]
            cols_visibles = [c for c in columnas_en_orden if c in df_view.columns]
            cols_extra = [c for c in df_view.columns if c not in cols_visibles]
            df_view = df_view[cols_visibles + cols_extra]

            for cat_col in ["lavadoras", "secadoras", "detergentes", "bolsas", "otros"]:
                if cat_col in df_view.columns:
                    df_view[cat_col] = df_view[cat_col].apply(_prune_zeros_simple)

            st.dataframe(
                df_view,
                use_container_width=True,
                column_config={
                    "venta_sola": money_col("Venta (sin otros)"),
                    "otros_importe": money_col("Otros"),
                    "total": money_col("Total"),
                    "cambio": money_col("Cambio"),
                }
            )

            # Métricas (ceil)
            venta_sum = float(df_filtrado["venta_sola"].sum()) if "venta_sola" in df_filtrado.columns else 0.0
            otros_sum = float(df_filtrado["otros_importe"].sum()) if "otros_importe" in df_filtrado.columns else 0.0
            total_sum = float(df_filtrado["total"].sum()) if "total" in df_filtrado.columns else 0.0

            c1, c2, c3 = st.columns(3)
            c1.metric("Venta (sin otros)", f"${ceil_pesos(venta_sum):,.2f}")
            c2.metric("Otros", f"${ceil_pesos(otros_sum):,.2f}")
            c3.metric("Total", f"${ceil_pesos(total_sum):,.2f}")

            st.subheader("📊 Corte de ventas del período seleccionado")
            cantidad_ventas = len(df_filtrado)
            promedio = (total_sum / cantidad_ventas) if cantidad_ventas > 0 else 0.0
            st.markdown(f"**Total de ventas:** ${ceil_pesos(total_sum):,.2f}")
            st.markdown(f"**Cantidad de ventas:** {cantidad_ventas}")
            st.markdown(f"**Promedio por venta:** ${ceil_pesos(promedio):,.2f}")

            st.subheader("📥 Descargar reporte")
            df_export = df_view[[c for c in ["id","fecha","vendedor","cliente","venta_sola","otros_importe","total","cambio","lavadoras","secadoras","detergentes","bolsas","otros"] if c in df_view.columns]].copy()

            csv = df_export.to_csv(index=False).encode("utf-8")
            st.download_button("📁 Descargar CSV", data=csv, file_name="reporte_ventas_filtrado.csv", mime="text/csv")

            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_export.to_excel(writer, index=False, sheet_name="Ventas")
                st.download_button("📊 Descargar Excel", data=output.getvalue(),
                                   file_name="reporte_ventas_filtrado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Para exportar a Excel en la nube, agrega 'XlsxWriter'.")
        else:
            st.info("Aún no hay ventas registradas.")
    except Exception as e:
        st.error(f"Error al obtener los registros: {e}")

# ============================
# ===== REGISTRAR ENCARGO ====
# ============================
elif menu == "Registrar encargo":
    st.header("📦 Registrar encargo (kilos a $22/kg + servicios)")

    st.session_state.vendedor = st.text_input(
        "👤 Nombre del empleado / vendedor (encargo)",
        value=st.session_state.get("vendedor", ""),
        key="vendedor_enc_live"
    )
    cliente_enc = st.text_input("Nombre del cliente (encargo)", key=key_for("cliente_enc_live"))
    telefono_enc = st.text_input("📞 Teléfono del cliente", placeholder="10 dígitos", key=key_for("telefono_enc_live"))

    def _tel_ok(t):
        tnum = "".join(ch for ch in (t or "") if ch.isdigit())
        return 8 <= len(tnum) <= 15
    if telefono_enc and not _tel_ok(telefono_enc):
        st.info("Formato sugerido: solo números, 10 dígitos en MX (ej. 5551234567).")

    PRECIO_KILO = 22
    kilos = st.number_input("Kilos pesados (ropa por kilo)", min_value=0.0, step=0.1, key=key_for("kg_encargo_live"))

    with st.expander("➕ Servicios adicionales (opcional)", expanded=False):
        st.subheader("🙌 Servicios adicionales")

        st.markdown("**Edredón / Cobertor (por pieza)**")
        col_e1, col_e2, col_e3 = st.columns(3)
        edre_ind = col_e1.number_input("Individual ($80) — piezas", min_value=0, step=1, key=key_for("edre_ind_live"))
        edre_mat = col_e2.number_input("Matrimonial ($85) — piezas", min_value=0, step=1, key=key_for("edre_mat_live"))
        edre_ks  = col_e3.number_input("King Size ($95) — piezas", min_value=0, step=1, key=key_for("edre_ks_live"))

        st.markdown("**Colcha (por pieza)**")
        col_c1, col_c2, col_c3 = st.columns(3)
        colcha_ind = col_c1.number_input("Individual ($75) — piezas", min_value=0, step=1, key=key_for("colcha_ind_live"))
        colcha_mat = col_c2.number_input("Matrimonial ($80) — piezas", min_value=0, step=1, key=key_for("colcha_mat_live"))
        colcha_ks  = col_c3.number_input("King Size ($85) — piezas", min_value=0, step=1, key=key_for("colcha_ks_live"))

        st.markdown("**Manteles (por kilo)**")
        kilos_manteles = st.number_input("Kilos de manteles ($40/kg)", min_value=0.0, step=0.1, key=key_for("manteles_kg_live"))

        st.markdown("**Almohada / Peluches (precio manual)**")
        col_a1, col_a2 = st.columns(2)
        alm_pzas = col_a1.number_input("Cantidad de piezas", min_value=0, step=1, key=key_for("alm_pzas_live"))
        alm_precio_unit = col_a2.number_input("Precio unitario (manual)", min_value=0.0, step=1.0, key=key_for("alm_precio_live"))

    with st.expander("🧪 Otros (productos sueltos)", expanded=False):
        if "otros_encargo_live" not in st.session_state:
            st.session_state.otros_encargo_live = {}
        otros_temp = {}
        for prod, precio in otros_catalogo.items():
            key = key_for(f"otros_enc_live_{prod.replace(' ', '_')}")
            cant = st.number_input(f"{prod} (${precio})", min_value=0, step=1, key=key)
            if cant > 0:
                otros_temp[prod] = cant
        st.session_state.otros_encargo_live = otros_temp

    precios_edredon = {"Individual": 80, "Matrimonial": 85, "King Size": 95}
    precios_colcha  = {"Individual": 75, "Matrimonial": 80, "King Size": 85}

    # Subtotales "raw"
    subtotal_kilos     = round((kilos or 0) * PRECIO_KILO, 2)
    subtotal_edredon   = edre_ind*precios_edredon["Individual"] + edre_mat*precios_edredon["Matrimonial"] + edre_ks*precios_edredon["King Size"]
    subtotal_colcha    = colcha_ind*precios_colcha["Individual"]  + colcha_mat*precios_colcha["Matrimonial"]  + colcha_ks*precios_colcha["King Size"]
    subtotal_manteles  = (kilos_manteles or 0) * 40
    subtotal_almohada  = (alm_pzas or 0) * (alm_precio_unit or 0)
    total_servicios_raw = round(subtotal_edredon + subtotal_colcha + subtotal_manteles + subtotal_almohada, 2)
    subtotal_otros_enc = sum(otros_catalogo[p]*c for p, c in (st.session_state.otros_encargo_live or {}).items())

    # Ceil por partes y total (para BD y presentación)
    total_kilos_ce      = ceil_pesos(subtotal_kilos)
    total_servicios_ce  = ceil_pesos(total_servicios_raw)
    otros_importe_ce    = ceil_pesos(subtotal_otros_enc)
    total_enc_ce        = ceil_pesos(total_kilos_ce + total_servicios_ce + otros_importe_ce)

    st.write("---")
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    col_t1.metric("Ropa por kilo", f"${total_kilos_ce:,.2f}")
    col_t2.metric("Servicios adicionales", f"${total_servicios_ce:,.2f}")
    col_t3.metric("Otros", f"${otros_importe_ce:,.2f}")
    col_t4.metric("TOTAL encargo", f"${total_enc_ce:,.2f}")

    pago_estado = st.radio("Estado del pago", ["Pagado", "Pendiente"], horizontal=True, index=1, key=key_for("estado_pago_encargo_live"))
    dinero_recibido = 0.0
    cambio_enc_ce = 0.0
    if pago_estado == "Pagado":
        dinero_recibido = st.number_input("💳 ¿Con cuánto paga?", min_value=0.0, step=1.0, key=key_for("dinero_recibido_enc_live"))
        cambio_enc_ce = ceil_pesos(max(dinero_recibido - total_enc_ce, 0.0))
        st.markdown(f"**💵 Cambio a entregar: ${cambio_enc_ce:,.2f}**")
        #st.caption("El cambio se calcula contra el total ceileado.")

    def hay_servicios():
        return any([
            edre_ind, edre_mat, edre_ks,
            colcha_ind, colcha_mat, colcha_ks,
            (kilos_manteles or 0) > 0,
            (alm_pzas or 0) > 0 and (alm_precio_unit or 0) > 0
        ])

    st.write("---")
    if st.button("✅ Registrar encargo", key=key_for("btn_registrar_encargo")):
        if not st.session_state.vendedor.strip():
            st.warning("Ingresa el nombre del vendedor.")
        elif not (cliente_enc or "").strip():
            st.warning("Ingresa el nombre del cliente.")
        elif not (telefono_enc or "").strip():
            st.warning("Ingresa el teléfono del cliente.")
        elif not _tel_ok(telefono_enc):
            st.warning("El teléfono debe tener entre 8 y 15 dígitos (solo números).")
        elif (kilos <= 0) and (not hay_servicios()) and (not st.session_state.otros_encargo_live):
            st.warning("Agrega kilos, un servicio adicional o algún producto en 'Otros'.")
        elif pago_estado == "Pagado" and dinero_recibido < total_enc_ce:
            st.error(f"El monto recibido (${ceil_pesos(dinero_recibido):,.2f}) no cubre el total (${total_enc_ce:,.2f}.")
        else:
            try:
                if pago_estado == "Pagado":
                    dinero_db = float(dinero_recibido)           # lo guardamos tal cual lo ingresas
                    cambio_db = float(cambio_enc_ce)             # ceileado
                    pago_fecha = datetime.now(timezone("America/Mexico_City")).isoformat()
                else:
                    dinero_db = 0.0
                    cambio_db = 0.0
                    pago_fecha = None

                servicios_especiales = {}
                if hay_servicios():
                    servicios_especiales = {
                        "edredon_cobertor": {
                            "piezas": {
                                "Individual": int(edre_ind),
                                "Matrimonial": int(edre_mat),
                                "King Size": int(edre_ks)
                            },
                            "subtotal": float(ceil_pesos(subtotal_edredon)),
                        },
                        "colcha": {
                            "piezas": {
                                "Individual": int(colcha_ind),
                                "Matrimonial": int(colcha_mat),
                                "King Size": int(colcha_ks)
                            },
                            "subtotal": float(ceil_pesos(subtotal_colcha)),
                        },
                        "manteles": {"kilos": float(kilos_manteles or 0), "subtotal": float(ceil_pesos(subtotal_manteles))},
                        "almohada_peluches": {"cantidad": int(alm_pzas or 0), "subtotal": float(ceil_pesos(subtotal_almohada))},
                        "total_servicios": float(total_servicios_ce),
                    }

                data = {
                    "fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                    "vendedor": st.session_state.vendedor.strip(),
                    "cliente": (cliente_enc or "").strip(),
                    "telefono": (telefono_enc or "").strip(),
                    "kilos": float(kilos or 0),
                    "total_kilos": float(total_kilos_ce),
                    "total_servicios": float(total_servicios_ce),
                    "otros": {k: int(v) for k, v in (st.session_state.otros_encargo_live or {}).items() },
                    "otros_importe": float(otros_importe_ce),
                    "total": float(total_enc_ce),
                    "dinero": float(dinero_db),
                    "cambio": float(cambio_db),
                    "estado": "En espera",
                    "uso_lavadoras": {},
                    "uso_secadoras": {},
                    "detergentes_usados": {},
                    "bolsas_usadas": {},
                    "servicios_especiales": servicios_especiales if servicios_especiales else {},
                    "pago_estado": pago_estado,
                    "pago_fecha": pago_fecha
                }
                supabase.table("encargos_kilos").insert(data).execute()
                st.success("✅ Encargo registrado.")

                reset_encargo_widgets()
                st.rerun()

            except Exception as e:
                st.error(f"Error al guardar el encargo: {e}")

# ========================
# ===== VER ENCARGOS  ====
# ========================
elif menu == "Ver encargos":
    st.header("📋 Encargos (kilos)")

    if st.session_state.get("reset_after_save") and st.session_state.get("last_saved_id"):
        enc_id = str(st.session_state["last_saved_id"])
        for prefix in ["lav16_", "lav9_", "lav4_", "sec15_", "sec30_", "detj_", "dets_", "detd_", "bolc_", "bolm_", "bolg_", "pago_"]:
            st.session_state.pop(prefix + enc_id, None)
        st.session_state["encargo_selector"] = "— Selecciona —"
        st.session_state["reset_after_save"] = False
        st.session_state["last_saved_id"] = None

    st.subheader("📆 Filtrar encargos por rango de fechas")
    start_date_e = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="enc_start")
    end_date_e = st.date_input("Fecha fin", value=date.today(), key="enc_end")

    estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "En espera", "Entregado"])

    def _prune_servicios(d):
        if not isinstance(d, dict):
            return {}
        out = {}
        ec = d.get("edredon_cobertor", {})
        piezas = _prune_zeros_simple(ec.get("piezas", {}))
        subtotal_ec = float(ec.get("subtotal", 0) or 0)
        if piezas or subtotal_ec > 0:
            ent = {}
            if piezas: ent["piezas"] = piezas
            if subtotal_ec > 0: ent["subtotal"] = subtotal_ec
            out["edredon_cobertor"] = ent
        co = d.get("colcha", {})
        piezas = _prune_zeros_simple(co.get("piezas", {}))
        subtotal_co = float(co.get("subtotal", 0) or 0)
        if piezas or subtotal_co > 0:
            ent = {}
            if piezas: ent["piezas"] = piezas
            if subtotal_co > 0: ent["subtotal"] = subtotal_co
            out["colcha"] = ent
        ma = d.get("manteles", {})
        kilos = float(ma.get("kilos", 0) or 0)
        subtotal_ma = float(ma.get("subtotal", 0) or 0)
        if kilos > 0 or subtotal_ma > 0:
            ent = {}
            if kilos > 0: ent["kilos"] = kilos
            if subtotal_ma > 0: ent["subtotal"] = subtotal_ma
            out["manteles"] = ent
        ap = d.get("almohada_peluches", {})
        cant = int(ap.get("cantidad", 0) or 0)
        subtotal_ap = float(ap.get("subtotal", 0) or 0)
        if cant > 0 or subtotal_ap > 0:
            ent = {}
            if cant > 0: ent["cantidad"] = cant
            if subtotal_ap > 0: ent["subtotal"] = subtotal_ap
            out["almohada_peluches"] = ent
        ts = float(d.get("total_servicios", 0) or 0)
        if ts > 0:
            out["total_servicios"] = ts
        return out

    try:
        response = supabase.table("encargos_kilos").select("*").order("fecha", desc=True).execute()
        registros_e = response.data

        if registros_e:
            df_e = pd.DataFrame(registros_e)
            if "fecha" in df_e.columns:
                df_e["fecha"] = pd.to_datetime(df_e["fecha"]).dt.tz_localize(None)

            mask_e = (df_e["fecha"] >= pd.to_datetime(start_date_e)) & (df_e["fecha"] < pd.to_datetime(end_date_e) + pd.Timedelta(days=1))
            df_e = df_e.loc[mask_e].copy()

            if estado_filtro != "Todos" and "estado" in df_e.columns:
                df_e = df_e[df_e["estado"] == estado_filtro]

            # asegurar dinero numérico
            for colm in ["total", "dinero", "cambio", "total_kilos", "total_servicios", "otros_importe"]:
                if colm in df_e.columns:
                    df_e[colm] = pd.to_numeric(df_e[colm], errors="coerce").fillna(0.0)
                else:
                    df_e[colm] = 0.0

            # Vista ceileada
            df_e_display = df_e.copy()
            money_cols_e = ["total", "dinero", "cambio", "total_kilos", "total_servicios", "otros_importe"]
            df_e_display = ceil_cols_df(df_e_display, money_cols_e)

            for col in ["uso_lavadoras", "uso_secadoras", "detergentes_usados", "bolsas_usadas", "otros"]:
                if col in df_e_display.columns:
                    df_e_display[col] = df_e_display[col].apply(_prune_zeros_simple)
            if "servicios_especiales" in df_e_display.columns:
                df_e_display["servicios_especiales"] = df_e_display["servicios_especiales"].apply(_prune_servicios)

            columnas_en_orden = [
                "id", "fecha", "vendedor", "cliente", "telefono",
                "kilos", "total_kilos", "total_servicios", "otros_importe", "total",
                "dinero", "cambio", "estado", "pago_estado", "pago_fecha",
                "servicios_especiales", "uso_lavadoras", "uso_secadoras",
                "detergentes_usados", "bolsas_usadas", "otros",
            ]
            cols_visibles = [c for c in columnas_en_orden if c in df_e_display.columns]
            cols_extra = [c for c in df_e_display.columns if c not in cols_visibles]
            df_e_display = df_e_display[cols_visibles + cols_extra]

            st.dataframe(
                df_e_display,
                use_container_width=True,
                column_config={
                    "total_kilos": money_col("Kilos (encargos)"),
                    "total_servicios": money_col("Servicios"),
                    "otros_importe": money_col("Otros"),
                    "total": money_col("Total"),
                    "dinero": money_col("Dinero recibido"),
                    "cambio": money_col("Cambio"),
                }
            )

            st.subheader("📊 Totales de encargos del período")
            total_importe = float(df_e["total"].sum()) if "total" in df_e.columns else 0.0
            total_kilos = float(df_e["kilos"].sum()) if "kilos" in df_e.columns else 0.0
            cantidad_enc = int(len(df_e))
            st.markdown(f"**Kilos totales (peso):** {total_kilos:.2f} kg")
            st.markdown(f"**Cantidad de encargos:** {cantidad_enc}")
            st.markdown(f"**Total del período:** ${ceil_pesos(total_importe):,.2f}")

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

                    def init_key(key, default_val):
                        if key not in st.session_state:
                            st.session_state[key] = default_val

                    init_key(k_lav16, int((uso_lav or {}).get("Lavadora 16 kg", 0)))
                    init_key(k_lav9,  int((uso_lav or {}).get("Lavadora 9 kg",  0)))
                    init_key(k_lav4,  int((uso_lav or {}).get("Lavadora 4 kg",  0)))
                    init_key(k_sec15, int((uso_sec or {}).get("Secadora 9 kg (15 minutos)", 0)))
                    # 👇 Mostrar en UI tandas de 30 min (si en BD hay '2', aquí verás '1')
                    init_key(k_sec30, int((uso_sec or {}).get("Secadora 9 kg (30 minutos)", 0)) // 2)
                    init_key(k_det_j, int((det_us  or {}).get("1 medida de jabón", 0)))
                    init_key(k_det_s, int((det_us  or {}).get("1 medida de suavizante", 0)))
                    init_key(k_det_d, int((det_us  or {}).get("1 medida de desmugrante", 0)))
                    init_key(k_bol_c, int((bol_us  or {}).get("1 bolsa chica",   0)))
                    init_key(k_bol_m, int((bol_us  or {}).get("1 bolsa mediana", 0)))
                    init_key(k_bol_g, int((bol_us  or {}).get("1 bolsa grande",  0)))
                    init_key(k_pago,  0.0)

                    st.markdown("**Lavadoras usadas**")
                    colL1, colL2, colL3 = st.columns(3)
                    lav16 = colL1.number_input("Lavadora 16 kg (cantidad)", min_value=0, step=1, key=k_lav16)
                    lav9  = colL2.number_input("Lavadora 9 kg (cantidad)",  min_value=0, step=1, key=k_lav9)
                    lav4  = colL3.number_input("Lavadora 4 kg (cantidad)",  min_value=0, step=1, key=k_lav4)

                    st.markdown("**Secadoras usadas**")
                    colS1, colS2 = st.columns(2)
                    sec15 = colS1.number_input("Secadora 9 kg (15 min)", min_value=0, step=1, key=k_sec15)
                    sec30 = colS2.number_input("Secadora 9 kg (30 min)", min_value=0, step=1, key=k_sec30)

                    st.markdown("**Detergentes usados**")
                    colD1, colD2, colD3 = st.columns(3)
                    det_jabon = colD1.number_input("Medidas de jabón",       min_value=0, step=1, key=k_det_j)
                    det_suav  = colD2.number_input("Medidas de suavizante",  min_value=0, step=1, key=k_det_s)
                    det_desm  = colD3.number_input("Medidas de desmugrante", min_value=0, step=1, key=k_det_d)

                    st.markdown("**Bolsas usadas**")
                    colB1, colB2, colB3 = st.columns(3)
                    bol_ch = colB1.number_input("Bolsas chicas",   min_value=0, step=1, key=k_bol_c)
                    bol_md = colB2.number_input("Bolsas medianas", min_value=0, step=1, key=k_bol_m)
                    bol_gr = colB3.number_input("Bolsas grandes",  min_value=0, step=1, key=k_bol_g)

                    st.write("---")
                    total_encargo_bd = float(encargo_row.get("total", 0.0))  # debería venir ya ceileado para nuevos
                    pago_estado_actual = (encargo_row.get("pago_estado") or "Pendiente")
                    st.markdown(f"**Estado de pago actual:** {pago_estado_actual} | **Total:** ${ceil_pesos(total_encargo_bd):,.2f}")

                    dinero_cobrar = 0.0
                    if pago_estado_actual == "Pendiente":
                        dinero_cobrar = st.number_input("💳 Monto recibido ahora", min_value=0.0, step=1.0, value=st.session_state.get(k_pago, 0.0), key=k_pago)
                        cambio_preview = ceil_pesos(max(dinero_cobrar - ceil_pesos(total_encargo_bd), 0.0))
                        st.markdown(f"**💵 Cambio a entregar (previo):** ${cambio_preview:,.2f}")
                        #st.caption("Se calcula contra el total ceileado en BD.")

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
                                    # 👇 Guardar doble en BD por cada tanda de 30 minutos
                                    "Secadora 9 kg (30 minutos)": int(st.session_state[k_sec30]) * 2,
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

                            if pago_estado_actual == "Pendiente" and dinero_cobrar > 0:
                                recibido = float(dinero_cobrar)  # se guarda tal cual
                                total_enc_ce = ceil_pesos(total_encargo_bd)
                                nuevo_cambio_ce = ceil_pesos(max(recibido - total_enc_ce, 0.0))
                                update_data.update({
                                    "pago_estado": "Pagado" if recibido >= total_enc_ce else "Pendiente",
                                    "pago_fecha": datetime.now(timezone("America/Mexico_City")).isoformat(),
                                    "dinero": recibido,
                                    "cambio": float(nuevo_cambio_ce),
                                })

                            supabase.table("encargos_kilos").update(update_data).eq("id", int(encargo_id_sel)).execute()

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
                            st.session_state["last_saved_id"] = encargo_id_sel
                            st.session_state["reset_after_save"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar el encargo: {e}")
            else:
                st.info("No hay encargos para editar en el rango/estado seleccionado.")

            st.subheader("📥 Descargar reporte (encargos)")
            csv_e = df_e_display.to_csv(index=False).encode("utf-8")
            st.download_button("📁 Descargar CSV (encargos)", data=csv_e, file_name="reporte_encargos_filtrado.csv", mime="text/csv")

            try:
                output_e = BytesIO()
                with pd.ExcelWriter(output_e, engine="xlsxwriter") as writer:
                    df_e_display.to_excel(writer, index=False, sheet_name="Encargos")
                st.download_button("📊 Descargar Excel (encargos)", data=output_e.getvalue(),
                                   file_name="reporte_encargos_filtrado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Para exportar a Excel en la nube, agrega 'XlsxWriter'.")
        else:
            st.info("Aún no hay encargos registrados.")
    except Exception as e:
        st.error(f"Error al obtener los encargos: {e}")

# ============================
# ===== RESUMEN DE USO =======
# ============================
elif menu == "Resumen de uso":
    st.header("📊 Resumen de uso — Ventas vs Encargos")

    st.subheader("📆 Selecciona rango de fechas")
    start_date_u = st.date_input("Fecha inicio", value=date.today().replace(day=1), key="uso_start")
    end_date_u = st.date_input("Fecha fin", value=date.today(), key="uso_end")
    #st.caption("El cálculo se hace al vuelo a partir de las tablas. No se guarda nada en la base de datos.")

    try:
        ventas = supabase.table("ventas").select("*").order("fecha", desc=True).execute().data or []
        df_v = pd.DataFrame(ventas) if ventas else pd.DataFrame()
        if not df_v.empty and "fecha" in df_v.columns:
            df_v["fecha"] = pd.to_datetime(df_v["fecha"]).dt.tz_localize(None)
            mask_v = (df_v["fecha"] >= pd.to_datetime(start_date_u)) & (df_v["fecha"] < pd.to_datetime(end_date_u) + pd.Timedelta(days=1))
            df_v = df_v.loc[mask_v]

        cnt_lav_v = sumar_dicts_en_col(df_v["lavadoras"]) if "lavadoras" in df_v.columns else Counter()
        cnt_sec_v = sumar_dicts_en_col(df_v["secadoras"]) if "secadoras" in df_v.columns else Counter()
        cnt_det_v = sumar_dicts_en_col(df_v["detergentes"]) if "detergentes" in df_v.columns else Counter()
        cnt_bol_v = sumar_dicts_en_col(df_v["bolsas"]) if "bolsas" in df_v.columns else Counter()
        cnt_ot_v  = sumar_dicts_en_col(df_v["otros"]) if "otros" in df_v.columns else Counter()

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
        cnt_ot_e  = sumar_dicts_en_col(df_eu["otros"]) if not df_eu.empty and "otros" in df_eu.columns else Counter()

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

        items_lav = ["Lavadora 16 kg", "Lavadora 9 kg", "Lavadora 4 kg"]
        items_sec = ["Secadora 9 kg (15 minutos)", "Secadora 9 kg (30 minutos)", "Secado"]
        items_det = ["1 medida de jabón", "1 medida de suavizante", "1 medida de desmugrante"]
        items_bol = ["1 bolsa chica", "1 bolsa mediana", "1 bolsa grande"]
        items_ot  = list(otros_catalogo.keys())

        df_lav = make_df("🧺 Lavadoras", items=items_lav, cnt_v=cnt_lav_v, cnt_e=cnt_lav_e)
        df_sec = make_df("🔥 Secadoras",  items=items_sec, cnt_v=cnt_sec_v, cnt_e=cnt_sec_e)
        df_det = make_df("🧴 Detergentes",items=items_det, cnt_v=cnt_det_v, cnt_e=cnt_det_e)
        df_bol = make_df("🛍️ Bolsas",    items=items_bol, cnt_v=cnt_bol_v, cnt_e=cnt_bol_e)
        df_ot  = make_df("🧪 Otros",      items=items_ot,  cnt_v=cnt_ot_v,  cnt_e=cnt_ot_e)

        st.write("---")
        colA, colB, colC = st.columns(3)
        colA.metric("🔧 Total por ventas",
                    int(df_lav["Por ventas"].sum() + df_sec["Por ventas"].sum() + df_det["Por ventas"].sum() + df_bol["Por ventas"].sum() + df_ot["Por ventas"].sum()))
        colB.metric("📦 Total por encargos",
                    int(df_lav["Por encargos"].sum() + df_sec["Por encargos"].sum() + df_det["Por encargos"].sum() + df_bol["Por encargos"].sum() + df_ot["Por encargos"].sum()))
        colC.metric("🧮 Total general",
                    int(df_lav["Total"].sum() + df_sec["Total"].sum() + df_det["Total"].sum() + df_bol["Total"].sum() + df_ot["Total"].sum()))

        st.write("---")
        st.subheader("📥 Descargar CSV (resumen de uso: ventas vs encargos)")
        df_export = pd.concat([
            df_lav.assign(Categoría="Lavadoras"),
            df_sec.assign(Categoría="Secadoras"),
            df_det.assign(Categoría="Detergentes"),
            df_bol.assign(Categoría="Bolsas"),
            df_ot.assign(Categoría="Otros"),
        ], axis=0)[["Categoría", "Ítem", "Por ventas", "Por encargos", "Total"]]
        csv_export = df_export.to_csv(index=False).encode("utf-8")
        st.download_button("📁 Descargar CSV (uso por ítem)", data=csv_export, file_name="resumen_uso_ventas_encargos.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Error al generar el resumen: {e}")

# ===========================
# ===== ADMINISTRACIÓN  =====
# ===========================
elif menu == "Administración":
    st.header("💼 Administración — Ingresos por día, semana y mes")

    st.subheader("📆 Rango de análisis")
    col_r1, col_r2 = st.columns(2)
    fecha_ini = col_r1.date_input("Fecha inicio", value=date.today().replace(day=1), key="adm_start")
    fecha_fin = col_r2.date_input("Fecha fin", value=date.today(), key="adm_end")
    st.caption("Resumen general de ventas y encargos.")

    def _prep(df, tipo):
        # Estructura homogénea
        base_cols = ["fecha","tipo","total_ingreso","kilos_importe","servicios_importe","otros_importe"]
        if df is None or df.empty:
            return pd.DataFrame(columns=base_cols)

        df = df.copy()
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
        mask = (df["fecha"] >= pd.to_datetime(fecha_ini)) & (df["fecha"] < pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df = df.loc[mask]

        if df.empty:
            return pd.DataFrame(columns=base_cols)

        # Helper: siempre devuelve una Serie alineada con el índice
        def serie_num(col_name):
            if col_name in df.columns:
                return pd.to_numeric(df[col_name], errors="coerce")
            else:
                return pd.Series(0.0, index=df.index, dtype="float64")

        # Numéricos base (en crudo)
        df["total_ingreso"]     = serie_num("total").fillna(0.0)
        df["kilos_importe"]     = serie_num("total_kilos").fillna(0.0)
        df["servicios_importe"] = serie_num("total_servicios").fillna(0.0)

        # Otros: tolerante a tipos y ausencia de columna
        if "otros_importe" in df.columns:
            df["otros_importe"] = pd.to_numeric(df["otros_importe"], errors="coerce").fillna(0.0)
        elif "otros" in df.columns:
            otros_series = df["otros"].apply(lambda x: x if isinstance(x, dict) else {})
            df["otros_importe"] = otros_series.apply(subtotal_otros).astype(float)
        else:
            df["otros_importe"] = pd.Series(0.0, index=df.index, dtype="float64")

        df["tipo"] = tipo
        return df[base_cols]

    try:
        ventas = supabase.table("ventas").select("*").order("fecha", desc=True).execute().data or []
        df_v = pd.DataFrame(ventas) if ventas else pd.DataFrame()
        df_v2 = _prep(df_v, "Venta")

        encargos = supabase.table("encargos_kilos").select("*").order("fecha", desc=True).execute().data or []
        df_e = pd.DataFrame(encargos) if encargos else pd.DataFrame()
        df_e2 = _prep(df_e, "Encargo")

        df_all = pd.concat([df_v2, df_e2], ignore_index=True)

        if df_all.empty:
            st.info("No hay movimientos en el rango seleccionado.")
        else:
            # Etiquetas de periodo
            df_all["día"] = df_all["fecha"].dt.date
            iso = df_all["fecha"].dt.isocalendar()
            df_all["semana"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
            df_all["mes"] = df_all["fecha"].dt.to_period("M").astype(str)

            # ===== Columnas derivadas (6 apartados) =====
            # Ventas (sin otros) y Otros (ventas)
            df_all["ventas_sin_otros"]    = df_all.apply(lambda r: max((r["total_ingreso"] - r["otros_importe"]), 0.0) if r["tipo"]=="Venta" else 0.0, axis=1)
            df_all["otros_ventas_only"]   = df_all.apply(lambda r: r["otros_importe"] if r["tipo"]=="Venta"   else 0.0, axis=1)
            # Encargos desglosado: Kilos, Servicios, Otros
            df_all["kilos_only"]          = df_all.apply(lambda r: r["kilos_importe"]     if r["tipo"]=="Encargo" else 0.0, axis=1)
            df_all["servicios_only"]      = df_all.apply(lambda r: r["servicios_importe"] if r["tipo"]=="Encargo" else 0.0, axis=1)
            df_all["otros_encargos_only"] = df_all.apply(lambda r: r["otros_importe"]     if r["tipo"]=="Encargo" else 0.0, axis=1)

            # ===== Métricas de rango (6 apartados) =====
            ingreso_total_rango = float(df_all["total_ingreso"].sum())
            ventas_sin_otros_rg = float(df_all["ventas_sin_otros"].sum())
            otros_ventas_rango  = float(df_all["otros_ventas_only"].sum())
            kilos_rango         = float(df_all["kilos_only"].sum())
            servicios_rango     = float(df_all["servicios_only"].sum())
            otros_enc_rango     = float(df_all["otros_encargos_only"].sum())

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Ingreso total (rango)",  f"${ceil_pesos(ingreso_total_rango):,.2f}")
            c2.metric("Ventas (sin otros)",     f"${ceil_pesos(ventas_sin_otros_rg):,.2f}")
            c3.metric("Otros (ventas)",         f"${ceil_pesos(otros_ventas_rango):,.2f}")
            c4.metric("Kilos (encargos)",       f"${ceil_pesos(kilos_rango):,.2f}")
            c5.metric("Servicios (encargos)",   f"${ceil_pesos(servicios_rango):,.2f}")
            c6.metric("Otros (en encargo)",     f"${ceil_pesos(otros_enc_rango):,.2f}")

            st.write("---")

            def cuadro_agrupado(label_periodo, col_periodo):
                st.subheader(f"📈 Ingresos por {label_periodo}")

                # Sumas por periodo (en crudo); ceileamos para vista/export
                base = df_all.groupby(col_periodo, as_index=False).agg(
                    ingreso_total=("total_ingreso","sum"),
                    ventas_sin_otros=("ventas_sin_otros","sum"),
                    otros_ventas_only=("otros_ventas_only","sum"),
                    kilos_only=("kilos_only","sum"),
                    servicios_only=("servicios_only","sum"),
                    otros_encargos_only=("otros_encargos_only","sum"),
                )

                # Orden temporal amigable
                if col_periodo == "día":
                    base = base.sort_values(by="día")
                elif col_periodo == "semana":
                    week_num = base["semana"].str[-2:].astype(int)
                    year_num = base["semana"].str[:4].astype(int)
                    approx = pd.to_datetime(year_num.astype(str) + "-01-04") + pd.to_timedelta((week_num-1)*7, unit="D")
                    base = base.assign(_ord=approx).sort_values("_ord").drop(columns=["_ord"])
                else:
                    base = base.assign(_ord=pd.to_datetime(base["mes"] + "-01")).sort_values("_ord").drop(columns=["_ord"])

                # Ceil para vista/export
                money_cols_admin = [
                    "ingreso_total","ventas_sin_otros","otros_ventas_only",
                    "kilos_only","servicios_only","otros_encargos_only"
                ]
                base = ceil_cols_df(base, money_cols_admin)

                # Mostrar tabla con los 6 apartados
                desired_cols = [
                    col_periodo,
                    "ingreso_total",
                    "ventas_sin_otros",
                    "otros_ventas_only",
                    "kilos_only",
                    "servicios_only",
                    "otros_encargos_only",
                ]
                base = base[[c for c in desired_cols if c in base.columns]]

                st.dataframe(
                    base,
                    use_container_width=True,
                    column_config={
                        "ingreso_total":       money_col("Ingreso total"),
                        "ventas_sin_otros":    money_col("Ventas (sin otros)"),
                        "otros_ventas_only":   money_col("Otros (ventas)"),
                        "kilos_only":          money_col("Kilos (encargos)"),
                        "servicios_only":      money_col("Servicios (encargos)"),
                        "otros_encargos_only": money_col("Otros (en encargo)"),
                    }
                )

                # Export CSV del resumen
                csv_bytes = base.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"📁 Descargar CSV — {label_periodo}",
                    data=csv_bytes,
                    file_name=f"administracion_{label_periodo.lower()}.csv",
                    mime="text/csv"
                )

                # Métricas del último periodo (si existe)
                if not base.empty:
                    ult = base.tail(1).iloc[0]
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric(f"Último {label_periodo} — Ingreso total",      f"${ceil_pesos(ult['ingreso_total']):,.2f}")
                    c2.metric(f"Último {label_periodo} — Ventas (sin otros)", f"${ceil_pesos(ult['ventas_sin_otros']):,.2f}")
                    c3.metric(f"Último {label_periodo} — Otros (ventas)",     f"${ceil_pesos(ult['otros_ventas_only']):,.2f}")
                    c4.metric(f"Último {label_periodo} — Kilos",              f"${ceil_pesos(ult['kilos_only']):,.2f}")
                    c5.metric(f"Último {label_periodo} — Servicios",          f"${ceil_pesos(ult['servicios_only']):,.2f}")
                    c6.metric(f"Último {label_periodo} — Otros (encargo)",    f"${ceil_pesos(ult['otros_encargos_only']):,.2f}")

                st.write("---")

            cuadro_agrupado("día", "día")
            cuadro_agrupado("semana", "semana")
            cuadro_agrupado("mes", "mes")

    except Exception as e:
        st.error(f"Error al calcular la administración: {e}")

# ========== ADMIN ==========
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



