# IVA total e informe de compras

> Implementación directa en la rama actual autorizada por el usuario. Diseño: docs/superpowers/specs/2026-11-17-iva-total-compras-design.md.

## Arquitectura
Guardar método y tasa en purchases (migración 26 con respaldo). El desglose por línea usa subtotal_cents y vat_cents existentes, con una asignación derivada en PurchaseLineInput que se recalcula desde el pedido y nunca cambia importes originales. Un único cálculo sobre total COP reparte centavos por acumulados. El informe consume snapshots del repositorio y no modifica compras.

## Pasos
- [x] Pruebas del dominio: 119000 -> base100000 IVA19000; centavos, USD, duplicados, activación/desactivación y persistencia. Observar fallo; implementar cálculo y migración.
- [x] UI: toggle y tasa en Qué compramos, tasa predeterminada editable en ajustes; bloqueo de modos simultáneos; resumen y reapertura. Probar señales y estados.
- [x] Informe Compras: período, proveedor/búsqueda y vigencia; mercancía, IVA, otros costos por concepto y PDF. Probar anuladas, históricos, caracteres HTML, períodos sin registros y exportación.
- [x] Suite completa, revisión visual y Git. No recompilar ni publicar binarios.

## Riesgos a verificar
Redondeo global versus por línea; preservación de moneda y tasa; historial anterior sin campos nuevos; FIFO y costos recibidos; costos manuales de IVA contados una vez; desactivación restaura importe original; tarifas inválidas no dejan resúmenes anteriores; fallos de migración revierten DDL.


## Resultado y verificación
- Migración 26 con respaldo previo; encabezado conserva método y tarifa. Las líneas conservan importes originales y guardan base e IVA en sus columnas existentes.
- Reparto del IVA con acumulados enteros: suma exacta, también con monedas mixtas. Desactivar recupera los importes ingresados. Se conservan snapshots históricos.
- Interruptor de IVA incluido en Qué compramos, tarifa configurable y exclusión de IVA por producto/cargo manual. Resumen base/IVA en un solo bloque para evitar desplazamiento vertical a 1280×720.
- Nueva pestaña Compras en Informes: filtros de fecha, búsqueda y vigencia; base, IVA y otros cargos por concepto; PDF del mismo snapshot. No se interpreta IVA dentro de Impuestos genéricos.
- TDD: pruebas nuevas fallaron por funciones/controles ausentes y pasaron tras implementar. Suite final: **492 passed** (`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`, 17,28 s).
- Verificados visualmente formulario 1280×720 (barras generales con máximo 0) y PDF A4 horizontal con datos ficticios. Archivos temporales en /tmp/nimbo-iva-total.png y /tmp/nimbo-informe-compras.pdf.
- Revisión independiente de dominio, FIFO, historial y reporte: sin bloqueos. No se modificó la base del usuario, no se recompilaron binarios ni se publicó.
- Ajuste de implementación: el desglose de IVA comparte la tarjeta de total de productos para evitar duplicar información y ocupar una fila adicional.
