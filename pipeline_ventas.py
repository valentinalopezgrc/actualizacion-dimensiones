# =============================================================================
# PIPELINE: ACTUALIZACIÓN DE LA TABLA DE HECHOS (VentasFact) - MySQL
# =============================================================================
# Basado en pipeline_erp.py del profe (clase 2026-09-22), adaptado a MySQL.
#
# IMPORTANTE: este pipeline se corre DESPUÉS de los de las dimensiones.
# Una venta solo se puede cargar si su cliente, tienda y producto ya existen
# (llaves foráneas). Si llega una venta de un cliente nuevo y todavía no se ha
# corrido pipeline_cliente.py, esa venta se descarta.
# =============================================================================

import os
from dotenv import load_dotenv
from utils.reglas import calcular_valor_venta, eliminar_duplicados, eliminar_espacios, formato_fecha, leer_archivos_csv, renombrar_columnas, conversion_mayusculas
from db_utils.load import cargar_datos_en_db, preparar_datos_para_carga

load_dotenv()

ruta_archivos = os.getenv("RUTA_ARCHIVOS", "csvs")


# ------------------------------------------------------------------ EXTRAER
# Lee todos los CSV de ventas de la carpeta csvs/ventas
datos_ventas = leer_archivos_csv(os.path.join(ruta_archivos, "ventas"))
print(f"Registros leídos del archivo: {len(datos_ventas)}")


# -------------------------------------------------------------- TRANSFORMAR
mapeo_columnas = {
    "FECHA_VTA": "Fecha",
    "COD_PRODUCTO": "ProductoID",
    "CANTIDAD": "Unidades",
    "PRECIO_COP": "PrecioUnitario",
    "DESCUENTO_PCT": "Descuento",
    "COD_CLIENTE": "ClienteID",
    "COD_TIENDA": "TiendaID"
}
datos_ventas = renombrar_columnas(datos_ventas, mapeo_columnas)

columnas = ["Fecha", "ProductoID", "Unidades", "PrecioUnitario", "Descuento", "ClienteID", "TiendaID"]

# Limpiar espacios y mayúsculas ANTES de buscar duplicados, para que " t01 " y
# "T01" se reconozcan como la misma tienda
datos_ventas = eliminar_espacios(datos_ventas, ["ProductoID", "ClienteID", "TiendaID"])
datos_ventas = conversion_mayusculas(datos_ventas, ["ProductoID", "ClienteID", "TiendaID"])

datos_ventas = eliminar_duplicados(datos_ventas, columnas)

# CORRECCIÓN respecto al código de clase: la fecha viene en formato colombiano
# dd/mm/aaaa. Sin decirle el formato, pandas lee "03/01/2024" como 1 de marzo
# (formato gringo mes/día) en vez de 3 de enero.
datos_ventas = formato_fecha(datos_ventas, "Fecha", "%Y-%m-%d", formato_entrada="%d/%m/%Y")

# Descuento de porcentaje a fracción (5 -> 0.05) y ValorVenta = Unidades x Precio x (1 - Descuento)
datos_ventas = calcular_valor_venta(datos_ventas)

print(f"Registros válidos después de transformar: {len(datos_ventas)}")


# ------------------------------------------------------------------- CARGAR
# preparar_datos_para_carga: crea FechaID, valida contra las dimensiones,
# quita las ventas ya cargadas y genera los VentaID consecutivos
datos_a_cargar = preparar_datos_para_carga(datos_ventas)

insertados = cargar_datos_en_db(datos_a_cargar)

print(f"VentasFact -> ventas nuevas cargadas: {insertados}")
