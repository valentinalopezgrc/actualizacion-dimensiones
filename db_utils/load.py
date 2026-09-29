import sqlite3
import pandas as pd
import os
from dotenv import load_dotenv

# Se cargan las variables del .env aquí también, para que RUTA_DB se lea bien
# sin importar desde qué archivo se importe load.py
load_dotenv()

RUTA_DB = os.getenv("RUTA_DB", "instance")

conn = sqlite3.connect(f'{RUTA_DB}/datacaos_estrella.db')

def _siguiente_numero_venta(con):
    actual = con.execute(
        "SELECT MAX(CAST(SUBSTR(VentaID, 2) AS INTEGER)) FROM VentasFact"
    ).fetchone()[0]
    return actual or 0



def preparar_datos_para_carga(df):
    """
    Prepara los datos para la carga en la base de datos.

    Args:
        df (pd.DataFrame): DataFrame con los datos a preparar.

    Returns:
        pd.DataFrame: DataFrame preparado para la carga.
    """
    # Aquí puedes agregar cualquier transformación adicional que necesites
    df = df.copy()
    df["FechaID"] = pd.to_datetime(df["Fecha"], format="%Y-%m-%d").dt.strftime("%Y%m%d").astype(int)

    # Genera los consecutivos de VentaID basados en el último número en la base de datos
    siguiente = _siguiente_numero_venta(conn)
    df["VentaID"] = [f"V{str(siguiente + i + 1).zfill(6)}" for i in range(len(df))]

    df = df[["VentaID", "FechaID", "TiendaID", "ProductoID", "ClienteID","Unidades", "PrecioUnitario", "Descuento", "ValorVenta"]]

    return df


def cargar_datos_en_db(df):
    """
    Carga los datos en la base de datos.

    Args:
        df (pd.DataFrame): DataFrame con los datos a cargar.
    """
    df.to_sql("VentasFact", conn, if_exists="append", index=False)
    conn.commit()
    return len(df)


# =============================================================================
# CARGA PARA LA ACTUALIZACIÓN DE DIMENSIONES (agregado para la tarea)
# =============================================================================
# DIFERENCIA CON cargar_datos_en_db (la del profe):
#   - cargar_datos_en_db usa to_sql(..., if_exists="append"): SIEMPRE agrega filas.
#     Sirve para VentasFact porque cada venta es un evento nuevo.
#   - En una dimensión eso no sirve: si el cliente CLI0005 ya existe y lo
#     "agregamos" otra vez, se duplicaría (o fallaría por la llave primaria).
#     Por eso aquí se usa UPSERT = UPDATE + INSERT.
# =============================================================================

def _valores_iguales(valor_actual, valor_nuevo):
    """
    Compara el valor que hay en la base con el que viene en el archivo.
    Si los dos son números (ej. precios) los compara como número, porque
    1850000 (entero en la base) y 1850000.0 (decimal en pandas) son lo mismo
    aunque como texto se vean distinto.
    """
    try:
        # float() convierte a número. round(..., 2) = redondear a 2 decimales
        return round(float(valor_actual), 2) == round(float(valor_nuevo), 2)
    except (TypeError, ValueError):
        # Si no se pudo convertir a número (ej. "Bogotá"), se comparan como texto
        return str(valor_actual) == str(valor_nuevo)


