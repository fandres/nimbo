# Ventas: Resumen y Movimientos

Diseño aprobado en la conversación mediante dos propuestas visuales. Implementación autorizada en la rama actual.

- Resumen inicial: total vendido bruto (incluye envío cobrado), operaciones, promedio por venta, por cobrar; evolución semanal/mensual; cinco productos más vendidos por unidades o importe; servicios separados; cobros brutos y desglose de comisión, costo de envío y envío cobrado.
- Movimientos: listado existente, con producto debajo del cliente, estados y acciones por fila. Confirmar cobro abre el detalle para revisar y guardar, nunca confirma sin intervención.
- Filtros comunes visibles: búsqueda, cobro, cuenta, fecha y adicionales. El mes actual sigue siendo predeterminado. Atajos: mes actual y últimos tres meses (desde el primero de hace dos meses hasta hoy).
- Comparación: mismo tramo del mes anterior en filtros mensuales, hasta hoy si está en curso; rangos personalizados contra el tramo inmediatamente anterior de igual duración. Fechas de ambos períodos siempre visibles. Sin rango, el resumen muestra todos los datos y no inventa una comparación. Base anterior cero: sin porcentaje.
- Totales excluyen anuladas aun cuando la tabla las muestra. Promedio redondeado al centavo; dinero calculado con enteros. Cobros corresponden al estado de esas ventas, no al flujo de caja por fecha de cobro.
- Comisiones reales si existe cobro, estimadas si está pendiente (advertencia explícita). Envíos y retención no se descuentan otra vez del total bruto. Sin utilidad por modelo en esta etapa.
- Clasificación de productos/servicios usa el tipo actual del catálogo; código y nombre vendidos se conservan desde la línea histórica. Ranking agrupado por identidad del producto, no por nombre.
- Elegido: gráficos QtPainter y controles Qt existentes, sin nuevas dependencias ni migraciones. Alternativa QtCharts descartada por añadir dependencias de distribución; imágenes estáticas no responden a los filtros.
- Se conserva la navegación de Inicio a pendientes y el atajo Nueva venta. Pantallas amplias muestran el resumen completo; pantallas pequeñas conservan acceso mediante adaptación y scroll solo si es necesario.
