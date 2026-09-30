# =============================================================================
# Ejecuta todos los pipelines en el orden correcto:
#   0. Carga inicial (llena las tablas vacías con los datos de DataCaos)
#   1. Dimensiones (cliente, tienda, producto)
#   2. Tabla de hechos (ventas)
# El orden importa: una venta solo se puede cargar si su cliente, tienda y
# producto ya existen en las dimensiones (llaves foráneas).
# =============================================================================
import runpy

for archivo in ["carga_inicial.py", "pipeline_cliente.py", "pipeline_tienda.py", "pipeline_producto.py", "pipeline_ventas.py"]:
    print(f"\n===== {archivo} =====")
    runpy.run_path(archivo)   # ejecuta el archivo como si se corriera con "python archivo.py"
