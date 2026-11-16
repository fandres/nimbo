# Costos de compras por subtipo y excepciones por producto

## Objetivo
Mostrar en cada compra los conceptos pertinentes a sus productos y evitar pendientes innecesarios, sin perder importes ni alterar compras anteriores.

## Enfoques considerados
- Solo por producto: preciso, pero obliga a repetir la configuración en cada modelo.
- Por subtipo con excepciones por producto: elegido por el usuario; permite reutilizar reglas y ajustar casos concretos.

## Configuración
En Configuración → Costos de compras se mantienen la creación, edición y desactivación de conceptos. Se añade una sección «Aplicación por producto» con dos vistas:
- Subtipos: seleccionar un subtipo y marcar sus conceptos aplicables.
- Productos: buscar por código o nombre; «Heredar del subtipo» activado por defecto. Al desactivarlo, definir la lista completa para ese producto, partiendo de la selección heredada. Se puede volver a heredar.

Sin configuración específica se conservan todos los conceptos activos, manteniendo el comportamiento actual. Una selección explícita vacía significa «sin costos adicionales» y se distingue de no haber configurado reglas. Las relaciones usan identificadores estables para soportar cambios de nombre.

## Nueva compra
Al agregar, cambiar o quitar productos se muestra la unión de sus conceptos aplicables. Un concepto compartido aparece una sola vez. Sin productos se muestra una indicación para agregarlos antes de determinar los costos.

Los conceptos excluidos no generan pendientes. Si un concepto deja de aplicar pero tiene un cargo o una asignación ya introducida, se conserva visible con aviso para revisión; nunca se elimina un valor automáticamente. Las reglas orientan la selección de conceptos, no reparten automáticamente sus importes entre modelos.

Se mantiene la exclusión entre IVA por producto e IVA total de factura; esa protección prevalece sobre las reglas de configuración.

## Compras guardadas
Conservan sus conceptos e importes históricos. Cambiar las reglas en Configuración no modifica una compra guardada al abrirla. «Actualizar conceptos» permite aplicar expresamente las reglas actuales a los productos del pedido, conservando todos los cargos y asignaciones existentes y avisando de diferencias.

## Persistencia y validación
Migración aditiva para las reglas de subtipo y las excepciones de producto, sin cambiar compras ni datos del catálogo existentes. Pruebas de herencia, selección vacía, excepciones, mezcla de modelos, cambio de subtipo, conservación del historial y cargos, y compatibilidad con el bloqueo de IVA.

## Fuera de alcance
No se deducen costos a partir del proveedor, país o modalidad de importación. No se modifica el cálculo fiscal ni se distribuyen costos automáticamente.
