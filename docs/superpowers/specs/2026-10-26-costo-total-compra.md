# Costo total o unitario de mercancía

Cambio solicitado: en Producto comprado, seleccionar total de todas las unidades
(predeterminado) o costo por unidad. El total corresponde al producto de esa línea,
no a los gastos adicionales ni a otras máquinas del pedido.

El selector convierte el importe y muestra ambos valores. Cambiar la cantidad en
modo total conserva el total; en modo unitario conserva el precio por unidad.
Cambiar de modo sin editar conserva el total exacto aunque la división produzca
fracciones de centavo; el unitario se señala como aproximado. Escribir un nuevo
unitario o cambiar su cantidad recalcula el total con ese importe.

Se conserva el total original en COP o USD antes de conversión. Migración 15:
columna opcional total_cost_cents, con respaldo y transacción. Las líneas antiguas
mantienen cantidad × costo unitario. Nuevas líneas y ediciones usan el total exacto
para importes, costos por unidad, asignaciones y reapertura.

Verificación: pruebas de ambas formas, cantidades, conservación al alternar,
reapertura, USD y migración desde 14 con rollback. Captura sintética revisada sin
barras de desplazamiento a 850 × 640. No se modifican datos reales en las pruebas.
