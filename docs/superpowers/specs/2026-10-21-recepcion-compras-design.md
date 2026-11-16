# Recepción completa de compras

## Acuerdo y alcance

Todos los pedidos llegan completos. Un botón «Recibir maquinaria y confirmar
stock» registra la entrada de todas sus unidades. Se permite recibir aunque
falten costos o asignaciones: la advertencia recuerda información por completar,
no bloquea ni confirma pagos. No se consulta una plataforma externa.

Esta entrega registra entradas trazables por compra y muestra unidades recibidas.
La siguiente conectará estas entradas con ventas y el límite de disponibilidad.
Mientras no exista esa conexión, no presentar la suma histórica de entradas como
stock actual disponible: algunas unidades podrían haberse vendido. Mantener
explícito en interfaz que las ventas todavía no descuentan estas entradas.

## Flujo

En Compras, seleccionar pedido o una de sus máquinas y pulsar el botón de recepción.
Solo habilitado en compras vigentes no recibidas. Mostrar resumen no editable de
modelos, códigos y cantidades, fecha de recepción (hoy por defecto, calendario) y
un único botón principal «Confirmar recepción completa». Cancelar no modifica datos.
La fecha estará entre la fecha de compra y hoy, inclusive.

Si hay conceptos pendientes o gastos por asignar, mostrar un aviso naranja con
texto: «Puedes recibir la maquinaria. Recuerda completar los costos de este pedido».
Mostrar qué conceptos faltan cuando exista seguimiento detallado. Para compras
históricas sin seguimiento, indicar que es necesario revisar sus costos, sin
inventar conceptos. No pedir una confirmación adicional por ese aviso.

Al guardar, registrar recepción y entradas en una sola transacción. Refrescar el
listado y deshabilitar la recepción repetida. Distinguir «Pendiente de recepción»
y «Recibido · fecha», independiente del indicador naranja/azul/verde de costos.
Usar «Pendiente de recepción», no afirmar «En tránsito» de compras históricas cuya
ubicación se desconoce. Añadir filtro Todos / Pendientes de recepción / Recibidos.
Mostrar cantidades recibidas por pedido; el total de inversión no cambia.

## Integridad y correcciones

Una sola recepción vigente por pedido, protegida por restricción UNIQUE. Un doble
clic o reintento devuelve la recepción existente si coincide su fecha; una fecha
diferente requiere corregir, no genera otra entrada. Un pedido anulado no se recibe.
Comprobar revisión de compra antes de recibir: si cambiaron sus líneas mientras
el diálogo estaba abierto, pedir recargar y no recibir cantidades desactualizadas.

Después de recibir, se pueden completar importes, tasas, cargos y estados con el
historial actual. No cambiar identidad ni cantidades de líneas recibidas ni borrar
líneas; permitir correcciones monetarias sobre los mismos identificadores.
No anular directamente una compra recibida: explicar que primero debe deshacerse
la recepción. Ofrecer «Deshacer recepción» con motivo obligatorio y confirmación.
En esta entrega todavía no hay salidas vinculadas; la siguiente deberá impedir
revertir entradas consumidas por ventas. La reversión conservará el registro y sus
entradas como anulados y permitirá recibir nuevamente sin duplicar entradas vigentes.

Las correcciones y recepción incrementarán la revisión de la compra y conservarán
la instantánea anterior. Un fallo de guardado conserva el diálogo y no deja
recepciones o entradas parciales. Las unidades recibidas de productos desactivados
se conservan: la recepción responde a las líneas históricas del pedido.

## Datos y migración

Migración 10 → 11 con respaldo SQLite y transacción, condicionando la migración
anterior a version < 10. Añadir purchase_receipts con id, purchase_id, received_on,
created_at, reversed_at, reversal_reason; índice único parcial por purchase_id
cuando reversed_at IS NULL. Añadir receipt_lines con receipt_id, purchase_line_id,
product_id, copias de código/nombre y cantidad entera positiva, única por recepción
más línea de compra. Las líneas de recepción referencian las líneas conservadas.

Los pedidos existentes comienzan sin recepción registrada y no generan stock.
La UI debe advertir al recibir compras antiguas que se confirmen las unidades
reales aún pertenecientes al negocio; las compras ya vendidas no deben usarse para
recrear existencias. La conciliación de existencias iniciales será parte del diseño
posterior de inventario/ventas, sin descontar ventas históricas automáticamente.

Las entradas se guardan por línea y cantidad, sin generar ahora una fila por cada
máquina. Las etiquetas y selección de unidades individuales se diseñarán después;
los códigos del catálogo no cambian. No congelar costos definitivos al recibir.

## Organización y pruebas

Servicio/repositorio de recepción independiente; reutilizar la conexión y manejo
de transacciones actuales. Integración en purchases_page y protección en
PurchasesRepository.update/cancel. Diálogo compacto con resumen, aviso y botones
siempre visibles; desplazamiento solo cuando el número de modelos lo requiera.

Pruebas: recepción completa y fecha, costos pendientes permitidos, pedido anulado,
reintento idempotente, revisión obsoleta, rollback, reversión con historial,
recepción posterior a reversión, corrección de costos permitida y cantidades
bloqueadas. Migración con pedidos existentes sin inventario inventado. Verificar
filtros combinados, selección de fila hija, inversión sin cambios, reapertura de
la base y errores sin pérdida de datos. Usar bases temporales y comprobar que el
formulario se ajuste a 1280×720 y 1440×900.
