# Retenciones de renta en ventas nuevas

Desde este cambio, «Se aplicó retención» descuenta el 2,5 % del total de la venta del depósito esperado/recibido. La venta conserva su importe bruto. Las comisiones se descuentan además de la retención, sin cambiar su base de cálculo.

Al confirmar el cobro se reflejan dos movimientos vinculados a la venta: el depósito neto en la cuenta elegida y el importe retenido en la cuenta auxiliar «Retenciones de renta», visible en Dinero → Cuentas y en el filtro de movimientos. El saldo auxiliar es automático; no es una cuenta para pagos o transferencias, ni suma al efectivo disponible o al flujo de caja. La retención no se registra como gasto.

Ejemplo sin comisión: venta $3.653.000; retención $91.325; depósito $3.561.675.

La migración 22 conserva el tratamiento informativo de las ventas existentes, incluso si se cobran después de actualizar. Las nuevas ventas usan el descuento. Editar la marca de una nueva venta cobrada actualiza ambos movimientos; anularla los excluye de los saldos. El detalle distingue las ventas históricas informativas.

Pendiente para beta 2: revisión general de colores de botones, anotada en futuras-versiones.md.

## Factura y correo requeridos
En Configuración → Ventas, «Exigir factura y correo del cliente cuando se aplique retención» está activado inicialmente. Puede desactivarse. Se comprueba al guardar una venta nueva o sus cambios; no modifica los datos ya guardados.
Al activar retención en Nueva venta se muestran los campos necesarios. Los vacíos se resaltan en rojo y se enfoca el primero pendiente. El detalle de venta permite completar/editar el correo y guardarlo junto con los demás cambios.
