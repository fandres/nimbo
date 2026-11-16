# Ventas, cobros completos y formas de pago

Fecha: 18 de octubre de 2026.
Estado: diseño aprobado por el usuario; implementado en la rama codex/catalogo. Ver docs/verificacion-ventas.md para alcance y evidencia.

## Objetivo y decisiones del usuario

Registrar las ventas habituales desde Inicio con pocos pasos, conservando el catálogo y su diseño horizontal. Separar una venta de la recepción del dinero: tarjeta o Addi pueden liquidarse días después. Cada venta tendrá un único cobro completo; anticipos y abonos parciales quedan para una versión posterior.

La prioridad actual es ventas antes de compras e inventario. No se descontarán existencias ni se mostrará utilidad sin conocer el costo de la mercancía. Se mantienen Python, PySide6, SQLite local y la rama de Git actual.

## Venta rápida

Nueva venta y Vender abrirán el mismo diálogo horizontal. Organización: productos a la izquierda; pago, envío y resumen a la derecha. Guardar y Cancelar siempre visibles; desplazamiento de respaldo para pantallas pequeñas.

- Fecha de hoy editable y referencia opcional de factura electrónica externa. La aplicación no emite facturas electrónicas.
- Buscar productos y servicios activos por código o nombre, manteniendo exactamente los códigos del catálogo.
- Una o varias líneas con cantidad entera positiva y precio unitario real editable, inicialmente tomado del precio recomendado.
- Guardar una copia del código, nombre y precio aplicado: editar el catálogo después no modifica la venta histórica.
- Tres opciones principales iniciales: Efectivo, Transferencia y Tarjeta. Ninguna se seleccionará silenciosamente al guardar.
- Interruptor «Otras formas de pago», inicialmente apagado, muestra solo las adicionales habilitadas. Si se apaga con una adicional seleccionada se limpia la selección y se solicita otra.
- Estado recibido o pendiente. Efectivo y transferencia proponen recibido; tarjeta y Addi proponen pendiente. La propuesta siempre es visible y editable.
- Cuenta de destino obligatoria, fecha de recepción obligatoria únicamente para ventas recibidas. No confirmar cobros automáticamente por transcurrir dos días.

## Formas de pago y cuentas

Configuración tendrá dos secciones acotadas: Formas de pago y Cuentas. Se podrán crear, renombrar y desactivar; no borrar registros referenciados. Las cuentas iniciales propuestas son Efectivo y Cuenta principal; no tendrán saldos iniciales inventados.

Cada forma de pago guarda nombre, porcentaje de comisión, cargo fijo COP, estado habilitado y ubicación principal/adicional. Las tarifas iniciales fueron proporcionadas por el usuario, no consultadas ni verificadas con proveedores:

| Forma | Porcentaje | Cargo fijo COP | Ubicación |
|---|---:|---:|---|
| Efectivo | 0 % | 0 | Principal |
| Transferencia | 0 % | 0 | Principal |
| Tarjeta (Bolt) | 3,59 % | 900 | Principal |
| Addi | 7,735 % | 0 | Adicional |

La etiqueta principal de tarjeta será «Tarjeta» y el detalle indicará Bolt. Los nombres y tarifas son editables para otros negocios. La selección de cuenta y de forma de pago son independientes.

Desactivar una forma o cuenta impide usarla en nuevas ventas, pero conserva su historial. Un cobro pendiente puede completarse con su configuración histórica, aunque la forma se haya desactivado; puede elegirse otra cuenta activa para recibirlo.

## Envío y cálculo

«Agregar envío» muestra costo del envío para el negocio y envío cobrado al cliente. Son valores distintos: envío gratuito significa cobro al cliente cero, aunque exista un costo. El usuario confirmó que el envío cobrado forma parte del mismo pago.

- Subtotal = suma de cantidad × precio unitario.
- Total pagado por el cliente = subtotal + envío cobrado.
- Comisión estimada = total pagado por el cliente × porcentaje / 100 + cargo fijo.
- Neto depositado = total pagado por el cliente − comisión real.
- Neto después de comisión y envío = total pagado por el cliente − comisión − costo del envío.

El último importe no se llamará utilidad ni saldo de cuenta. La comisión se aplica una sola vez al total de la venta, incluido el envío cobrado. El envío pagado se registra aparte, con su propia cuenta y fecha; no se resta otra vez del depósito recibido. Un costo de envío conocido pero todavía no pagado se mantiene pendiente.

