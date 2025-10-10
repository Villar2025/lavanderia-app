from supabase import create_client

# 🔗 Conexión a tu Supabase
SUPABASE_URL = "https://bempjrdqahqqjulatlcb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJlbXBqcmRxYWhxcWp1bGF0bGNiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4NjMyMzEsImV4cCI6MjA3NTQzOTIzMX0.qrx-H5c5mdKJP8RnHoyiETwmbBgx1Yvc8yGmW3NiuiU"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def reiniciar_tabla_ventas():
    try:
        # 🔥 Elimina TODAS las filas
        response = supabase.table("ventas").delete().neq("id", 0).execute()

        print("✅ Base de datos 'ventas' limpiada con éxito.")
        print(f"Filas eliminadas: {len(response.data) if response.data else 0}")

    except Exception as e:
        print("❌ Error al reiniciar la tabla:", e)

reiniciar_tabla_ventas()