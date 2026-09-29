# =============================================================================
# PIPELINE: ACTUALIZACIÓN DE LA DIMENSIÓN TIENDA (DimTienda)
# =============================================================================
# Misma idea del pipeline de clientes: EXTRAER el CSV de tiendas, TRANSFORMAR
# (limpiar) y CARGAR en la tabla DimTienda de datacaos_estrella.
# Lo especial de este: la fecha de apertura viene en formato colombiano
# (dd/mm/aaaa) y en la base se guarda como aaaa-mm-dd.
# =============================================================================

import os                                   # para armar la ruta csvs/tiendas
from dotenv import load_dotenv              # para leer el archivo .env

from utils.reglas import leer_archivos_csv, renombrar_columnas, eliminar_espacios, conversion_mayusculas, formato_titulo, formato_fecha, eliminar_nulos, eliminar_duplicados
from db_utils.load import actualizar_dimension

load_dotenv()

ruta_archivos = os.getenv("RUTA_ARCHIVOS", "csvs")


# =============================================================================
# 1. EXTRAER
# =============================================================================
# Lee todos los CSV de la carpeta csvs/tiendas y los junta en un DataFrame
datos_tiendas = leer_archivos_csv(os.path.join(ruta_archivos, "tiendas"))
print(f"Registros leídos del archivo: {len(datos_tiendas)}")


# =============================================================================
# 2. TRANSFORMAR
# =============================================================================

# Nombres de las columnas del archivo -> nombres de la tabla DimTienda
mapeo_columnas = {
    "COD_TIENDA": "TiendaID",
    "NOMBRE_TIENDA": "NombreTienda",
    "CIUDAD": "Ciudad",
    "REGION": "Region",
    "FECHA_APERTURA": "FechaApertura"
}
datos_tiendas = renombrar_columnas(datos_tiendas, mapeo_columnas)

# Solo las columnas de DimTienda, en su orden
columnas = ["TiendaID", "NombreTienda", "Ciudad", "Region", "FechaApertura"]
datos_tiendas = datos_tiendas[columnas]

# Quita espacios sobrantes: " t06 " -> "t06"
datos_tiendas = eliminar_espacios(datos_tiendas, columnas)

# ID en mayúscula: "t06" -> "T06"
datos_tiendas = conversion_mayusculas(datos_tiendas, ["TiendaID"])

# "pereira" -> "Pereira", "eje cafetero" -> "Eje Cafetero"
# OJO: al NombreTienda NO se le aplica, porque dañaría "DataCaos" -> "Datacaos"
datos_tiendas = formato_titulo(datos_tiendas, ["Ciudad", "Region"])

# Fecha: le decimos cómo viene en el archivo (formato_entrada="%d/%m/%Y" -> 01/06/2023)
# y cómo la queremos en la base ("%Y-%m-%d" -> 2023-06-01).
#   %d = día, %m = mes, %Y = año con 4 dígitos
# Si una fecha no cumple el formato (ej. "2025/13/40" de T08) queda vacía.
datos_tiendas = formato_fecha(datos_tiendas, "FechaApertura", "%Y-%m-%d", formato_entrada="%d/%m/%Y")

# Se botan las filas con datos vacíos (aquí cae T08 por su fecha dañada)
datos_tiendas = eliminar_nulos(datos_tiendas, columnas)

# T07 viene repetida en el CSV: se deja una sola (la última)
datos_tiendas = eliminar_duplicados(datos_tiendas, ["TiendaID"], conservar="last")

print(f"Registros válidos después de transformar: {len(datos_tiendas)}")


# =============================================================================
# 3. CARGAR
# =============================================================================
# UPSERT en DimTienda usando TiendaID como llave:
#   T06 y T07 no existen -> se insertan
#   T03 cambió de nombre (Cali Norte -> Cali Chipichape) -> se actualiza
#   T01 vino igual -> no se toca
resultado = actualizar_dimension(datos_tiendas, "DimTienda", "TiendaID")

print(f"DimTienda -> nuevos: {resultado['nuevos']} | actualizados: {resultado['actualizados']} | sin cambios: {resultado['sin_cambios']}")