def actualizar_dimension(df, tabla, llave):
    """
    Actualiza una tabla de dimensión con la técnica UPSERT (SCD Tipo 1):
      - Si la llave no existe en la tabla  -> INSERT (registro nuevo).
      - Si existe y algún dato cambió      -> UPDATE (se sobrescribe el dato viejo).
      - Si existe y todo es igual          -> no se hace nada.

    SCD = Slowly Changing Dimension (dimensión de cambio lento).
    Tipo 1 = el dato nuevo REEMPLAZA al viejo y no se guarda historial.
    (Tipo 2 sería guardar las dos versiones con fechas de vigencia.)

    Args:
        df (pd.DataFrame): Datos ya transformados, con las mismas columnas de la tabla.
        tabla (str): Nombre de la dimensión, ej. "DimCliente".
        llave (str): Llave primaria de la dimensión, ej. "ClienteID".

    Returns:
        dict: Cantidad de registros nuevos, actualizados y sin cambios.
    """
    # Lista con los nombres de las columnas: ["ClienteID", "NombreCliente", ...]
    columnas = list(df.columns)

    # ---- 1. Traer lo que hoy tiene la dimensión ----------------------------
    # pd.read_sql ejecuta el SELECT y devuelve un DataFrame.
    # set_index(llave) pone el ID como "índice" para poder buscar rápido una
    # fila por su ID, así: actual.at["CLI0005", "Ciudad"]
    actual = pd.read_sql(f"SELECT * FROM {tabla}", conn).set_index(llave)

    # ---- 2. Clasificar cada fila del archivo -------------------------------
    nuevos, actualizados, sin_cambios = [], [], 0

    # to_dict("records") convierte el DataFrame en una lista de diccionarios,
    # uno por fila: {"ClienteID": "CLI0005", "NombreCliente": "Nicolás...", ...}
    for fila in df.to_dict("records"):
        id_fila = fila[llave]

        if id_fila not in actual.index:
            # El ID no está en la tabla -> registro NUEVO
            nuevos.append(fila)

        # any(...) es True si AL MENOS UNA columna (sin contar la llave) es distinta
        elif any(not _valores_iguales(actual.at[id_fila, c], fila[c]) for c in columnas if c != llave):
            # El ID existe pero algo cambió -> hay que ACTUALIZAR
            actualizados.append(fila)

        else:
            # El ID existe y todo es igual -> no se toca
            sin_cambios += 1

    # ---- 3. Armar la sentencia SQL del UPSERT ------------------------------
    # Ejemplo de cómo queda para DimTienda:
    #   INSERT INTO DimTienda (TiendaID, NombreTienda, Ciudad, Region, FechaApertura)
    #   VALUES (?, ?, ?, ?, ?)
    #   ON CONFLICT(TiendaID) DO UPDATE SET
    #       NombreTienda = excluded.NombreTienda, Ciudad = excluded.Ciudad, ...
    #
    # - Los "?" son espacios que SQLite llena con los datos de cada fila
    #   (así se evita pegar texto directo en el SQL).
    # - ON CONFLICT(llave): "si ya existe una fila con ese ID..."
    # - DO UPDATE SET: "...en vez de fallar, actualiza estas columnas"
    # - excluded.Columna = el valor que se INTENTÓ insertar (el dato nuevo)
    columnas_sql = ", ".join(columnas)                     # "TiendaID, NombreTienda, ..."
    marcadores = ", ".join(["?"] * len(columnas))          # "?, ?, ?, ?, ?"
    columnas_update = ", ".join(f"{c} = excluded.{c}" for c in columnas if c != llave)
    sql = (f"INSERT INTO {tabla} ({columnas_sql}) VALUES ({marcadores}) "
           f"ON CONFLICT({llave}) DO UPDATE SET {columnas_update}")

    # ---- 4. Ejecutar ---------------------------------------------------------
    # Solo se mandan los nuevos y los actualizados (los "sin cambios" no hace
    # falta tocarlos). Cada fila se convierte en una tupla con los valores en
    # el mismo orden de las columnas.
    registros = [tuple(fila[c] for c in columnas) for fila in nuevos + actualizados]

    # executemany ejecuta el mismo SQL una vez por cada tupla de la lista
    conn.executemany(sql, registros)

    # commit = guardar los cambios en la base (sin esto no quedan guardados)
    conn.commit()

    return {"nuevos": len(nuevos), "actualizados": len(actualizados), "sin_cambios": sin_cambios}