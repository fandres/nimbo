# Acumulado de compras sin guardar

Se añade Total de productos dentro de Qué compramos y una columna Total mercancía
por línea. Los importes se actualizan al aplicar, editar o quitar productos del
formulario. Los cargos adicionales actualizan el total general sin duplicar la
mercancía. Se utiliza el importe total original exacto y su conversión a COP.

El cálculo de vista previa valida los importes y cantidades, sin exigir todavía
proveedor, fecha ni estados completos. El guardado mantiene la validación completa.
Prueba de regresión: añadir dos líneas, editar una, registrar un cargo, quitar una
línea, comprobar los acumulados y confirmar que no se guardan datos ni se permite
omitir el proveedor obligatorio.
