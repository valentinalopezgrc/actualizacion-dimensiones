import os
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Se cargan las variables del .env (host, usuario, contraseña, nombre de la base)
load_dotenv()

# =============================================================================
# CONEXIÓN A MYSQL
# =============================================================================
# En SQLite la base era un ARCHIVO (instance/datacaos_estrella.db) y bastaba con
# sqlite3.connect("ruta"). MySQL es un SERVIDOR: hay que decir dónde está (host y
# puerto), a qué base entrar y con qué usuario y contraseña.
#
# Usamos SQLAlchemy para crear la conexión ("engine") y PyMySQL como el "driver"
# que sabe hablar con MySQL. pandas trabaja directo con el engine de SQLAlchemy
# (read_sql y to_sql).
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# quote_plus protege la contraseña por si tiene caracteres especiales (@, #, /...)
# que dañarían la dirección de conexión.
URL_CONEXION = (
    f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"   # para que las tildes y la ñ se guarden bien (Bogotá, Nicolás)
)

# pool_pre_ping=True revisa que la conexión siga viva antes de usarla
# (útil porque el servidor está en la nube y puede cerrar conexiones inactivas).
engine = create_engine(URL_CONEXION, pool_pre_ping=True)


def _a_tipo_python(valor):
    """
    pandas guarda los números como tipos de numpy (numpy.int64, numpy.float64) y
    PyMySQL no siempre los entiende. .item() los convierte a int/float normales.
    """
    return valor.item() if hasattr(valor, "item") else valor


# =============================================================================
# TABLA DE HECHOS: VentasFact
# =============================================================================

def _siguiente_numero_venta():
    """
    Busca el número del último VentaID (ej. V002200 -> 2200).
    En MySQL se usa SUBSTRING y CAST(... AS UNSIGNED) (en SQLite era SUBSTR y INTEGER).
    """
    with engine.connect() as con:
        actual = con.execute(
            text("SELECT MAX(CAST(SUBSTRING(VentaID, 2) AS UNSIGNED)) FROM VentasFact")
        ).scalar()
    return int(actual or 0)


def validar_referencias(df):
    """
    Descarta las ventas cuya tienda, producto o cliente NO exista en su dimensión.

    En MySQL las llaves foráneas (FOREIGN KEY) sí se hacen cumplir: si una venta
    apunta a un cliente que no existe, MySQL rechaza la carga. Por eso se validan
    antes. (Misma idea que load_erp_estrella.py del profe.)
    Por eso también hay que actualizar las DIMENSIONES ANTES que los HECHOS.
    """
    with engine.connect() as con:
        tiendas = {r[0] for r in con.execute(text("SELECT TiendaID FROM DimTienda"))}
        productos = {r[0] for r in con.execute(text("SELECT ProductoID FROM DimProducto"))}
        clientes = {r[0] for r in con.execute(text("SELECT ClienteID FROM DimCliente"))}
        fechas = {r[0] for r in con.execute(text("SELECT FechaID FROM DimFecha"))}

    ok = (df["TiendaID"].isin(tiendas)
          & df["ProductoID"].isin(productos)
          & df["ClienteID"].isin(clientes)
          & df["FechaID"].isin(fechas))

    if (~ok).any():
        print(f"Ventas descartadas por referencias que no existen: {(~ok).sum()}")
        print(df.loc[~ok, ["FechaID", "TiendaID", "ProductoID", "ClienteID"]].to_string(index=False))
    return df[ok].copy()


def quitar_ventas_ya_cargadas(df):
    """
    Evita cargar dos veces la misma venta (carga idempotente).

    Una venta se considera la misma si coincide en fecha, tienda, producto,
    cliente, unidades y precio. Se compara contra lo que ya hay en VentasFact
    y solo se dejan las que no existen.
    """
    llave = ["FechaID", "TiendaID", "ProductoID", "ClienteID", "Unidades", "PrecioUnitario"]
    existentes = pd.read_sql(f"SELECT {', '.join(llave)} FROM VentasFact", engine)

    # Se igualan los tipos para poder comparar (MySQL devuelve DECIMAL)
    existentes["PrecioUnitario"] = existentes["PrecioUnitario"].astype(float)
    df = df.copy()
    df["PrecioUnitario"] = df["PrecioUnitario"].astype(float)

    # merge con indicator=True marca cada venta como "both" (ya estaba en la base)
    # o "left_only" (solo está en el archivo, o sea que es nueva)
    cruce = df.merge(existentes.drop_duplicates(), on=llave, how="left", indicator=True)
    nuevas = cruce[cruce["_merge"] == "left_only"].drop(columns="_merge")

    ya_cargadas = len(df) - len(nuevas)
    if ya_cargadas:
        print(f"Ventas que ya estaban en la base (se omiten): {ya_cargadas}")
    return nuevas


def preparar_datos_para_carga(df):
    """
    Prepara las ventas para VentasFact (función del profe, adaptada a MySQL):
      1. Convierte la fecha en FechaID (2024-01-03 -> 20240103).
      2. Valida que tienda, producto, cliente y fecha existan en las dimensiones.
      3. Quita las ventas que ya estaban cargadas.
      4. Genera el VentaID consecutivo (V002201, V002202, ...).
    """
    df = df.copy()
    df["FechaID"] = pd.to_datetime(df["Fecha"], format="%Y-%m-%d").dt.strftime("%Y%m%d").astype(int)

    df = validar_referencias(df)
    df = quitar_ventas_ya_cargadas(df)

    siguiente = _siguiente_numero_venta()
    df["VentaID"] = [f"V{str(siguiente + i + 1).zfill(6)}" for i in range(len(df))]

    return df[["VentaID", "FechaID", "TiendaID", "ProductoID", "ClienteID",
               "Unidades", "PrecioUnitario", "Descuento", "ValorVenta"]]


