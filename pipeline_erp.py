import os
import pandas as pd
from dotenv import load_dotenv
from utils.reglas import calcular_valor_venta, eliminar_duplicados, eliminar_espacios, formato_fecha, leer_archivos_csv, renombrar_columnas,conversion_mayusculas
from db_utils.load import cargar_datos_en_db, preparar_datos_para_carga

load_dotenv()

ruta_archivos = os.getenv("RUTA_ARCHIVOS", "csvs")


datos_ventas = leer_archivos_csv(ruta_archivos)

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

datos_ventas = eliminar_duplicados(datos_ventas, columnas)

datos_ventas = formato_fecha(datos_ventas, "Fecha", "%Y-%m-%d")

datos_ventas = conversion_mayusculas(datos_ventas, ["ProductoID", "ClienteID", "TiendaID"])

datos_ventas = eliminar_espacios(datos_ventas, ["ProductoID", "ClienteID", "TiendaID"])

datos_ventas  = calcular_valor_venta(datos_ventas)

datos_a_cargar = preparar_datos_para_carga(datos_ventas)


insertados = cargar_datos_en_db(datos_a_cargar)

print(f"Se han cargado {insertados} registros en la base de datos.")



