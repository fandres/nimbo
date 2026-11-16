# Gastos, movimientos y préstamos

Diseño aprobado en conversación el 23 de octubre de 2026. Referencias: «Nuevo gasto (propuesta).png», «Gastos · Movimientos.png», «Gastos · Resumen.png».

## Enfoque elegido
El usuario eligió pestañas Resumen / Movimientos / Préstamos dentro de la ventana principal, en lugar de gráficos y tabla completa juntos. Resumen conserva gráficos y los cuatro últimos gastos, sin tarjetas redundantes. Movimientos tiene filtros completos, totales filtrados y acciones rápidas. Mismo tema y navegación de Nimbo; acceso desde Inicio para crear gasto.

## Reglas
- Importes enteros en centavos COP. Gastos manuales con concepto, categoría configurable, fecha, importe positivo, pagado/pendiente, cuenta obligatoria al pagar, fecha de pago, nota y referencia de comprobante opcionales; fecha estimada de pago opcional para pendientes.
- Categorías iniciales: Insumos y taller, Marketing, Software, Servicios, Salud y pensión, Intereses, Otros. Crear, renombrar y desactivar desde Configuración y acceso directo del formulario. Identidad estable; categorías utilizadas no se borran.
- Calendarios se abren al primer clic. Importes seleccionados al entrar. Formularios horizontales; desplazamiento solo como respaldo para pantallas pequeñas.
- Editar y anular conservando historial, sin borrado. Revisiones contra edición obsoleta y clave de solicitud contra doble guardado. Se anula con motivo.
- Comisiones y envíos de ventas son proyecciones consultadas, no registros duplicados. Se abren en la venta original. Fecha de imputación: fecha de venta. Comisión estimada mientras no hay cobro, real cuando lo hay. Envíos pagados a crédito se identifican: pago a transportadora no implica débito bancario. Cuenta desconocida se mantiene vacía. Ventas anuladas excluidas de totales.
- Resumen: selector de período y cuenta, barras por categoría con pesos y porcentajes, comparación equivalente y últimos cuatro gastos vigentes. Mes actual hasta hoy por defecto; meses anteriores completos. Mes completo anterior contra mes completo; mes parcial contra mismos días del mes anterior (limitados al último día). Rango personalizado contra intervalo inmediatamente anterior de igual duración. Mostrar fechas exactas y «Sin base de comparación» si base cero. Variación neutral, no juicio de rentabilidad.
- Movimientos: búsqueda, categoría, estado, cuenta y período; anulados ocultos por defecto y accesibles. Totales siempre sobre vigentes filtrados. Resumen comparte período/cuenta, pero no filtros de detalle ocultos. Al ir a «Ver todos» limpiar filtros exclusivos de movimientos.
- Préstamos: entidad/nombre, fecha de saldo inicial, saldo de capital inicial; registrar pagos efectivamente realizados con fecha, cuenta, capital e intereses desglosados. Saldo = inicial menos capital de pagos vigentes; impedir sobrepago, fechas anteriores al saldo inicial y duplicación. Historial y anulación con motivo. Intereses proyectados una sola vez en Gastos; capital fuera del total y gráficos. No cálculo de amortización ni tasas automáticas ni desembolsos en caja en esta etapa.
- No crear aún saldos de cuentas o flujo de caja: pagos y fechas quedan listos para el módulo Dinero, evitando prometer saldos inexistentes.

## Decisiones de implementación
SQLite esquema 13, respaldo antes de migrar y transacción total; nuevas tablas aisladas para categorías, gastos, revisiones, préstamos y pagos. Sin dependencia gráfica nueva: QtPainter para barras de comparación y widgets de progreso para categorías. Referencia de comprobante como texto (número/documento); archivos adjuntos fuera de esta entrega. Préstamos permiten corregir nombre y saldo inicial solo antes de registrar pagos; pagos erróneos se anulan y se vuelven a registrar, con historial. Datos de prueba siempre temporales. Paquetes alfa anteriores no se recompilan en esta tarea.
