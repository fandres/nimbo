# Ventas: Resumen y Movimientos

La sección Ventas abre ahora en Resumen. Movimientos conserva la consulta y gestión de registros. Ambas pestañas comparten búsqueda, estado de cobro, cuenta, fechas, vigencia, retención e importes mínimos/máximos.

## Resumen

- Total bruto del filtro, cantidad de operaciones, valor promedio y pendiente de cobro. El total incluye lo cobrado por envío.
- Evolución por mes o semana, con importes y fechas exactas al pasar el cursor. Rangos extensos se agrupan por mes (más de 90 días) o año (más de 730 días) para mantener la legibilidad.
- Cinco productos o servicios más vendidos, alternando unidades e importe. Se agrupan por producto, no por nombre. El tipo corresponde a la clasificación actual del catálogo; nombres y precios proceden de las líneas vendidas.
- Cobros recibidos y pendientes de esas ventas, en bruto. No equivale a entradas de caja por fecha de recepción.
- Comisión real cuando se confirmó el cobro; estimada en ventas pendientes, con aviso. Costos de envío y envío cobrado separados. No se calcula utilidad ni se descuenta otra vez la retención informativa.
- Las anuladas pueden consultarse en Movimientos pero no se suman a indicadores ni gráficos.

## Fechas y comparación

El mes actual sigue siendo predeterminado. En Fecha de venta están los accesos Este mes y Últimos 3 meses (primer día de hace dos meses hasta hoy).

El mes en curso compara solo días transcurridos con el mismo tramo del mes anterior. Un mes completo compara con el mes anterior completo, incluyendo febrero. Un rango personalizado compara con el tramo inmediatamente anterior de igual duración. Las fechas se muestran sobre los filtros. Las barras anteriores se alinean por tramos transcurridos, no por fronteras de meses diferentes. Sin rango definido no se ofrece un porcentaje; con base anterior cero se indica que no hay base para comparar.

## Movimientos

Cliente y producto en la misma celda, estado con color y acciones en cada fila. Confirmar cobro abre el detalle con la opción seleccionada; solo se registra al guardar. Inicio → cobros pendientes abre Movimientos con los pendientes sin restringirlos al mes.

## Alcance técnico

Sin nuevas dependencias ni migraciones. Gráficos QtPainter. Capturas verificadas con una base temporal; no contienen datos reales. Resumen completo sin desplazamiento a 1440×900 y 1320×720 con los datos de prueba. Pantallas pequeñas conservan acceso por desplazamiento.

Las distribuciones AppImage y Windows anteriores no cambian; esta actualización se ejecuta desde el código fuente hasta el siguiente empaquetado.
