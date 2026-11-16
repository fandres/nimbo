# Central de Informes

Estado: aprobado por el usuario el 6 de noviembre de 2026.

## Objetivo
Habilitar Informes en el menú lateral para consultar y exportar ventas, gastos y movimientos de dinero desde un mismo lugar. El usuario eligió esta central antes de abordar rentabilidad por máquina.

## Enfoque
Se eligió reunir los informes existentes y completar Gastos. La alternativa de comenzar por rentabilidad requiere vincular costos de inventario con ventas y queda fuera de esta entrega. Dentro de la central, la propuesta técnica es una pantalla con tres pestañas y vista previa, en lugar de accesos que obliguen a navegar a otro módulo.

## Interfaz
- Encabezado Informes con explicación breve y botón principal Exportar PDF.
- Pestañas Ventas, Gastos y Dinero; Ventas inicialmente seleccionada.
- Bloque de filtros separado de la vista previa. Mes actual por defecto, selector rápido de mes/año y rango personalizado con calendario al hacer clic. Fechas desde/hasta siempre visibles, sin desplazar otros filtros.
- Cuenta y búsqueda comunes en intención, con opciones adecuadas al informe. Ventas: estado del cobro, vigencia y retención. Gastos: categoría, estado, vigencia y plataforma de comisión y fecha del gasto/fecha de pago. Dinero: cuenta y búsqueda.
- Cada pestaña conserva sus filtros durante la sesión, independientes de los filtros de los otros módulos.
- Vista previa de solo lectura con filtros aplicados, totales y detalle. Texto largo ajustado; desplazamiento dentro de la vista previa para documentos extensos, no en los controles principales.
- Exportación del mismo contenido que se está previsualizando, incluyendo períodos sin registros. Indicador de fecha de generación; actualizar al entrar y al cambiar filtros, y botón Actualizar para refrescar explícitamente.

## Datos y significado
Reutilizar SalesRepository.list_sales, ExpensesRepository.list_movements y MoneyRepository.movements. No introducir consultas con una segunda definición de los totales.

Ventas reutiliza el informe actual: importes brutos, IVA incluido identificado, cobros y pendientes brutos, retenciones, anuladas fuera de totales. Mantener aclaración del tratamiento histórico de retenciones.

Gastos añade informe con total vigente, pagado y pendiente, resumen por categoría y detalle por fecha, concepto, categoría, cuenta, plataforma/origen, estado y valor. Incluir comisiones y envíos automáticos ya presentes en el repositorio sin duplicarlos. Capital de préstamos no es gasto; los intereses siguen el comportamiento existente. Los anulados visibles no suman. Por defecto el período utiliza fecha del gasto; permitir fecha de pago y rotular ambos modos. Al elegir fecha de pago, los gastos sin pago quedan fuera. Conservar estimated y detail del repositorio: aviso «Incluye comisiones estimadas», estado «Cargado a tarjeta» y total «Pagado / cargado a tarjeta». No confundir estimaciones con importes definitivos ni deuda con efectivo pagado.

Dinero reutiliza su informe existente: cobros/pagos por fecha de movimiento, distinción de crédito, retenciones y transferencias internas. No presentar flujo como utilidad o saldo disponible.

## Implementación y límites
Reutilizar QTextDocument/QPdfWriter y guardado atómico existente. Vista previa con QTextBrowser sin enlaces externos ni recursos remotos, datos escapados. No nuevas dependencias ni migraciones. Operación de lectura; no modificar ventas, cuentas ni inventario. Fallos de consulta limpian la vista previa y deshabilitan exportación para evitar documentos desactualizados.

Fuera de alcance: utilidad neta, costo de ventas, impuestos calculados nuevos, Excel, impresión directa, compras e inventario en Informes y reconstrucción de los gráficos existentes.

## Verificación
Pruebas de filtros y totales, exclusión de anulados, fuentes automáticas sin duplicados, retención, cuentas, períodos vacíos, rangos inválidos y cambios entre pestañas. Exportar PDF con texto largo y varias páginas y verificar su contenido/layout. Comprobar navegación, tamaño habitual y apertura sin datos con bases temporales. Ejecutar suite y registrar commit. No recompilar binarios en esta entrega.

## Revisión de factibilidad
Revisión independiente completada: sin bloqueos técnicos. Incorporada la distinción de comisiones estimadas y cargos a tarjeta en Gastos.