def cargar_datos_en_db(df):
    """
    Carga las ventas en VentasFact con append (función del profe).
    Aquí sí sirve append: cada venta es un evento nuevo, y las repetidas
    ya se quitaron en preparar_datos_para_carga.
    """
    if df.empty:
        return 0
    df.to_sql("VentasFact", engine, if_exists="append", index=False)
    return len(df)


# =============================================================================
# DIMENSIONES: DimCliente, DimTienda, DimProducto
# =============================================================================

def _valores_iguales(valor_actual, valor_nuevo):
    """
    Compara el valor de la base con el del archivo.
    MySQL devuelve los precios como Decimal y las fechas como date, por eso se
    comparan como número si se puede, y si no como texto.
    """
    try:
        return round(float(valor_actual), 2) == round(float(valor_nuevo), 2)
    except (TypeError, ValueError):
        return str(valor_actual) == str(valor_nuevo)


def actualizar_dimension(df, tabla, llave):
    """
    Actualiza una dimensión con UPSERT (SCD Tipo 1):
      - La llave no existe          -> INSERT (registro nuevo)
      - Existe y algún dato cambió  -> UPDATE (se sobrescribe)
      - Existe y todo es igual      -> no se toca

    Diferencia con la versión SQLite: la sintaxis del UPSERT.
      SQLite: INSERT ... ON CONFLICT(llave) DO UPDATE SET col = excluded.col
      MySQL:  INSERT ... ON DUPLICATE KEY UPDATE col = VALUES(col)
    Y en MySQL los espacios para los datos se marcan con %s en vez de ?.
    """
    columnas = list(df.columns)

    # 1. Lo que hoy tiene la dimensión, con el ID como índice para buscar rápido
    actual = pd.read_sql(f"SELECT * FROM {tabla}", engine).set_index(llave)

    # 2. Clasificar cada fila del archivo
    nuevos, actualizados, sin_cambios = [], [], 0
    for fila in df.to_dict("records"):
        id_fila = fila[llave]
        if id_fila not in actual.index:
            nuevos.append(fila)
        elif any(not _valores_iguales(actual.at[id_fila, c], fila[c]) for c in columnas if c != llave):
            actualizados.append(fila)
        else:
            sin_cambios += 1

    # 3. Armar el UPSERT de MySQL. Ejemplo para DimTienda:
    #   INSERT INTO DimTienda (TiendaID, NombreTienda, Ciudad, Region, FechaApertura)
    #   VALUES (%s, %s, %s, %s, %s)
    #   ON DUPLICATE KEY UPDATE NombreTienda = VALUES(NombreTienda), Ciudad = VALUES(Ciudad), ...
    #
    # ON DUPLICATE KEY: "si ese ID ya existe (llave primaria duplicada)..."
    # UPDATE ... = VALUES(col): "...actualiza la columna con el valor que intenté insertar"
    columnas_sql = ", ".join(columnas)
    marcadores = ", ".join(["%s"] * len(columnas))
    columnas_update = ", ".join(f"{c} = VALUES({c})" for c in columnas if c != llave)
    sql = (f"INSERT INTO {tabla} ({columnas_sql}) VALUES ({marcadores}) "
           f"ON DUPLICATE KEY UPDATE {columnas_update}")

    # 4. Ejecutar solo nuevos + actualizados.
    # engine.begin() abre una transacción y hace COMMIT automático al terminar
    # (si algo falla, hace ROLLBACK y no queda nada a medias).
    registros = [tuple(_a_tipo_python(fila[c]) for c in columnas) for fila in nuevos + actualizados]
    if registros:
        with engine.begin() as con:
            con.exec_driver_sql(sql, registros)

    return {"nuevos": len(nuevos), "actualizados": len(actualizados), "sin_cambios": sin_cambios}


# =============================================================================
# CARGA INICIAL (tablas vacías)
# =============================================================================

def carga_inicial_tabla(df, tabla, llave):
    """
    Carga los datos originales de DataCaos en una tabla de MySQL.

    Solo inserta los registros cuya llave NO existe todavía en la tabla. Así,
    si se ejecuta dos veces, la segunda vez no duplica nada ni da error.
    (Aquí no se actualiza nada: esto es solo para llenar las tablas vacías.)

    Returns:
        tuple: (registros insertados, registros que ya existían)
    """
    existentes = pd.read_sql(f"SELECT {llave} FROM {tabla}", engine)[llave].astype(str)
    nuevos = df[~df[llave].astype(str).isin(existentes)]

    if not nuevos.empty:
        # method="multi" y chunksize=500: manda los datos en paquetes de 500 filas
        # por consulta, en vez de una por una (mucho más rápido con la base en la nube)
        nuevos.to_sql(tabla, engine, if_exists="append", index=False, method="multi", chunksize=500)

    return len(nuevos), len(df) - len(nuevos)
