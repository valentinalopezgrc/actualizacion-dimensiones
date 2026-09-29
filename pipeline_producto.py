# =============================================================================
# PIPELINE: ACTUALIZACIÓN DE LA DIMENSIÓN PRODUCTO (DimProducto)
# =============================================================================
# EXTRAER el CSV de productos, TRANSFORMAR (limpiar) y CARGAR en DimProducto.
#
# Recordar: en el esquema ESTRELLA DimProducto está DESNORMALIZADA, o sea que
# la categoría y el proveedor van escritos dentro de cada producto (no hay
# tablas aparte DimCategoria/DimProveedor como en copo de nieve). Por eso el
# CSV trae todo en una sola fila.
#
# Lo especial de este: el precio puede venir como texto ("$1.450.000") y hay
# que convertirlo a número.
# =============================================================================

import os                                   # para armar la ruta csvs/productos
from dotenv import load_dotenv              # para leer el archivo .env

from utils.reglas import leer_archivos_csv, renombrar_columnas, eliminar_espacios, conversion_mayusculas, formato_titulo, primera_mayuscula, limpiar_precio, eliminar_nulos, eliminar_duplicados
from db_utils.load import actualizar_dimension

load_dotenv()

ruta_archivos = os.getenv("RUTA_ARCHIVOS", "csvs")


# =============================================================================
# 1. EXTRAER
# =============================================================================
# Lee todos los CSV de la carpeta csvs/productos y los junta en un DataFrame
datos_productos = leer_archivos_csv(os.path.join(ruta_archivos, "productos"))
print(f"Registros leídos del archivo: {len(datos_productos)}")


# =============================================================================
# 2. TRANSFORMAR
# =============================================================================

# Nombres de las columnas del archivo -> nombres de la tabla DimProducto
mapeo_columnas = {
    "COD_PRODUCTO": "ProductoID",
    "NOMBRE_PRODUCTO": "NombreProducto",
    "MARCA": "MarcaProducto",
    "CATEGORIA": "NombreCategoria",
    "PROVEEDOR": "NombreProveedor",
    "PAIS_PROVEEDOR": "PaisProveedor",
    "PRECIO_LISTA": "PrecioListado"
}
datos_productos = renombrar_columnas(datos_productos, mapeo_columnas)

# Solo las columnas de DimProducto, en su orden
columnas = ["ProductoID", "NombreProducto", "MarcaProducto", "NombreCategoria",
            "NombreProveedor", "PaisProveedor", "PrecioListado"]
datos_productos = datos_productos[columnas]

# Columnas de texto (todas menos el precio). A estas se les quitan los espacios.
# Al precio no, porque ese se limpia aparte con limpiar_precio.
columnas_texto = ["ProductoID", "NombreProducto", "MarcaProducto", "NombreCategoria",
                  "NombreProveedor", "PaisProveedor"]
datos_productos = eliminar_espacios(datos_productos, columnas_texto)

# " prd039 " ya sin espacios -> "PRD039"
datos_productos = conversion_mayusculas(datos_productos, ["ProductoID"])

# Solo la primera letra en mayúscula, igual a como está en la base:
# "CELULARES" -> "Celulares", "audio" -> "Audio", "Equipos de computo" se mantiene.
# (No se usa formato_titulo porque daría "Equipos De Computo" y no coincidiría)
datos_productos = primera_mayuscula(datos_productos, ["NombreCategoria"])

# "méxico" -> "México", "estados unidos" -> "Estados Unidos"
# OJO: a nombre, marca y proveedor NO se les aplica, porque dañaría marcas
# como "SoundMax" -> "Soundmax"
datos_productos = formato_titulo(datos_productos, ["PaisProveedor"])

# Precio: "$459.900" -> 459900.0
# Se botan los precios negativos (PRD042 con -45000) y los que no son número
# (PRD043 con "precio pendiente")
datos_productos = limpiar_precio(datos_productos, "PrecioListado")

# Se botan las filas con algún dato vacío (todas las columnas son NOT NULL)
datos_productos = eliminar_nulos(datos_productos, columnas)

# Si un producto viene repetido se deja el último registro
datos_productos = eliminar_duplicados(datos_productos, ["ProductoID"], conservar="last")

print(f"Registros válidos después de transformar: {len(datos_productos)}")


# =============================================================================
# 3. CARGAR
# =============================================================================
# UPSERT en DimProducto usando ProductoID como llave:
#   PRD039, PRD040, PRD041 no existen -> se insertan
#   PRD010 y PRD020 cambiaron de precio -> se actualizan
#   PRD038 vino igual -> no se toca
resultado = actualizar_dimension(datos_productos, "DimProducto", "ProductoID")

print(f"DimProducto -> nuevos: {resultado['nuevos']} | actualizados: {resultado['actualizados']} | sin cambios: {resultado['sin_cambios']}")