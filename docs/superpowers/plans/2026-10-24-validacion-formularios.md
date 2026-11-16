# Validación visible en formularios

Solicitud: al intentar guardar información incompleta, explicar qué falta, marcar los controles en rojo y enfocar el primero, incluso dentro de una sección plegada. No cambiar los campos opcionales ni las reglas de persistencia.

Implementación:
- Una utilidad compartida marca todos los campos detectados, enfoca el primero, selecciona el texto y lo desplaza a la vista. El marcado se retira al editar; se vuelve a comprobar al guardar.
- Validación específica en gastos y pagos, préstamos, ventas y cobros, compras y recepción, productos/costos de compra, catálogo, cuentas, comisiones, transportadoras, categorías y ajustes de inventario.
- Los motivos obligatorios de anulación o reversión se completan en un diálogo que permanece abierto si están vacíos. El motivo de anulación de ventas conserva su carácter opcional.
- Los errores operativos (base de datos, concurrencia, registros deshabilitados desde otra ventana) mantienen sus mensajes y no se atribuyen a un campo arbitrario.

Verificación: pruebas de foco, marcado simultáneo y limpieza al editar; importe cero en Nuevo gasto; cuenta opcional al dejar pendiente; distintos formularios vacíos; conversión USD/COP; motivos obligatorios; regresión completa.
