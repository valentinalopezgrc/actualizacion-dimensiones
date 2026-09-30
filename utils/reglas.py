import pandas as pd
import os

def leer_archivos_csv(ruta_archivos):
    """
    Lee todos los archivos CSV en la ruta especificada y los concatena en un solo DataFrame.

    Args:
        ruta_archivos (str): Ruta del directorio que contiene los archivos CSV.

    Returns:
        pd.DataFrame: DataFrame concatenado con todos los datos de los archivos CSV.
    """
    archivos_csv = [archivo for archivo in os.listdir(ruta_archivos) if archivo.endswith('.csv')]
    
    if not archivos_csv:
        raise FileNotFoundError(f"No se encontraron archivos CSV en la ruta: {ruta_archivos}")

    dataframes = []
    for archivo in archivos_csv:
        ruta_completa = os.path.join(ruta_archivos, archivo)
        df = pd.read_csv(ruta_completa)
        dataframes.append(df)

    df_concatenado = pd.concat(dataframes, ignore_index=True)
    return df_concatenado

def eliminar_duplicados(df, columnas, conservar="first"):
    """
    Elimina filas duplicadas en un DataFrame basado en las columnas especificadas.

    Args:
        df (pd.DataFrame): El DataFrame del cual se eliminarán los duplicados.
        columnas (list): Lista de nombres de columnas para identificar duplicados.
        conservar (str): "first" deja el primer registro repetido, "last" el último.

    Returns:
        pd.DataFrame: DataFrame sin filas duplicadas.
    """
    return df.drop_duplicates(subset=columnas, keep=conservar)

def formato_fecha(df, columna_fecha, formato="%Y-%m-%d", formato_entrada=None):
    """
    Convierte una columna de fecha en un DataFrame al formato especificado.

    Args:
        df (pd.DataFrame): El DataFrame que contiene la columna de fecha.
        columna_fecha (str): Nombre de la columna que contiene las fechas.
        formato (str): Formato deseado para la fecha (por defecto es "%Y-%m-%d").
        formato_entrada (str): Formato en que viene la fecha en el archivo, ej. "%d/%m/%Y".
            Si la fecha no cumple ese formato queda vacía (NaN).

    Returns:
        pd.DataFrame: DataFrame con la columna de fecha formateada.
    """
    # Si nos dicen cómo viene la fecha, se usa ese formato. errors="coerce"
    # deja vacía (NaT) la fecha que no se pueda leer, en vez de dar error.
    if formato_entrada:
        df[columna_fecha] = pd.to_datetime(df[columna_fecha], format=formato_entrada, errors="coerce").dt.strftime(formato)
    else:
        df[columna_fecha] = pd.to_datetime(df[columna_fecha]).dt.strftime(formato)
    return df

def renombrar_columnas(df, mapeo_columnas):
    """
    Renombra las columnas de un DataFrame según un mapeo proporcionado.

    Args:
        df (pd.DataFrame): El DataFrame cuyas columnas se renombrarán.
        mapeo_columnas (dict): Diccionario que mapea nombres antiguos a nuevos nombres.

    Returns:
        pd.DataFrame: DataFrame con las columnas renombradas.
    """
    return df.rename(columns=mapeo_columnas)

def conversion_mayusculas(df, columnas):
    """
    Convierte los valores de las columnas especificadas a mayúsculas.

    Args:
        df (pd.DataFrame): El DataFrame que contiene las columnas a convertir.
        columnas (list): Lista de nombres de columnas cuyos valores se convertirán a mayúsculas.

    Returns:
        pd.DataFrame: DataFrame con los valores de las columnas especificadas en mayúsculas.
    """
    for columna in columnas:
        df[columna] = df[columna].str.upper()
    return df

def eliminar_espacios(df, columnas):
    """
    Elimina los espacios en blanco al inicio y al final de los valores en las columnas especificadas.

    Args:
        df (pd.DataFrame): El DataFrame que contiene las columnas a limpiar.
        columnas (list): Lista de nombres de columnas cuyos valores se limpiarán.

    Returns:
        pd.DataFrame: DataFrame con los valores de las columnas especificadas sin espacios en blanco.
    """
    for columna in columnas:
        df[columna] = df[columna].str.strip()
    return df

