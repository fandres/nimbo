# Informes

Abre **Informes** en el menú lateral y elige **Ventas**, **Compras**, **Retenciones**, **Gastos**, **Dinero** o **Rentabilidad**.
Cada pestaña conserva sus filtros durante la sesión y comienza en el mes actual,
desde el primer día hasta hoy (Retenciones comienza en el año actual).
Usa **Este mes**, **Mes pasado**, **Este año** o **Personalizado**. Los calendarios
Desde/Hasta permiten consultar cualquier período anterior. **Limpiar filtros**
restablece el período inicial y los filtros de la pestaña actual.

La vista previa se actualiza al cambiar filtros. **Actualizar** vuelve a consultar
los registros y las opciones de cuentas/categorías. **Exportar PDF** guarda el
contenido de la pestaña activa que estás viendo; si el archivo existe pide confirmación para reemplazarlo.
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

La consulta y exportación no modifican operaciones ni reemplazan los certificados de retención o documentos
originales. Exportación PDF A4 horizontal con ajuste de texto y encabezados de
tabla repetidos cuando hay varias páginas.

## Retenciones

Comienza en el año actual. Filtra por fechas, cliente, cédula/NIT, correo,
factura o estado del certificado. Incluye ventas vigentes con retención y distingue
las registradas al cobrar, las pendientes de cobro y las históricas informativas.

En **Gestionar certificados**, cada cliente y año tiene un estado: **Pendiente de
solicitar**, **Solicitado** o **Recibido**, además de una nota opcional y un historial.
El estado se guarda al seleccionarlo; la nota, al salir del campo. Estos cambios
no modifican ventas, cobros ni saldos. El PDF incluye los estados y el detalle de
las facturas del período consultado.

El estado corresponde al año completo aunque filtres un mes. Los importes sí
corresponden al período filtrado. Una búsqueda selecciona el grupo del cliente
y año con todas sus facturas dentro de ese período.

Se agrupa por identificación; si falta, se utiliza el nombre normalizado y se
avisa para revisarlo. Corregir la identificación crea otro grupo pendiente: el
seguimiento anterior no se transfiere automáticamente.

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

### Soportes del certificado

En **Gestionar certificados**, usa el clip de la columna **Soportes** para adjuntar
PDF, PNG o JPG, abrir una copia, consultar su carpeta o quitarla del seguimiento.
El número junto al clip indica los archivos activos del cliente y año.

Las copias se guardan en `Documentos/<año>/Retenciones/cliente-<id>/` y se incluyen
en los respaldos. El identificador interno evita mezclar clientes con nombres
iguales. Se conserva el archivo original. Al quitar un adjunto, la copia permanece
en la carpeta, igual que con los demás documentos de Nimbo.

Después de adjuntar correctamente, puedes aceptar marcar el certificado como
**Recibido**. Si eliges no hacerlo, conserva su estado. Quitar un documento no cambia
el estado automáticamente. La fecha del filtro no cambia la asociación anual del
soporte. No se envían correos ni se interpreta automáticamente el contenido.
