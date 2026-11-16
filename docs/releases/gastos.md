# Gastos y préstamos — desarrollo posterior a alfa 0.2

Disponible desde `./abrir.sh`. Los AppImage y ZIP publicados de alfa 0.2 todavía
no incluyen esta entrega.

## Uso

Gastos aparece en el menú lateral. Inicio → Anotar un gasto abre el formulario.

- **Resumen:** gráficos por categoría, comparación con el período equivalente y
  últimos cuatro gastos vigentes, según período y cuenta. Incluye gastos pendientes;
  no es un informe de caja. Las comisiones pendientes de cobro se señalan como estimadas.
- **Movimientos:** búsqueda por concepto, categoría, estado, cuenta y período.
  Los importes de las tarjetas corresponden a los filtros visibles. Más filtros
  permite consultar anulados, excluidos siempre de los totales. Doble clic abre el
  detalle; las acciones permiten editar, marcar pagado o consultar el origen.
- **Préstamos:** registrar nombre/entidad, fecha y capital pendiente inicial.
  Cada pago realizado distingue capital e intereses y exige cuenta y fecha.
  Solo los intereses alimentan Gastos. No se genera automáticamente un desembolso
  en una cuenta ni una tabla de amortización.

Las categorías se crean, renombran o desactivan en Configuración → Gastos o desde
Nuevo gasto → Nueva / editar categorías. Desactivar no elimina históricos.
Los cambios de nombre se reflejan en los listados y filtros de los gastos existentes.

Nuevo gasto usa la fecha actual de forma predeterminada. El clic en la fecha abre
el calendario y el primer clic al entrar en un importe selecciona su contenido.
Un gasto pendiente no requiere cuenta; al marcarlo pagado se solicita cuenta y
fecha. Fecha estimada de pago, nota y referencia textual del comprobante son opcionales.
Esta entrega no adjunta archivos de comprobantes.

## Comparaciones

El mes en curso llega hasta hoy y se compara con los mismos días del mes anterior,
limitados al último día si ese mes es más corto. Un mes completo se compara con el
mes anterior completo. Un rango personalizado se compara con el intervalo anterior
inmediato de igual duración. Las fechas exactas se muestran junto al gráfico.
Con una base anterior de cero se indica «Sin base de comparación»; no se inventa
un porcentaje. El color de la variación es neutro.

Los filtros de búsqueda/categoría/estado de Movimientos no se aplican ocultamente
al Resumen. Período y cuenta sí se comparten. «Ver todos en Movimientos» conserva
período/cuenta y limpia los filtros exclusivos del detalle.

## Origen e historial

Comisiones y envíos se consultan directamente desde Ventas: no se copian a una
segunda tabla de gastos. Se imputan a la fecha de la venta; la comisión pasa de
estimada a real al registrar el cobro. Anular una venta excluye sus costos de los
totales. «Ver venta» permite consultar/corregir allí los datos de origen.
Un envío pagado con tarjeta de crédito se identifica como pago a la transportadora;
no debe confundirse con el pago de la tarjeta desde una cuenta bancaria.

Los intereses de cuotas se consultan desde Préstamos sin duplicación. El capital
se informa aparte. Anular un pago exige motivo, resta sus intereses de los gastos
y restituye el capital al saldo pendiente. Los pagos se corrigen anulando y
registrando de nuevo. El saldo inicial del préstamo solo se corrige antes de que
exista historial de pagos, incluidos los anulados.

Los gastos manuales conservan versiones al crear, editar, pagar y anular. La
validación de revisión evita sobrescribir un formulario obsoleto y la identificación
de solicitudes evita un doble registro por reintento. Las escrituras son atómicas.

Dentro de un mismo día, los gastos nuevos se ordenan por creación y número de
registro. Las ventas históricas no tienen fecha de creación: sus costos usan fecha
de venta y número de venta como desempate.

## Base de datos y compatibilidad

Se actualiza al esquema **13**, con respaldo automático del archivo existente
antes de migrar y rollback si falla la migración. No se reinicia el inventario.
Las versiones anteriores no pueden abrir una base actualizada: usar el código
actual con `abrir.sh`; conservar el respaldo para volver a una versión anterior.
Durante el desarrollo y las pruebas solo se usaron bases temporales.

Validación final: 253 pruebas aprobadas en Linux local, Debian 13 y Python para
Windows bajo Wine. Revisión independiente sin hallazgos pendientes. Capturas con
datos ficticios en `docs/capturas/gastos-*.png` y `docs/capturas/nuevo-gasto.png`.
La validación nativa de los próximos paquetes en Windows 11 sigue pendiente.
El módulo Dinero (saldos y flujo de caja) no forma parte de esta entrega.

## Conceptos frecuentes

Desde tres caracteres, el concepto sugiere hasta quince coincidencias de gastos
manuales vigentes, sin distinguir mayúsculas. Se busca también dentro del texto.
Al elegir una sugerencia con clic o Enter, se completa el concepto y la categoría
usada en su registro actualizado más recientemente. Los conceptos repetidos se
agrupan sin distinguir mayúsculas. No se copian importes, cuentas ni fechas, ni se
guarda automáticamente el gasto. Se puede escribir un concepto nuevo y modificar
la categoría propuesta. Si la categoría más reciente está deshabilitada, ese
concepto no se ofrece; las categorías se vuelven a comprobar al seleccionar.
