# =============================================================================
# PIPELINE: ACTUALIZACIÓN DE LA DIMENSIÓN CLIENTE (DimCliente)
# =============================================================================
# ¿Qué es un pipeline? Una secuencia de pasos que toma datos de una FUENTE
# (aquí un archivo CSV) y los lleva a un DESTINO (la tabla DimCliente de la
# base datacaos_estrella). Tiene 3 fases: EXTRAER -> TRANSFORMAR -> CARGAR (ETL).
#
# ¿Por qué hay que actualizar la dimensión? Si llega una venta de un cliente
# que NO existe en DimCliente, esa venta se descarta (no se puede relacionar).
# Por eso primero hay que tener los clientes nuevos y los cambios al día.
# =============================================================================

import os                                   # para armar rutas de carpetas (csvs/clientes)
from dotenv import load_dotenv              # para leer las variables del archivo .env

# Funciones de limpieza que están en utils/reglas.py
# (las primeras son las del profe, las otras las agregamos nosotras)
from utils.reglas import leer_archivos_csv, renombrar_columnas, eliminar_espacios, conversion_mayusculas, formato_titulo, primera_mayuscula, eliminar_nulos, filtrar_valores_validos, eliminar_duplicados

# Función que hace la carga (el UPSERT) y que está en db_utils/load.py
from db_utils.load import actualizar_dimension

# Carga las variables del .env (RUTA_ARCHIVOS=csvs y RUTA_DB=instance)
load_dotenv()

# Carpeta donde están los CSV. Si no encuentra la variable en el .env, usa "csvs"
ruta_archivos = os.getenv("RUTA_ARCHIVOS", "csvs")


# =============================================================================
# 1. EXTRAER
# =============================================================================
# os.path.join arma la ruta "csvs/clientes" (o "csvs\clientes" en Windows).
# leer_archivos_csv lee TODOS los .csv de esa carpeta y los junta en un solo
# DataFrame (una tabla de pandas). Si mañana llega otro CSV de clientes, basta
# con meterlo en la carpeta y se procesa también.
datos_clientes = leer_archivos_csv(os.path.join(ruta_archivos, "clientes"))
print(f"Registros leídos del archivo: {len(datos_clientes)}")   # len() = cantidad de filas


# =============================================================================
# 2. TRANSFORMAR (limpiar y dejar los datos como los espera la base)
# =============================================================================

# El archivo fuente trae nombres de columna distintos a los de la tabla
# (COD_CLIENTE vs ClienteID). Este diccionario dice: "nombre viejo": "nombre nuevo"
mapeo_columnas = {
    "COD_CLIENTE": "ClienteID",
    "NOMBRE_CLIENTE": "NombreCliente",
    "GENERO": "Genero",
    "RANGO_EDAD": "RangoEdad",
    "CIUDAD": "Ciudad",
    "SEGMENTO": "SegmentoCliente"
}
datos_clientes = renombrar_columnas(datos_clientes, mapeo_columnas)

# Nos quedamos solo con las columnas que tiene la tabla DimCliente, en ese orden
columnas = ["ClienteID", "NombreCliente", "Genero", "RangoEdad", "Ciudad", "SegmentoCliente"]
datos_clientes = datos_clientes[columnas]

# Quita espacios al inicio y al final: " cli0082 " -> "cli0082"
datos_clientes = eliminar_espacios(datos_clientes, columnas)

# Pasa a mayúsculas el ID y el género: "cli0082" -> "CLI0082", "f" -> "F"
datos_clientes = conversion_mayusculas(datos_clientes, ["ClienteID", "Genero"])

# Primera letra de cada palabra en mayúscula: "valentina lópez garcía" -> "Valentina López García"
datos_clientes = formato_titulo(datos_clientes, ["NombreCliente", "Ciudad"])

# En la base el género es de 1 sola letra. .str[0] toma la primera letra del texto:
# "MASCULINO" -> "M", "FEMENINO" -> "F"
datos_clientes["Genero"] = datos_clientes["Genero"].str[0]

# Deja el segmento como está en la base: "nuevo" -> "Nuevo", "vip" -> "Vip"...
datos_clientes = primera_mayuscula(datos_clientes, ["SegmentoCliente"])
# ...pero VIP va todo en mayúscula, entonces se corrige ese caso: "Vip" -> "VIP"
datos_clientes["SegmentoCliente"] = datos_clientes["SegmentoCliente"].replace({"Vip": "VIP"})

# Todas las columnas de DimCliente son NOT NULL: si falta un dato, la fila se bota
# (en el CSV: CLI0086 no tiene nombre)
datos_clientes = eliminar_nulos(datos_clientes, columnas)

# Solo se aceptan géneros F o M (en el CSV: CLI0087 viene con "X" y se bota)
datos_clientes = filtrar_valores_validos(datos_clientes, "Genero", ["F", "M"])

# Solo se aceptan los 3 segmentos que maneja el negocio
datos_clientes = filtrar_valores_validos(datos_clientes, "SegmentoCliente", ["Nuevo", "Regular", "VIP"])

# Si el mismo cliente viene 2 veces se deja el ÚLTIMO (conservar="last"), porque
# es el dato más reciente. En el CSV, CLI0083 viene como "Regular" y luego como "VIP":
# queda VIP.
datos_clientes = eliminar_duplicados(datos_clientes, ["ClienteID"], conservar="last")

print(f"Registros válidos después de transformar: {len(datos_clientes)}")


# =============================================================================
# 3. CARGAR
# =============================================================================
# actualizar_dimension compara cada cliente del archivo con DimCliente:
#   - ClienteID no existe            -> lo INSERTA (cliente nuevo)
#   - existe pero cambió algún dato  -> lo ACTUALIZA (ej. CLI0005 pasó de Regular a VIP)
#   - existe y todo es igual         -> no hace nada
# Recibe: los datos limpios, el nombre de la tabla y su llave primaria.
resultado = actualizar_dimension(datos_clientes, "DimCliente", "ClienteID")

# resultado es un diccionario con los conteos, por eso se lee con resultado['nuevos']
print(f"DimCliente -> nuevos: {resultado['nuevos']} | actualizados: {resultado['actualizados']} | sin cambios: {resultado['sin_cambios']}")