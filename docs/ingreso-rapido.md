# Ingreso rápido de ventas y gastos

En Ventas y Gastos, el botón **Ingreso rápido** aparece junto al registro individual, con un tono azul claro. Abre una tabla donde cada fila corresponde a una operación independiente. Una fila de venta contiene un producto o servicio del catálogo.

- Escribe en las celdas y avanza con Tab. En productos, cuentas, categorías y formas de pago hay opciones para seleccionar.
- Pega desde Excel con Ctrl+V o **Pegar desde Excel**, sin encabezados y respetando el orden de las columnas. Se admiten hasta 500 filas por pegado. El pegado empieza en la celda seleccionada.
- Usa **Agregar fila**, **Duplicar fila** y **Quitar filas** para organizar la captura. Las filas ya registradas no se pueden modificar ni eliminar desde esta tabla; sus acciones habituales están en Movimientos.
- Los importes se introducen en COP, con hasta dos decimales. En ventas el precio es por unidad; la cantidad determina el total. Las fechas aceptan `dd/mm/aaaa` o `aaaa-mm-dd`.
- Cobrado/Pagado empieza en **No**. Para confirmar un cobro o pago, elige **Sí**, indica su fecha y la cuenta correspondiente. Una venta sin cobrar requiere cuenta de destino; un gasto sin pagar no tiene cuenta de pago.
- Cada venta permite indicar IVA (No aplica, Sumar IVA o IVA incluido), tarifa y retención. Las comisiones se calculan con la configuración vigente. También se respetan los requisitos configurados de identificación, factura y correo.

**Guardar filas** conserva los datos incompletos sin exigir que los completes en ese momento. Las filas incompletas quedan en rojo, con la explicación de lo que falta o debe corregirse. Se recuperan al volver a abrir Ingreso rápido y aparecen en un listado separado en Movimientos, visible para todos los períodos. Haz doble clic en un pendiente para retomarlo.

Guardar procesa solo las filas nuevas o editadas. **Reintentar pendientes** vuelve a evaluar explícitamente los pendientes cargados, por ejemplo después de corregir el catálogo o las existencias. Si una fila presenta un conflicto, las otras filas independientes pueden guardarse; la pantalla indica cuáles no se guardaron.

Las operaciones completas usan las mismas reglas y movimientos del registro individual. El guardado de cada fila es atómico: no puede quedar una venta creada sin vincularla a la fila. Los reintentos no duplican operaciones.

## Configuración e informes

En **Configuración → Ingreso rápido**, la opción de mostrar importes provisionales está desactivada inicialmente. Los pendientes no afectan dinero, existencias ni los totales de las operaciones registradas.

Al activar la opción, los informes de Ventas y Gastos incorporan un apartado separado de pendientes provisionales, sujeto a los filtros. Una venta requiere cantidad, precio e interpretación del IVA para estimar su importe. Los valores no calculables se muestran como `—`. Las filas sin fecha válida no se atribuyen al período ni se suman. El PDF contiene el mismo apartado que la vista previa.

Los pendientes y esta configuración se guardan en la base de datos y se incluyen en las copias de seguridad. La actualización al esquema 29 no modifica ventas, gastos ni existencias anteriores.
