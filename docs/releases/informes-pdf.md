# Informes PDF · desarrollo posterior a alfa 0.3

## Dinero
Dinero → Movimientos → Exportar PDF. Respeta fechas, cuenta y búsqueda; separa
totales de tabla y flujo de efectivo. Ver dinero.md para las reglas completas.

## Ventas
Ventas → Movimientos → Exportar PDF. Respeta todos los filtros: fechas, estado de
cobro, cuenta, búsqueda, vigentes/anuladas, retención y límites mínimo/máximo.
Para preparar el listado anual de retenciones, elige el rango del año en el
selector de fechas y Más filtros → Retención en la fuente → Con retención.

Incluye cliente, cédula/NIT cuando se registró, referencia de factura, forma de
pago/cuenta, estado, total y retención informativa del 2,5 % sobre el total con
envío cobrado. No sustituye certificados ni descuenta retención de los importes.
Totales recibido/pendiente son importes brutos, como en la pantalla, no depósitos
netos bancarios. Anuladas identificadas y excluidas de los totales y retenciones.

PDF A4 horizontal con encabezados repetidos, paginación y texto que se adapta al
ancho. Usa el mismo escritor Qt de Dinero y guardado atómico. Si se cancela el
diálogo no se escribe. No se modifican registros ni adjuntos. Los portables alfa
0.3 ya entregados no incluyen estas funciones hasta la próxima compilación.
