# Comisiones configurables y consulta por plataforma

Implementación directa autorizada por el usuario. Python/PySide6/SQLite, sin dependencias nuevas.

Diseño: tarifa base y escalones opcionales «Desde COP» (límite inclusivo, aplica al total completo incluido envío; debajo del primer escalón usa base). Nueva venta aplica automáticamente y muestra tarifa, con Ajustar comisión apagado para habilitar una excepción local. Conserva comisión real del cobro y snapshots históricos. Gastos consulta las ventas, sin duplicar asientos: plataforma por ID estable, nombre histórico visible, fecha del gasto o del pago explícita; pendientes sin fecha de pago se excluyen de esta última.

- [x] Tests de límites, persistencia, edición local, concurrencia e historial.
- [x] Migración 20, tarifas, configuración y Nueva venta.
- [x] Filtro plataforma y fecha de pago en Gastos; totales y pruebas de importes reales/estimados/anulados.
- [x] Verificar suite y revisar cambios; commit local.

Riesgos: redondeo en centavos, comisión mayor al total, reemplazo manual involuntario, filtrado de fechas mezcladas, cambio de nombre/plataforma deshabilitada. Se probarán explícitamente.

Verificación: 373 pruebas Linux; 22 seleccionadas Debian 13; 22 seleccionadas Windows vía Wine. Capturas Qt revisadas con 1280×820. Revisión independiente sin defectos importantes. Se mantiene la edición de comisión real del cobro separada del ajuste de tarifa, para registrar liquidaciones reales.
