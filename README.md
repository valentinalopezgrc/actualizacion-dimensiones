# Actualización de dimensiones - DataCaos (esquema estrella)

Pipelines en Python para actualizar las dimensiones **DimCliente**, **DimTienda** y **DimProducto** de la base `datacaos_estrella`, tomando como base el ETL de la clase del 22 de septiembre (`pipeline_erp.py`).

## Estructura

```
├── pipeline_cliente.py     -> actualiza DimCliente
├── pipeline_tienda.py      -> actualiza DimTienda
├── pipeline_producto.py    -> actualiza DimProducto
├── pipeline_erp.py         -> ETL de ventas visto en clase
├── utils/reglas.py         -> reglas de limpieza y transformación
├── db_utils/load.py        -> conexión y carga a la base de datos
├── csvs/
│   ├── clientes/fuente_clientes.csv
│   ├── tiendas/fuente_tiendas.csv
│   └── productos/fuente_productos.csv
├── instance/datacaos_estrella.db
└── .env                    -> rutas de archivos y base de datos
```

## Cómo funciona cada pipeline

1. **Extraer:** lee todos los CSV de su carpeta dentro de `csvs/`.
2. **Transformar:** renombra columnas, quita espacios, corrige mayúsculas, formatea fechas y precios, valida valores y elimina filas incompletas o repetidas.
3. **Cargar:** compara con lo que ya existe en la dimensión y hace un **UPSERT** (SCD Tipo 1):
   - ID nuevo → se inserta.
   - ID existente con cambios → se actualiza.
   - ID existente sin cambios → no se toca.

## Ejecución

```bash
python -m venv env
env\Scripts\activate          # Windows
pip install pandas python-dotenv

python pipeline_cliente.py
python pipeline_tienda.py
python pipeline_producto.py
```

Si se ejecuta un pipeline dos veces seguidas, la segunda vez todos los registros salen como "sin cambios".
