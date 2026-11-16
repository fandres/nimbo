# Costos adicionales en un único lugar

Solicitud: quitar los gastos asignados del diálogo Producto comprado. Se confundían
con cargos nuevos; una asignación allí no registraba el cargo en el pedido y podía
superar los costos existentes, impidiendo guardar.

Producto comprado ahora solo edita producto, cantidad, costo total/unitario y moneda.
Las asignaciones anteriores se conservan al editar; las líneas nuevas parten de cero.
El formulario se reduce en altura y orienta al punto 3 para registrar cargos.

En 3 · Costos adicionales se registran todos los cargos. La acción «Distribuir costos
entre productos» reparte esos importes ya registrados por modelo, sin crear gastos.
Muestra límites por concepto y valida que ninguna suma los supere; señala el campo
problemático. Permite dejar importes por distribuir, manteniendo el estado provisional.
La distribución solo se aplica al formulario; Guardar compra persiste todo.

No se modifica el esquema ni se borran asignaciones históricas. Se verifica la
conservación al editar, la ausencia de doble registro y el bloqueo de asignaciones
excesivas, además de la suite general y una captura sintética del producto sin gastos.
