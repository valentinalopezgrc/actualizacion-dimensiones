# =============================================================================
# CARGA INICIAL DEL DATA WAREHOUSE EN MYSQL
# =============================================================================
# La base MySQL que creó el profe tiene las tablas VACÍAS (solo la estructura).
# Este archivo la llena con los datos originales de DataCaos (los CSV de la
# carpeta "Archivos datos base de datos DataCaos" del aula), que son los mismos
# que tenía la base SQLite: 366 fechas, 5 tiendas, 80 clientes, 38 productos y
# 2200 ventas.
#
# Se ejecuta UNA vez, antes de los pipelines de actualización. Si se corre otra
# vez no pasa nada: solo inserta lo que falte.
# =============================================================================

import os
import pandas as pd
from dotenv import load_dotenv
from db_utils.load import carga_inicial_tabla

load_dotenv()

ruta = os.path.join(os.getenv("RUTA_ARCHIVOS", "csvs"), "carga_inicial")

# ORDEN IMPORTANTE: primero las dimensiones y al final los hechos, porque las
# ventas apuntan (FOREIGN KEY) a fecha, tienda, producto y cliente.
tablas = [
    ("DIM_FECHA.csv",    "DimFecha",    "FechaID"),
    ("DIM_TIENDA.csv",   "DimTienda",   "TiendaID"),
    ("DIM_CLIENTE.csv",  "DimCliente",  "ClienteID"),
    ("DIM_PRODUCTO.csv", "DimProducto", "ProductoID"),
    ("VENTAS_FACT.csv",  "VentasFact",  "VentaID"),
]

for archivo, tabla, llave in tablas:
    # Los CSV del profe vienen separados por punto y coma (;) y con BOM
    # (un carácter invisible al inicio que pone Excel), por eso sep=";" y utf-8-sig
    df = pd.read_csv(os.path.join(ruta, archivo), sep=";", encoding="utf-8-sig", dtype=str)

    # En VENTAS_FACT el descuento viene con coma decimal ("0,05"): MySQL necesita punto
    if "Descuento" in df.columns:
        df["Descuento"] = df["Descuento"].str.replace(",", ".", regex=False)

    insertados, ya_estaban = carga_inicial_tabla(df, tabla, llave)
    print(f"{tabla}: {insertados} insertados | {ya_estaban} ya existían")
