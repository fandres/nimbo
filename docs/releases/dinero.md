# Dinero: cuentas y tarjetas

Implementación en desarrollo, posterior a 0.2.0-alpha.1. Disponible al ejecutar
el código actualizado; los AppImage y ejecutables publicados anteriormente no
incluyen estos cambios.

## Primer uso

1. En **Dinero → Cuentas**, configura el saldo inicial y la fecha de inicio de
   cada cuenta. El importe corresponde al comienzo de ese día; los movimientos
   anteriores no se suman otra vez. Un banco puede comenzar en sobregiro.
2. Registra transferencias, aportes, retiros, desembolsos de préstamos y pagos de
   compras desde **Registrar movimiento**. Un pago de compra identifica el pedido
   y el concepto pagado. Registrar una compra no significa haberla pagado.
3. Los cobros de ventas, envíos pagados, gastos pagados y cuotas de préstamos
   aparecen desde sus registros de origen. No se deben volver a registrar aquí.

El resumen separa **disponible hoy** de **entradas, salidas y flujo del período**.
El filtro temporal afecta estos últimos y su gráfico semanal o mensual. Las
transferencias entre cuentas no cuentan como entradas/salidas del negocio; al
filtrar una cuenta individual sí muestran su movimiento. El flujo no es utilidad.
Las cuentas sin saldo inicial se señalan y no se presumen con saldo cero.

Los movimientos propios pueden anularse con motivo; conservan historial. Para
corregir movimientos provenientes de ventas, gastos o préstamos, abre su origen.
Los saldos iniciales también conservan sus revisiones con fecha e importe.

## Tarjetas opcionales

El control está **desactivado por defecto**, en **Configuración → Dinero / tarjetas**.
Al habilitarlo, crea las tarjetas y configura su deuda inicial en Dinero → Cuentas.
Las tarjetas son cuentas de crédito separadas del efectivo y nunca aparecen como
cuentas de destino para cobrar ventas. Se pueden usar para gastos, pagos de compras
y envíos. Desactivar el control conserva deuda e historial.

- La tasa es una referencia editable; no genera intereses estimados.
- Registra intereses y otros cargos reales cuando llegue el extracto.
- Un pago puede ser parcial o total, en la fecha elegida, con capital, intereses
  y cargos separados. Los intereses deben haberse registrado antes como cargo.
  El pago reduce deuda y dinero disponible, sin crear otro gasto de intereses.
- Los cargos de tarjeta aparecen en Gastos como **Cargado a tarjeta**: el consumo
  está financiado. Su deuda y posterior pago se consultan en Dinero.
- Una tarjeta pagada no queda conciliada automáticamente. Confirma el período y
  el saldo contra el extracto. Los cambios retroactivos que alteren ese saldo
  vuelven provisional la conciliación.
- El día de corte y el aviso 1, 2 o 3 días antes son opcionales. Los avisos aparecen
  en Inicio/Dinero con el programa abierto; no son notificaciones del sistema ni
  tareas en segundo plano. Corte no significa fecha límite de pago.

Los envíos antiguos marcados como pagados a crédito sin una tarjeta identificada
se advierten como pagos sin cuenta asignada. No se convierten automáticamente las
cuentas existentes en tarjetas por su nombre.

## Validación

Pruebas de repositorios y formularios con bases temporales, migración transaccional
con respaldo, operaciones repetidas, pagos retroactivos, conciliación, formularios,
cuentas de crédito y flujo sin duplicación. Comprobación visual con datos sintéticos.
La validación automatizada de Windows se realiza mediante Python Windows en Wine;
no sustituye la prueba manual en Windows 11.

Resultados del 26/10/2026: 319 pruebas en Linux local, 319 en Debian 13 y
42 de Dinero/tarjetas/navegación con Python Windows mediante Wine, todas aprobadas.

## Exportar movimientos a PDF (28/10/2026)

En **Dinero → Movimientos → Exportar PDF**, el informe respeta las fechas,
la cuenta y la búsqueda activas. Se elige el destino en el diálogo de guardado.
El PDF incluye origen, cuenta, entradas/salidas y totales de los registros.

El bloque de flujo excluye tarjetas, movimientos sin cuenta y transferencias
internas cuando se consultan todas las cuentas. La tabla sí los conserva e
identifica, con totales separados. En filas de crédito, entrada es reducción
de deuda y salida aumento de deuda; no representan efectivo nuevo. Una comisión
de venta ya descontada no vuelve a restarse. Estos importes no son utilidad ni
saldo disponible. La exportación no altera registros ni adjunta documentos.

Qt genera el PDF sin dependencias nuevas. El guardado atómico conserva el informe
anterior si falla la escritura. Se pueden exportar períodos sin movimientos.
Disponible en el código posterior a la alfa 0.3; binarios anteriores sin cambios.
