# Informes

Abre **Informes** en el menú lateral y elige **Ventas**, **Gastos**, **Dinero** o **Rentabilidad**.
Cada pestaña conserva sus filtros durante la sesión y comienza en el mes actual,
desde el primer día hasta hoy. Puedes elegir otro mes/año o cambiar Desde/Hasta
con el calendario. Más años permite consultar períodos antiguos.

La vista previa se actualiza al cambiar filtros. **Actualizar** vuelve a consultar
los registros y las opciones de cuentas/categorías. **Exportar PDF** guarda el
contenido que estás viendo; si el archivo existe pide confirmación para reemplazarlo.
Un rango inválido o un error de consulta limpia el informe y bloquea su exportación.

- **Ventas:** búsqueda, cuenta, estado del cobro, vigencia y retenciones. Los
  importes son brutos; no equivalen al depósito neto ni a utilidad. Las anuladas
  no suman. El PDF conserva la distinción histórica de retenciones informativas.
- **Gastos:** categorías, cuentas, estado, vigencia y comisiones de plataforma.
  Puedes consultar por fecha del gasto o por fecha de pago. Se incluyen una sola
  vez comisiones/envíos de ventas e intereses ya registrados. El capital de
  préstamos queda fuera. Las comisiones estimadas y los cargos a tarjeta se
  identifican: estos últimos no significan una salida de efectivo.
- **Dinero:** movimientos por fecha, cuenta y búsqueda. Reutiliza las reglas del
  módulo Dinero para transferencias internas, tarjetas y retenciones. El flujo
  no equivale a utilidad ni a saldo disponible.

No modifica registros ni reemplaza los certificados de retención o documentos
originales. Exportación PDF A4 horizontal con ajuste de texto y encabezados de
tabla repetidos cuando hay varias páginas.

## Rentabilidad

Selecciona el período y consulta las ventas vigentes. El costo FIFO usa primero
las unidades de las compras recibidas más antiguas disponibles al registrar la
venta. Una venta con fecha retroactiva conserva el orden real de los movimientos
de inventario. Cada venta muestra las compras de origen y su margen tras mercancía,
comisión y envío. La retención es un anticipo, no otro gasto del resultado.

- **Costos completos:** mercancía valorada con costos registrados y distribuidos.
- **Provisional:** quedan costos por completar/distribuir o una comisión estimada.
  Corregir los costos de la compra actualiza el informe, sin alterar la venta.
- **Sin costo trazable:** ventas anteriores al control de inventario, existencias
  de apertura física, ajustes positivos sin compra, servicios sin costo directo o
  recepciones históricas revertidas. No se les asigna costo cero. El resultado
  completo del período permanece no disponible si alguna venta está en este estado.

La apertura **desde compras recibidas** sí permite identificar su costo. Los ajustes
negativos consumen existencias FIFO, pero no se registran como ventas. Corregir o
anular una venta restituye sus unidades a los lotes de origen. No se puede deshacer
una recepción que respalda ventas vigentes: primero deben corregirse o anularse.

El resultado del período resta los demás gastos registrados por fecha del gasto,
sin duplicar las comisiones y los envíos automáticos de ventas. Incluye intereses,
no pagos de capital. Al buscar un cliente/producto/factura se muestra el margen de
las ventas encontradas; limpia la búsqueda para ver el resultado completo con los
gastos del período, ya que estos no se atribuyen arbitrariamente a un cliente.

Es un **resultado de gestión**, no una liquidación fiscal ni flujo de caja. El costo
de compras conserva su IVA registrado; no determina si es fiscalmente descontable.
El PDF exporta exactamente la vista previa consultada, incluidos sus avisos.
