# Dinero: cuentas, movimientos y flujo de caja

Estado: diseño aprobado en conversación; implementación y validación terminadas el 26/10/2026.
Control de tarjetas aprobado con opción para deshabilitarlo desde Configuración.
Intereses reales del extracto confirmados; sin estimaciones automáticas.

## Objetivo y navegación

Responder cuánto dinero hay, en qué cuentas y cómo cambió durante un período.
Activar Dinero en el menú lateral con tres pestañas: Resumen, Movimientos y Cuentas.
Mantener la estética azul, importes separados, acciones claras y formularios adaptados
al espacio disponible. El módulo no presenta el flujo de caja como utilidad.

## Enfoque recomendado

Consultar los cobros, gastos, envíos y cuotas desde sus registros de origen. Añadir
registros propios para saldos iniciales, transferencias, aportes/retiros y pagos de
compras. Una vista unificada genera los movimientos sin copiar cada gasto o venta.
Así las correcciones y anulaciones se reflejan sin sincronizar duplicados.

Alternativa: copiar todos los eventos a un libro de movimientos central. Facilita
una contabilidad más compleja, pero añade sincronización y migraciones de todos los
módulos. No se recomienda para el alcance actual.

## Reglas de cálculo propuestas

- Saldo inicial por cuenta y fecha, entendido al comienzo del día. Incluir los
  movimientos desde esa fecha; los anteriores siguen consultables pero no se
  vuelven a sumar al saldo. Una cuenta sin inicio configurado no muestra un saldo
  supuesto de cero.
- Separar saldo actual, saldo al cierre del período y flujo neto del filtro.
  Los filtros de búsqueda no redefinen el saldo real de una cuenta.
- Cobros de ventas según fecha de recepción y cuenta efectivas: entrada neta de
  comisión real. Mostrar bruto y comisión en el detalle, sin descontarla dos veces.
- Gastos manuales pagados según fecha de pago; pendientes excluidos de caja.
- Envíos pagados según fecha, cuenta y medio. Si falta cuenta, mostrar pendiente
  de clasificación, sin adjudicarlo a efectivo o banco por defecto.
- Cuotas de préstamos: salida total capital + intereses una sola vez. El desglose
  sigue disponible; el capital no se vuelve un gasto.
- Compras: los costos, la distribución por modelo y la recepción de inventario
  no prueban que se haya pagado. Añadir pagos explícitos por importe, fecha,
  cuenta y concepto (mercancía, transporte, nacionalización, impuestos u otros).
  Permitir varios pagos reales por pedido, sin inferirlos de costos históricos.
- Transferencias: dos efectos atómicos, salida de origen y entrada en destino;
  neto consolidado cero. No se cuentan como ventas ni como gastos.
- Aportes y retiros del propietario se distinguen de ingresos por ventas y gastos.
  El desembolso de un préstamo debe ser explícito: crear una deuda histórica no
  genera por sí solo una entrada de dinero.
- Anulaciones de registros erróneos excluyen movimientos manteniendo historial.
  Una devolución real de dinero requiere un movimiento explícito y no se simula
  borrando un cobro histórico.

## Pantallas

### Resumen
Mes actual por defecto y filtro de cuenta. Disponible configurado, entradas,
salidas y flujo neto del período; avisos de cuentas sin saldo inicial y pagos
sin asignar. Gráfico semanal/mensual con cero visible, verde para flujo positivo
y rojo para negativo; cifras y etiquetas además del color. Comparación con
período equivalente, indicando fechas y ausencia de base cuando corresponda.

### Movimientos
Fecha, concepto, origen, cuenta, entrada, salida y acceso al registro de origen.
Filtros de período, cuenta, tipo y búsqueda; totales del filtro. Transferencias
identificables y sin inflar entradas/salidas operativas consolidadas.
Correcciones de ventas/gastos se hacen en su formulario existente.

### Cuentas
Reutilizar cuentas de Configuración; no crear una lista paralela. Mostrar estado,
tipo, saldo inicial/fecha y saldo calculado. Historial para cambios de inicio y
explicación de que alterar la fecha cambia el punto de partida.

## Seguridad de datos y validación

