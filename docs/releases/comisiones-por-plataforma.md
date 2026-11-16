# Comisiones por monto y por plataforma

## Configuración → Formas de pago

La comisión base sigue siendo porcentaje + cargo fijo COP. «Tarifas por monto» permite añadir umbrales Desde (inclusivos). Debajo del primero se usa la base; cada umbral aplica hasta el siguiente y el último no tiene límite superior. La tarifa se aplica al total completo cobrado al cliente, incluido el envío, sin cálculo progresivo por tramos. Aplicar tarifas y luego Guardar cambios conserva la configuración.

## Nueva venta

Aplica automáticamente la tarifa del método de pago y del importe. Se muestra el porcentaje y cargo fijo. «Ajustar comisión» habilita una excepción solo para esta venta; al apagarlo o cambiar de método se recupera la tarifa automática. El importe real del cobro se puede seguir registrando si la plataforma liquida una cifra distinta. Las cuentas de destino no añaden una segunda comisión.

## Gastos

En Más filtros: seleccionar Comisiones de plataforma y Fecha de pago, además del período habitual, para consultar cuánto se pagó a Siste Crédito, Addi u otra forma de pago utilizada. La tarjeta Pagado muestra la suma filtrada. Fecha del gasto conserva la vista por fecha de venta, con pendientes estimados identificados. Fecha de pago excluye pendientes sin cobro. Las ventas anuladas nunca se suman. El resumen, comparación y movimientos respetan plataforma y criterio de fechas; no se crean gastos duplicados.

Las comisiones usan el importe real cuando se confirma el cobro; mientras tanto usan el estimado guardado. El historial conserva el nombre y la tarifa, aunque después se cambie o deshabilite la plataforma.

Base de datos: migración 20, añade tarifas a métodos de pago con copia automática previa y transacción. No modifica importes históricos. Cambios de código; los binarios alfa 0.3 existentes no se recompilan en esta tarea.