def calcular_valor_venta(df):
    df = df.copy()
    df["Descuento"] = df["Descuento"] / 100.0
    df["Unidades"] = df["Unidades"].astype(int)
    df["PrecioUnitario"] = df["PrecioUnitario"].astype(float)
    df["ValorVenta"] = (df["Unidades"] * df["PrecioUnitario"] * (1 - df["Descuento"])).round(0)
    return df


# ---------------------------------------------------------------------------
# Reglas agregadas para la actualización de dimensiones
# ---------------------------------------------------------------------------

def formato_titulo(df, columnas):
    """
    Deja la primera letra de cada palabra en mayúscula: "maria gomez" -> "Maria Gomez".

    Args:
        df (pd.DataFrame): El DataFrame que contiene las columnas.
        columnas (list): Lista de columnas a formatear.

    Returns:
        pd.DataFrame: DataFrame con las columnas formateadas.
    """
    for columna in columnas:
        df[columna] = df[columna].str.title()
    return df

def primera_mayuscula(df, columnas):
    """
    Deja solo la primera letra del texto en mayúscula: "EQUIPOS DE COMPUTO" -> "Equipos de computo".

    Args:
        df (pd.DataFrame): El DataFrame que contiene las columnas.
        columnas (list): Lista de columnas a formatear.

    Returns:
        pd.DataFrame: DataFrame con las columnas formateadas.
    """
    for columna in columnas:
        df[columna] = df[columna].str.capitalize()
    return df

def eliminar_nulos(df, columnas):
    """
    Elimina las filas que tengan algún valor vacío en las columnas indicadas.
    Todas las columnas de las dimensiones son NOT NULL en la base de datos.

    Args:
        df (pd.DataFrame): El DataFrame a limpiar.
        columnas (list): Columnas obligatorias.

    Returns:
        pd.DataFrame: DataFrame sin filas incompletas.
    """
    # dropna = "drop not available": elimina filas con valores vacíos (NaN)
    return df.dropna(subset=columnas)

def filtrar_valores_validos(df, columna, valores_validos):
    """
    Deja solo las filas cuyo valor en la columna esté dentro de la lista permitida.
    Ej: Genero solo puede ser "F" o "M".

    Args:
        df (pd.DataFrame): El DataFrame a filtrar.
        columna (str): Columna a validar.
        valores_validos (list): Valores permitidos.

    Returns:
        pd.DataFrame: DataFrame solo con filas válidas.
    """
    # .isin() devuelve True/False por fila según si el valor está en la lista;
    # df[...] se queda solo con las filas True
    return df[df[columna].isin(valores_validos)]

def limpiar_precio(df, columna):
    """
    Convierte un precio escrito como texto ("$1.450.000") a número (1450000.0).
    Los precios que no se puedan convertir o que sean menores o iguales a 0 se eliminan.

    Args:
        df (pd.DataFrame): El DataFrame que contiene el precio.
        columna (str): Nombre de la columna del precio.

    Returns:
        pd.DataFrame: DataFrame con el precio numérico y válido.
    """
    df = df.copy()
    # .astype(str): se pasa todo a texto primero, porque algunos precios vienen
    # como número (1850000) y otros como texto ("$65.000")
    # Expresión regular [$\s]: quita el signo $ y los espacios -> "65.000"
    precio = df[columna].astype(str).str.replace(r"[$\s]", "", regex=True)

    # Quita el punto o coma que va seguido de exactamente 3 dígitos
    # (separador de miles): "1.450.000" -> "1450000"
    precio = precio.str.replace(r"[.,](?=\d{3}(\D|$))", "", regex=True)

    # Si queda una coma es decimal: "899900,50" -> "899900.50"
    precio = precio.str.replace(",", ".", regex=False)

    # pd.to_numeric convierte el texto a número. errors="coerce" hace que lo
    # que no sea número ("precio pendiente") quede vacío (NaN) en vez de dar error
    df[columna] = pd.to_numeric(precio, errors="coerce").round(2)

    # Solo se dejan precios mayores a 0 (los NaN y negativos se van)
    return df[df[columna] > 0]