Ejemplo de comprobación: mercancía de $1.000.000 y envío cobrado de $20.000 producen total de $1.020.000. Bolt estima $37.518 de comisión y depósito de $982.482. Si el envío cuesta $25.000, el neto después de ambos gastos es $957.482.

Importes persistidos como centavos enteros, cálculos con Decimal y redondeo HALF_UP a dos decimales al finalizar el cálculo de comisión. Porcentajes admiten al menos tres decimales. No añadir impuestos o cargos no indicados por el usuario. Valores no negativos; comisión real no puede superar el total cobrado. Un envío mayor que la venta sí puede dar neto negativo.

## Cobro y conservación histórica

La venta conserva el porcentaje y cargo fijo vigentes cuando se creó, además de la comisión estimada. Cambiar la configuración solo afecta ventas posteriores.

«Confirmar cobro» permite revisar fecha real, cuenta y comisión realmente descontada. El total comercial no cambia por una comisión diferente. Se registra el cobro completo junto con su comisión, en una transacción; pulsaciones repetidas no pueden duplicarlo. El mismo flujo se usa al guardar una venta ya recibida.

No habrá edición ni borrado destructivo de ventas cobradas en esta entrega. El detalle permite añadir o corregir la referencia de factura, confirmar un cobro pendiente y registrar el pago del envío una sola vez. Correcciones monetarias, anulaciones y devoluciones requieren una entrega posterior; la interfaz debe advertirlo antes de guardar y permitir revisar los importes.

## Ventas e Inicio

Ventas tendrá lista por fecha, referencia, total, forma, cuenta y estado; búsqueda por código/nombre/factura y filtros por rango de fechas, cuenta y recibido/pendiente. Un detalle presenta productos, envío, comisión estimada o real y cobro.

Inicio habilitará Nueva venta, Vender y Cobrar; actualizará ventas del mes (subtotal de productos y servicios, con envío cobrado separado), total comercial pendiente, número de pendientes y últimas ventas. Cobrar abre Ventas filtradas por pendientes.

Todavía no presentar un saldo disponible, rentabilidad ni flujo de caja completo: faltan saldos iniciales, compras y otros gastos. Mantener esos estados explicativos hasta que existan todos los movimientos. Las comisiones y pagos de envío quedarán estructurados para los futuros informes sin duplicarlos como gastos manuales.

## Implementación propuesta

Reglas monetarias y validación independientes de Qt. Repositorios específicos de ventas y configuración sobre la misma SQLite; migración transaccional desde esquema 2, conservando catálogo y listas. Tablas para cuentas, formas de pago, ventas, líneas, cobros únicos por venta y pagos de envío únicos por venta. Claves foráneas y restricciones de unicidad/tipos/valores también en la base.

Centralizar apertura y migraciones para que el repositorio de catálogo admita la nueva versión. Crear una copia de seguridad consistente mediante SQLite backup antes de migrar una base existente; abortar sin cambios si la copia o la migración falla. Semillas iniciales una sola vez, sin sobrescribir ajustes posteriores.

Venta y líneas se guardan atómicamente, incluyendo cobro y envío pagado cuando corresponda. Errores de almacenamiento dejan el diálogo abierto con sus datos y un mensaje recuperable. Deshabilitar Guardar durante la operación. Configuración, ventas y catálogo se conservan al navegar mediante QStackedWidget.

## Pruebas y aceptación

- Comisión Bolt y Addi, envío cobrado incluido, envío gratuito con costo, redondeo y validación de límites.
- Venta pendiente no genera cobro; confirmación posterior usa fecha real y admite comisión corregida.
- Cambio de tarifas o productos no altera históricos; desactivar no borra relaciones.
- No duplicar cobro, comisión ni pago de envío; errores revierten toda la operación.
- Migración desde base con catálogo existente; copia de seguridad y reapertura; todas las pruebas anteriores siguen pasando.
- Interruptor de adicionales, validación de selección, teclado y navegación entre módulos.
- Capturas con datos temporales, revisión a 1320 × 720 y 800 × 560; ninguna prueba modifica la base personal.

## Futuras versiones

Anticipos y abonos parciales, habilitables en Configuración cuando estén implementados, con varios cobros por venta y saldo pendiente. No añadir ahora un interruptor funcional ficticio. También quedan fuera crédito con cuotas/intereses, pagos mixtos, anulaciones/devoluciones, inventario físico, importación/exportación y PDF, y el resto del módulo financiero.
