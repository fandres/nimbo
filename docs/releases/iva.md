# IVA opcional en compras y ventas

- Configuración → IVA permite activar el IVA inicialmente para compras o ventas por separado. Ambas opciones comienzan desactivadas.
- La tarifa inicial es 19 % y puede cambiarse en cada operación.
- «Sin IVA»: el importe ingresado es la base y el impuesto se suma.
- «IVA incluido»: el importe ingresado es el total y se extraen base e impuesto. Por ejemplo, $119.000 al 19 % contiene $100.000 de base y $19.000 de IVA.

## Compras
El IVA se configura al agregar cada producto. El desglose aparece antes de aplicar la línea; el IVA calculado suma a «Impuestos y otros» y al costo por unidad con gastos, sin requerir distribución manual.
Los costos adicionales de importación siguen disponibles. Si se activa IVA en productos y se registra otro cargo identificado explícitamente como IVA, se pide revisarlo para no duplicarlo. Los conceptos genéricos como «Impuestos» no se reinterpretan: conviene separar IVA y arancel.
Una compra puede contener líneas con IVA y sin IVA.

## Ventas
El IVA se calcula sobre los productos y servicios; el envío cobrado se agrega por separado. Las comisiones se calculan sobre el total final al cliente.
El resumen y el detalle muestran base e IVA. «Más filtros» permite consultar ventas con o sin IVA; el informe PDF incluye el IVA de las ventas vigentes filtradas.
La retención informativa conserva el cálculo existente sobre el total.

## Conservación de datos
La migración 21 conserva las operaciones anteriores con IVA desactivado y sus importes originales. Cada operación nueva guarda su tarifa, modo e importe de IVA; cambiar la configuración no recalcula operaciones anteriores.
