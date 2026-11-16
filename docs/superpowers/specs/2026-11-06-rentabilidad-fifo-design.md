# Costo de ventas y rentabilidad FIFO

Estado: diseño técnico aprobado por el usuario el 6 de noviembre de 2026.
El reparto automático de costos para un solo modelo ya se implementa como cambio independiente autorizado.

## Decisiones confirmadas
Usuario: FIFO automático; método configurable en una versión futura, sin selector
manual de pedido en esta entrega. Completar o corregir costos de compra actualiza
la rentabilidad de las ventas relacionadas, conservando las revisiones de compra.
Pedidos con un único modelo reparten automáticamente cada cargo por unidades;
pedidos mixtos mantienen asignaciones manuales. Totales en centavos sin pérdidas
por redondeo. No distribuir el IVA de productos una segunda vez.

## Alcance técnico de la primera entrega
1. Normalización de costos de un mismo modelo en formulario y repositorio. La
   vista previa actualiza costo por unidad; al guardar se conservan las revisiones.
2. Reconstrucción de lotes FIFO a partir del historial de movimientos existente.
   Solo unidades ya recibidas/confirmadas pueden respaldar ventas. Orden FIFO por
   fecha de recepción, desempate estable por identificadores; aplicar salidas en
   orden de registro, tal como descuenta stock Nimbo (no reordenar por fechas de
   venta introducidas retrospectivamente).
3. Informe Rentabilidad de solo lectura dentro de Informes, con período y búsqueda.
   Detalle de ventas, costo trazable, margen después de comisiones/envío, procedencia
   de compra y advertencias. El PDF usa el mismo snapshot.

## Datos anteriores y excepciones
- Apertura desde compras recibidas: vincular los lotes de las recepciones incluidas
  en inventory_baseline_receipts. No duplicar esas entradas.
- Solo valorar la apertura con recepciones cuando inventory_state.mode sea receipts: la tabla de recepciones de apertura también existe en modo físico y por sí sola no demuestra el costo.
- Conteo físico y ajustes positivos sin compra: lote sin costo conocido. No inventar
  un costo ni enlazarlo a compras arbitrarias. Ventas sin control de stock previo:
  costo desconocido. Mostrar «Sin costo trazable» y no calcular margen definitivo.
- Servicios: sin costo directo registrado; avisar que su rentabilidad no está
  determinada. No interpretarlos silenciosamente como costo cero.
- Anulación/devolución de cantidades por edición restaura los tramos de lote de esa
  venta, empezando por los últimos tramos consumidos si la restitución es parcial. Incrementos consumen unidades disponibles. Borrados definitivos conservan
  el efecto del historial de movimientos y su compensación, pero no aparecen como
  ventas del informe.
- Ajustes negativos consumen FIFO, separados del costo de ventas. No son ventas.
- Antes de deshacer una recepción con unidades asignadas a ventas vigentes, exigir corregir o anular esas ventas; disponer de otras unidades del mismo modelo no sustituye su procedencia.
- Recepciones antiguas ya revertidas o referencias históricas que ya no coincidan:
  marcar costo desconocido cuando afecten una venta, nunca sustituir por otro costo
  sin advertencia. En la reconstrucción de una reversión antigua, quitar primero las unidades aún disponibles de esa recepción y cubrir su faltante mediante salidas FIFO de las existencias restantes, señalando la inconsistencia en la valoración. Así las cantidades cuadran con el historial real, pero no se afirma un costo definitivo para las ventas afectadas. Mantener las demás validaciones de stock.
- Costos pendientes o cargos sin distribuir: costo conocido parcial y margen
  provisional. Mostrar motivo y compras de origen. Los cambios de costo actualizan
  automáticamente la lectura; no reescriben importes ni fechas de la venta.

## Importes y significado
Costo de mercancía usa la valoración registrada de compras (base, IVA registrado
y cargos asignados), conservando su política actual; no determina IVA descontable.
Ingreso de venta sin IVA de venta + envío cobrado, menos costo de mercancía,
comisión real (o estimada identificada) y costo del envío. La retención no es un
segundo gasto. No descontar otra vez comisiones/envíos al restar gastos del período.
Para resultado del período excluir de gastos los movimientos automáticos originados
en ventas ya considerados en el margen. Mostrar que es resultado de gestión con
costos registrados, no liquidación fiscal. Si falta costo trazable de cualquier
venta del filtro, el resultado completo queda no disponible, con conteo de ventas
pendientes de valorar; se permite consultar los costos parciales conocidos.

## Persistencia y verificación
La primera versión calcula a partir de movimientos y revisiones ya existentes,
sin migración destructiva ni crear una segunda contabilidad de cantidades. Se
prefiere esta reconstrucción determinista a tablas de asignación adicionales que
podrían desincronizarse de correcciones antiguas. No modificar registros al abrir
un informe. Pruebas: dos lotes a distinto costo, venta entre lotes, redondeo,
costo tardío, apertura física/recepciones, ajuste, edición/anulación/borrado,
referencias revertidas, servicios, IVA y gastos sin duplicación.

## Revisión de diseño
Revisor independiente confirmó la viabilidad de reconstruir cantidades y origen desde los movimientos. Se precisaron restituciones parciales, apertura física y reversiones; estos comportamientos fueron aprobados para implementar el motor FIFO.
