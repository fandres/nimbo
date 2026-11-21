# IVA totalizado de compras

Estado: aprobado con cambio visual aportado por el usuario el 17 de noviembre. Conserva las opciones existentes por producto.

## Interfaz del producto comprado

Aplicar la segunda imagen aportada: producto a ancho completo; cantidad junto al costo; selector COP/USD y Total de la compra/Por unidad; conversión visible al usar USD; IVA con No aplica/Sumar IVA al costo/IVA ya incluido y tarifas 19 %, 5 % u Otra; tarjeta de base, IVA y total en COP. Conservar fecha de conversión y referencia opcional en COP. Los cambios de modo conservan el importe exacto existente. Los controles mantienen posición y los valores se actualizan al escribir.

## Comportamiento acordado

En «2 · Qué compramos», un interruptor «Separar IVA del total» permite indicar que los importes de mercancía ingresados ya incluyen el impuesto. Utiliza el porcentaje configurado (actualmente 19 %), visible junto al control. Se actualiza al agregar, editar o quitar productos. No se calcula sobre envíos, aranceles ni otros costos adicionales.

Ejemplo: con mercancía por $119.000 y tasa del 19 %, mostrar base de compra $100.000, IVA $19.000 y total con IVA $119.000. Separar IVA no aumenta el importe del pedido.

Se conserva el cálculo por producto, tanto «Sin IVA» (sumarlo a la base) como «IVA incluido» (separarlo del importe). Ambos métodos muestran y guardan base, IVA y total. No se permite combinar IVA totalizado con IVA por producto o con otro cargo de IVA en el mismo pedido. Si existe un método distinto, explicar el conflicto sin borrar importes ni cambiarlo silenciosamente.

## Enfoque

Se propone guardar explícitamente el método totalizado y su tasa, junto al desglose monetario, reutilizando las funciones de cálculo existentes. Un simple cargo manual calculado no permite distinguir con fiabilidad si debe recalcularse y no resuelve la separación de la base. Activar IVA por línea silenciosamente tampoco representa un cálculo único sobre el total y puede generar diferencias de redondeo.

El cálculo totalizado se realiza sobre la mercancía convertida a COP, redondeando una sola vez a centavos. Distribuir el desglose entre líneas conservando exactamente los totales, para mantener consistencia con costos de inventario. Conservar importes originales y tasas de cambio. Al desactivar el interruptor, recuperar el tratamiento sin IVA totalizado sin alterar los importes ingresados.

## Informes y persistencia

Persistir el método, tasa, base e IVA para que reapertura, historial e informes mantengan el mismo significado. No reinterpretar ni recalcular compras históricas automáticamente.

Incorporar a Informes el desglose de compras por período: base de mercancía, IVA y demás costos separados por concepto, con total del pedido y exportación PDF de los mismos datos filtrados. Excluir anuladas de los totales. Rotular los importes como registrados: el registro de una compra no demuestra su pago. Los cargos históricos de IVA identificables se muestran por separado sin volver a sumarlos al total; no inferir IVA dentro de cargos genéricos de impuestos.

## Verificación

Probar IVA total incluido, cálculo por producto conservado, exclusión entre métodos, edición y reapertura, cambio de cantidad e importe, redondeo de múltiples líneas, moneda USD y tasa de cambio, porcentaje configurado y compras históricas. Comprobar que base + IVA + otros costos coincide con el total tanto en pantalla como en PDF y que los conceptos no se duplican. Usar bases temporales y ejecutar la suite antes de registrar los cambios en Git.

No modificar los binarios publicados de la beta durante este desarrollo.