Migración transaccional con copia previa; importes en centavos enteros y controles
de revisión/solicitud para evitar duplicados y escrituras obsoletas.
No transformar automáticamente cuentas bancarias en tarjetas por su nombre.
La clasificación de tarjetas antiguas requiere revisión explícita del usuario.
Pruebas con bases temporales: fechas de corte, comisiones, anulaciones, transferencias,
cuotas, cuentas desactivadas, costos sin pago y pagos sin cuenta.

## Orden de implementación

1. Definir tarjetas y completar este diseño.
2. Modelo de movimientos, saldos iniciales y repositorio con pruebas.
3. Pagos de compras y transferencias con validación e historial.
4. Pestañas Cuentas y Movimientos.
5. Resumen, gráficos y conexión con Inicio.
6. Verificación en Linux, Debian y entorno Windows; empaquetado en una entrega posterior.

PDF, rentabilidad por costo de inventario y contraseña de acceso siguen fuera
de esta entrega. La contraseña continúa pendiente para la etapa final.


## Tarjetas de crédito: ampliación del alcance

Requisitos confirmados: control opcional desde Configuración, interés editable
por tarjeta y pagos en cualquier fecha, parciales o completos, sin imponer cuotas
mensuales ni suponer que siempre hay intereses. Esto no habilita los abonos de
ventas, que siguen siendo un pendiente independiente.

Propuesta de funcionamiento:
- Desactivado inicialmente para negocios nuevos; se habilita cuando se necesita.
- Cada tarjeta conserva nombre, deuda inicial y fecha, tasa de referencia con
  unidad explícita (mensual o efectiva anual) e historial de cambios.
- Comprar con tarjeta aumenta deuda sin descontar efectivo/banco. Su cupo no se
  presenta como dinero disponible.
- Registrar intereses reales y otros cargos aumenta deuda y alimenta Gastos una
  sola vez. Puede haber períodos sin intereses.
- Pagar tarjeta exige cuenta de origen, fecha y desglose de capital, intereses y
  cargos. Disminuye cuenta y deuda, sin duplicar los gastos ya registrados.
- Cambiar la tasa no recalcula movimientos históricos.
- Deshabilitar no borra historial ni deudas. Si quedan saldos, advertir y mantener
  su visibilidad en el resumen; se ocultan accesos a nuevas operaciones hasta
  reactivar el control.
- No reclasificar cuentas existentes por su nombre ni inventar saldos históricos.
- Decisión confirmada: tasa editable como referencia e interés real del extracto
  ingresado manualmente, sin estimaciones automáticas.


## Conciliación y recordatorios de tarjetas

- Conciliación por período: «Pendiente de conciliación» en naranja, con texto
  «Saldo provisional; pueden faltar intereses o cargos», y «Conciliado» en verde.
- Permitir pagos antes de recibir el extracto. Pagar toda la deuda registrada no
  concilia automáticamente. Confirmar la conciliación requiere revisar importes
  reales, incluidos períodos con cero intereses. Mostrar pendientes en Dinero.
- En la configuración de cada tarjeta, junto a su tasa: **día de corte opcional,
  recomendado**. No es requisito para crear la tarjeta, guardar su configuración,
  registrar movimientos, pagar ni conciliar manualmente.
- Recordatorio previo al corte también opcional: desactivado o 1, 2 o 3 días antes.
  Sin día de corte no calcular avisos ni inventar una fecha; explicar que se puede
  agregar después para habilitarlos.
- Propuesta de presentación: avisos dentro de Inicio y Dinero al abrir Nimbo y
  al cambiar el día mientras esté abierto. No requiere ejecución en segundo plano.
- Aviso previo: revisar movimientos antes del corte. Si el extracto aún no llegó,
  mantener el período pendiente hasta poder confirmar los intereses/cargos reales.
- El día de corte no es la fecha límite de pago; no confundir ambos conceptos.
- Para días 29–31 inexistentes en un mes, usar su último día; considerar cruces de
  mes/año al calcular la anticipación. Cambiar configuración no altera conciliaciones
  históricas. Sin corte configurado, permitir identificar manualmente el período.
