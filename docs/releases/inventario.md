# Inventario por modelo · desarrollo posterior a alfa 0.2

## Inicio

Al abrir el programa sin inventario configurado, se ofrece el asistente. También
se abre desde el nuevo menú **Inventario**. Puede posponerse: mientras esté pendiente,
se muestra que las ventas no controlan ni descuentan existencias.

- **Confirmar existencias actuales por modelo · recomendado:** escribe las unidades
  que tienes físicamente; confirma también los ceros y revisa modelos inactivos.
- **Usar las compras recibidas registradas:** revisa la suma de las recepciones
  vigentes. Los pedidos aún en tránsito no se incluyen.

La confirmación es única por base. No se descuentan ventas anteriores (incluidas
las pruebas) ni se vuelven a sumar las recepciones incluidas en la apertura.
Si todavía no has creado tu catálogo, puedes posponer el asistente y volver después.

## Después de iniciar

Las nuevas recepciones suman unidades; guardar una venta descuenta stock aunque
el cobro esté pendiente. Esto se decide por el momento del registro, no por la
fecha escrita en la venta. Los servicios no tienen límite de existencias.

Nueva venta muestra disponible y restante, suma líneas repetidas del mismo modelo
y limita la cantidad. La comprobación final y el descuento se guardan juntos:
otra ventana no puede vender las mismas últimas unidades. Si el stock cambió,
se avisa al guardar sin guardar parcialmente la venta.

Anular una venta nueva devuelve sus unidades una sola vez. Anular una venta anterior
al inicio no aumenta stock, porque nunca lo descontó. Deshacer una recepción nueva
se permite solo si quedan unidades suficientes. Las recepciones incluidas en la
apertura no pueden deshacerse; cualquier corrección de existencias se registra con
un ajuste y motivo. Editar costos de compras no cambia cantidades disponibles.

## Ajustes manuales

En **Configuración → Inventario**, activa «Permitir modificar las existencias desde
Inventario». Está desactivado por defecto y se guarda en la base de datos.
Selecciona el modelo y pulsa **Ajustar existencias**. Escribe el nuevo total y el
motivo. Antes de guardar se pregunta si estás seguro, mostrando valor actual,
nuevo valor y diferencia. Un cambio concurrente invalida el ajuste hasta actualizar.
Deshabilitar la opción vuelve a impedir ajustes, incluso desde ventanas ya abiertas.

**Ver historial** conserva el inicio, recepciones, ventas, anulaciones y ajustes.
Cambiar un producto con movimientos a servicio queda bloqueado para no perder su
relación con las existencias. Los ajustes no modifican compras, ventas ni dinero.

## Datos y alcance

Esquema SQLite 12, con respaldo automático antes de migrar. Las bases anteriores
no se inicializan silenciosamente. Los binarios alfa 0.2 entregados siguen en esquema
11: no pueden abrir una base ya actualizada a 12. Usa `./abrir.sh` para probar este
desarrollo; no se han reconstruido los paquetes de distribución en esta etapa.

Quedan pendientes identificación individual/códigos de barras, valoración de
inventario, costo de ventas y el asistente futuro para modalidad de compras.
