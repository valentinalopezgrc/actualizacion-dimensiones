# Actualización del Data Warehouse - DataCaos (esquema estrella en MySQL)

Construimos pipelines ETL en Python para cargar y mantener actualizado el Data Warehouse de DataCaos en **MySQL**: las dimensiones **DimCliente**, **DimTienda** y **DimProducto**, y la tabla de hechos **VentasFact**.

**Fundación Universitaria Konrad Lorenz**\
Inteligencia de Negocios - Módulo 2: Infraestructura y Procesos de Integración de Datos\
Docente: Leandro Pájaro Fuentes

**Integrantes:** Laura Valentina López García y Juan Camilo Prieto Mestizo\
**Fecha:** 29-09-2026

---

## Tabla de contenido

1. [Contexto del problema](#1-contexto-del-problema)
2. [Modelo de datos](#2-modelo-de-datos)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Configuración de la conexión](#4-configuración-de-la-conexión)
5. [Flujo de carga](#5-flujo-de-carga)
6. [Reglas de transformación](#6-reglas-de-transformación)
7. [Estrategia de carga](#7-estrategia-de-carga)
8. [Instalación y ejecución](#8-instalación-y-ejecución)
9. [Datos de prueba y resultados](#9-datos-de-prueba-y-resultados)
10. [Verificación en DBeaver](#10-verificación-en-dbeaver)
11. [Cambios respecto a la versión SQLite](#11-cambios-respecto-a-la-versión-sqlite)

---

## 1. Contexto del problema

### El caso DataCaos S.A.

DataCaos S.A. es una empresa de retail con tiendas en varias ciudades de Colombia y una tienda en línea. Sus ventas estaban repartidas en sistemas que no se comunicaban entre sí: un ERP en Oracle para las tiendas físicas, una base MySQL para la tienda en línea y planillas de Excel que cada sede enviaba cada semana. El reporte de ventas se armaba a mano, copiando cifras de un sistema a otro, con fechas en distintos formatos y filas duplicadas por errores de digitación.

Para resolverlo, la empresa centralizó su información en un **Data Warehouse**, organizado en un **esquema estrella**, que se alimenta con **procesos ETL** en Python.

### Lo que hicimos

Primero trabajamos el Data Warehouse en SQLite: en clase construimos `pipeline_erp.py` para cargar ventas, y luego creamos un pipeline para cada dimensión. Ahora el Data Warehouse está en un **servidor MySQL en la nube**, con una base para cada estudiante, que venía con las tablas creadas pero **vacías**.

Por eso este proyecto hace tres cosas:

1. **Carga inicial:** llena las tablas vacías con los datos originales de DataCaos.
2. **Actualización de dimensiones:** agrega los clientes, tiendas y productos nuevos, y actualiza los que cambiaron.
3. **Actualización de la tabla de hechos:** agrega las ventas nuevas, sin duplicar las que ya estaban.

---

## 2. Modelo de datos

![Diagrama del esquema estrella de DataCaos](img/datacaos_estrella.png)

*Diagrama generado en DBeaver a partir de la base de DataCaos.*

La tabla de hechos **VentasFact** registra cada venta y apunta, mediante llaves foráneas (FOREIGN KEY), a sus cuatro dimensiones: **DimFecha**, **DimCliente**, **DimTienda** y **DimProducto**. En el esquema estrella `DimProducto` está desnormalizada: la categoría y el proveedor van escritos dentro de cada producto.

---

## 3. Estructura del proyecto

```
actualizacion_dw_mysql/
│
├── carga_inicial.py          # Llena las tablas vacías con los datos de DataCaos
├── pipeline_cliente.py       # Actualiza DimCliente
├── pipeline_tienda.py        # Actualiza DimTienda
├── pipeline_producto.py      # Actualiza DimProducto
├── pipeline_ventas.py        # Actualiza VentasFact (basado en pipeline_erp.py)
├── ejecutar_todo.py          # Ejecuta todo en el orden correcto
│
├── utils/
│   └── reglas.py             # Funciones de limpieza y transformación
│
├── db_utils/
│   └── load.py               # Conexión a MySQL y funciones de carga
│
├── csvs/
│   ├── carga_inicial/        # Datos originales de DataCaos (del aula)
│   ├── clientes/             # Clientes nuevos o modificados
│   ├── tiendas/              # Tiendas nuevas o modificadas
│   ├── productos/            # Productos nuevos o modificados
│   └── ventas/               # Ventas del ERP Bogotá y ventas nuevas
│
├── img/
│   └── datacaos_estrella.png # Diagrama del modelo
│
├── .env.example              # Plantilla de configuración (sin contraseña)
├── requirements.txt          # Librerías necesarias
├── .gitignore
└── README.md
```

---

## 4. Configuración de la conexión

A diferencia de SQLite, donde la base era un archivo, MySQL es un **servidor**: para conectarse hay que indicar dirección, puerto, base, usuario y contraseña. Estos datos van en un archivo `.env`.

Como el `.env` tiene la **contraseña**, **no lo subimos al repositorio** (está en el `.gitignore`). En su lugar subimos `.env.example`, una plantilla sin datos reales. Para ejecutar el proyecto, se copia esa plantilla, se renombra a `.env` y se llenan los datos de la base de cada estudiante:

```
RUTA_ARCHIVOS=csvs

DB_HOST=34.45.146.241
DB_PORT=3306
DB_NAME=nombre_de_la_base
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
```

La conexión la creamos en `db_utils/load.py` con **SQLAlchemy** y el driver **PyMySQL**:

```python
engine = create_engine("mysql+pymysql://usuario:contraseña@host:puerto/base?charset=utf8mb4")
```

El `charset=utf8mb4` asegura que las tildes y la ñ se guarden bien (Bogotá, Nicolás).

---

## 5. Flujo de carga

```mermaid
flowchart LR
    A[carga_inicial.py<br/>llena tablas vacías] --> B[pipeline_cliente.py]
    B --> C[pipeline_tienda.py]
    C --> D[pipeline_producto.py]
    D --> E[pipeline_ventas.py<br/>tabla de hechos]
```

**El orden importa.** Cada venta apunta a una fecha, un cliente, una tienda y un producto. Si la venta llega antes que su cliente, no tiene a quién apuntar y MySQL la rechaza por la llave foránea. Por eso primero se cargan las dimensiones y al final los hechos. `ejecutar_todo.py` corre los cinco archivos en ese orden.

Cada pipeline sigue las tres fases de un ETL:

1. **Extraer:** `leer_archivos_csv` lee todos los `.csv` de su carpeta en `csvs/` y los une en un solo DataFrame.
2. **Transformar:** renombramos las columnas de la fuente a las de la tabla (`mapeo_columnas`) y aplicamos las reglas de limpieza.
3. **Cargar:** escribimos en MySQL con la estrategia de cada tabla (sección 7).

---

## 6. Reglas de transformación

Creamos fuentes que simulan datos reales "sucios": espacios de más, minúsculas, filas repetidas, valores inválidos y datos faltantes.

### DimCliente - `pipeline_cliente.py`

| Columna fuente | Columna destino | Regla aplicada | Ejemplo |
|---|---|---|---|
| `COD_CLIENTE` | `ClienteID` | Quitar espacios y pasar a mayúsculas | `" cli0082 "` → `CLI0082` |
| `NOMBRE_CLIENTE` | `NombreCliente` | Mayúscula inicial en cada palabra | `valentina lópez garcía` → `Valentina López García` |
| `GENERO` | `Genero` | Primera letra en mayúscula; solo `F` o `M` | `masculino` → `M` · `X` → se descarta |
| `RANGO_EDAD` | `RangoEdad` | Quitar espacios | `26-35` |
| `CIUDAD` | `Ciudad` | Mayúscula inicial en cada palabra | `medellín` → `Medellín` |
| `SEGMENTO` | `SegmentoCliente` | Solo `Nuevo`, `Regular` o `VIP` | `vip` → `VIP` |

### DimTienda - `pipeline_tienda.py`

| Columna fuente | Columna destino | Regla aplicada | Ejemplo |
|---|---|---|---|
| `COD_TIENDA` | `TiendaID` | Quitar espacios y pasar a mayúsculas | `" t06 "` → `T06` |
| `NOMBRE_TIENDA` | `NombreTienda` | Quitar espacios (se respeta el nombre original) | `DataCaos Pereira` |
| `CIUDAD` | `Ciudad` | Mayúscula inicial en cada palabra | `pereira` → `Pereira` |
| `REGION` | `Region` | Mayúscula inicial en cada palabra | `eje cafetero` → `Eje Cafetero` |
| `FECHA_APERTURA` | `FechaApertura` | De `dd/mm/aaaa` a `aaaa-mm-dd`; si es inválida se descarta | `01/06/2023` → `2023-06-01` |

### DimProducto - `pipeline_producto.py`

| Columna fuente | Columna destino | Regla aplicada | Ejemplo |
|---|---|---|---|
| `COD_PRODUCTO` | `ProductoID` | Quitar espacios y pasar a mayúsculas | `" prd039 "` → `PRD039` |
| `NOMBRE_PRODUCTO` | `NombreProducto` | Quitar espacios | `Barra de sonido` |
| `MARCA` | `MarcaProducto` | Quitar espacios (se respetan marcas como `SoundMax`) | `SoundMax` |
| `CATEGORIA` | `NombreCategoria` | Solo la primera letra en mayúscula | `CELULARES` → `Celulares` |
| `PROVEEDOR` | `NombreProveedor` | Quitar espacios | `Maquilas del Norte` |
| `PAIS_PROVEEDOR` | `PaisProveedor` | Mayúscula inicial en cada palabra | `méxico` → `México` |
| `PRECIO_LISTA` | `PrecioListado` | Texto a número; solo precios mayores a 0 | `"$459.900"` → `459900` · `-45000` → se descarta |

### VentasFact - `pipeline_ventas.py`

| Columna fuente | Columna destino | Regla aplicada | Ejemplo |
|---|---|---|---|
| `COD_TIENDA`, `COD_PRODUCTO`, `COD_CLIENTE` | `TiendaID`, `ProductoID`, `ClienteID` | Quitar espacios y pasar a mayúsculas | `" t01 "` → `T01` |
| `FECHA_VTA` | `FechaID` | De `dd/mm/aaaa` a `aaaammdd` | `03/01/2024` → `20240103` |
| `DESCUENTO_PCT` | `Descuento` | De porcentaje a fracción | `5` → `0.05` |
| (calculada) | `ValorVenta` | Unidades × Precio × (1 − Descuento) | `1 × 3014600 × 0.95` → `2863870` |
| (generada) | `VentaID` | Consecutivo después del último de la base | `V002201` |

### Reglas comunes

- **Datos obligatorios:** todas las columnas son `NOT NULL`, así que descartamos las filas con algún dato vacío.
- **Duplicados:** en las dimensiones, si un ID aparece varias veces en el archivo, conservamos el **último** registro por ser el más reciente. En las ventas eliminamos las filas repetidas.

---

## 7. Estrategia de carga

Cada tipo de tabla necesita una forma distinta de cargar:

| | Carga inicial | Dimensiones | Tabla de hechos |
|---|---|---|---|
| **Archivo** | `carga_inicial.py` | `pipeline_cliente/tienda/producto.py` | `pipeline_ventas.py` |
| **Función** | `carga_inicial_tabla` | `actualizar_dimension` | `preparar_datos_para_carga` + `cargar_datos_en_db` |
| **Qué hace** | Inserta solo los registros que faltan | Inserta los nuevos y actualiza los que cambiaron | Agrega solo las ventas nuevas y válidas |

### Dimensiones: UPSERT y SCD Tipo 1

Un cliente o un producto ya puede existir en la tabla. Si usáramos `append`, MySQL rechazaría la carga porque `ClienteID`, `TiendaID` y `ProductoID` son **llave primaria** y no se pueden repetir; además, `append` no puede modificar un registro. Por eso usamos **UPSERT** (UPDATE + INSERT).

En MySQL el UPSERT se escribe con `ON DUPLICATE KEY UPDATE` (ejemplo con DimTienda):

```sql
INSERT INTO DimTienda (TiendaID, NombreTienda, Ciudad, Region, FechaApertura)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    NombreTienda  = VALUES(NombreTienda),
    Ciudad        = VALUES(Ciudad),
    Region        = VALUES(Region),
    FechaApertura = VALUES(FechaApertura);
```

- Si el `TiendaID` no existe, se **inserta**.
- Si ya existe (llave duplicada), se **actualizan** las demás columnas con el valor nuevo (`VALUES(columna)`).

Antes de ejecutarla, la función compara cada registro con la tabla para contar cuáles son nuevos, cuáles cambiaron y cuáles vienen iguales, y solo envía los nuevos y los que cambiaron.

Esta estrategia es **SCD Tipo 1** (*Slowly Changing Dimension*): cuando un dato cambia, el valor nuevo reemplaza al anterior y no se guarda historial. La elegimos porque para el análisis de ventas solo nos interesa el dato vigente.

### Tabla de hechos: validación y carga sin duplicados

Aquí sí usamos `append`, como en `pipeline_erp.py`, porque cada venta es un evento nuevo. Pero antes de cargar, `preparar_datos_para_carga` hace cuatro pasos:

1. Convierte la fecha en `FechaID` (`2024-01-03` → `20240103`).
2. **Valida las referencias:** descarta las ventas cuya fecha, tienda, producto o cliente no exista en su dimensión, porque MySQL las rechazaría por la llave foránea.
3. **Quita las ventas ya cargadas:** compara fecha, tienda, producto, cliente, unidades y precio contra `VentasFact`, para no meter dos veces la misma venta.
4. Genera el `VentaID` consecutivo a partir del último de la base.

### Sin duplicados al repetir

En las tres estrategias, antes de cargar comparamos con lo que ya hay en la base. Por eso ejecutar el proceso varias veces **no duplica datos**: desde la segunda ejecución todo sale en 0.

---

## 8. Instalación y ejecución

**Requisitos:** Python 3.10 o superior y acceso a la base MySQL.

```powershell
# 1. Clonar el repositorio
git clone https://github.com/valentinalopezgrc/actualizacion-dimensiones.git
cd actualizacion-dimensiones

# 2. Crear y activar el entorno virtual
py -m venv env
.\env\Scripts\activate

# 3. Instalar las librerías
pip install -r requirements.txt

# 4. Crear el .env a partir de la plantilla y llenar los datos de conexión
copy .env.example .env

# 5. Ejecutar todo el proceso
python ejecutar_todo.py
```

También se puede ejecutar cada archivo por separado (`python pipeline_cliente.py`, etc.), respetando el orden de la sección 5.

**Librerías utilizadas:**

| Librería | Uso |
|---|---|
| `pandas` | Lectura de CSV y transformación de datos |
| `python-dotenv` | Lectura de la configuración del `.env` |
| `sqlalchemy` | Conexión a la base de datos |
| `pymysql` | Driver para comunicarse con MySQL |
| `cryptography` | Requerida por PyMySQL para autenticarse en MySQL 8 |

---

## 9. Datos de prueba y resultados

Creamos los CSV de `csvs/clientes`, `csvs/tiendas`, `csvs/productos` y `csvs/ventas` para probar cada caso: registros nuevos, modificados, sin cambios e inválidos. Usamos pocos registros a propósito, al menos uno por cada caso, para poder seguir fila por fila qué le pasa a cada uno.

### Resultado de la primera ejecución (base vacía)

```
===== carga_inicial.py =====
DimFecha: 366 insertados | 0 ya existían
DimTienda: 5 insertados | 0 ya existían
DimCliente: 80 insertados | 0 ya existían
DimProducto: 38 insertados | 0 ya existían
VentasFact: 2200 insertados | 0 ya existían

===== pipeline_cliente.py =====
DimCliente -> nuevos: 5 | actualizados: 2 | sin cambios: 1

===== pipeline_tienda.py =====
DimTienda -> nuevos: 2 | actualizados: 1 | sin cambios: 1

===== pipeline_producto.py =====
DimProducto -> nuevos: 3 | actualizados: 2 | sin cambios: 1

===== pipeline_ventas.py =====
Ventas descartadas por referencias que no existen: 1
Ventas que ya estaban en la base (se omiten): 9
VentasFact -> ventas nuevas cargadas: 4
```

### Detalle de cada caso

| Tabla | Nuevos | Actualizados | Descartados |
|---|---|---|---|
| **Cliente** | CLI0081 a CLI0085 | CLI0005 (Regular → VIP), CLI0010 (Barranquilla → Cartagena) | CLI0086 (sin nombre), CLI0087 (género `X`) |
| **Tienda** | T06 Pereira, T07 Cartagena | T03 (Cali Norte → Cali Chipichape) | T08 (fecha inválida) |
| **Producto** | PRD039, PRD040, PRD041 | PRD010 (1.932.000 → 1.850.000), PRD020 (60.000 → 65.000) | PRD042 (precio negativo), PRD043 (precio no numérico) |
| **Ventas** | 4 ventas de clientes, tiendas y productos nuevos (V002201 a V002204) | - | 1 venta de CLI0999 (cliente que no existe) · 9 ventas del ERP Bogotá que ya estaban cargadas |

### Estado final de la base

| | Fechas | Clientes | Tiendas | Productos | Ventas |
|---|---|---|---|---|---|
| **Después de la carga inicial** | 366 | 80 | 5 | 38 | 2.200 |
| **Después de las actualizaciones** | 366 | 85 | 7 | 41 | 2.204 |

Al ejecutar `ejecutar_todo.py` por segunda vez, todo sale en 0 y los totales no cambian.

---

## 10. Verificación en DBeaver

Con la conexión a la base MySQL:

```sql
-- Totales (deben dar 85 / 7 / 41 / 2204)
SELECT (SELECT COUNT(*) FROM DimCliente)  AS clientes,
       (SELECT COUNT(*) FROM DimTienda)   AS tiendas,
       (SELECT COUNT(*) FROM DimProducto) AS productos,
       (SELECT COUNT(*) FROM VentasFact)  AS ventas;

-- Clientes actualizados: CLI0005 pasa a VIP y CLI0010 a Cartagena
SELECT ClienteID, SegmentoCliente, Ciudad FROM DimCliente
WHERE ClienteID IN ('CLI0005','CLI0010');

-- Productos con precio actualizado
SELECT ProductoID, PrecioListado FROM DimProducto
WHERE ProductoID IN ('PRD010','PRD020');

-- Ventas nuevas
SELECT * FROM VentasFact WHERE VentaID > 'V002200';
```

---

## 11. Cambios respecto a la versión SQLite

| Aspecto | SQLite | MySQL |
|---|---|---|
| Base de datos | Archivo `instance/datacaos_estrella.db` | Servidor en la nube |
| Conexión | `sqlite3.connect("ruta")` | SQLAlchemy + PyMySQL con host, usuario y contraseña |
| Configuración | `.env` con rutas (se subía) | `.env` con contraseña (no se sube; se sube `.env.example`) |
| UPSERT | `ON CONFLICT(llave) DO UPDATE SET col = excluded.col` | `ON DUPLICATE KEY UPDATE col = VALUES(col)` |
| Marcadores de datos | `?` | `%s` |
| Número del VentaID | `SUBSTR` y `CAST(... AS INTEGER)` | `SUBSTRING` y `CAST(... AS UNSIGNED)` |
| Datos iniciales | La base ya venía llena | Tablas vacías: agregamos `carga_inicial.py` |
| Tabla de hechos | `pipeline_erp.py` (visto en clase) | `pipeline_ventas.py`, con validación de referencias y sin duplicados |

Además, en `pipeline_ventas.py` indicamos el formato de la fecha de origen (`dd/mm/aaaa`). Sin ese formato, pandas interpreta `03/01/2024` como 1 de marzo (formato mes/día) en lugar de 3 de enero.