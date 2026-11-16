# Gestión de ventas guardadas

Autorizado: configurar anulación, edición completa de líneas y eliminación definitiva.
Anular/editar activos inicialmente; eliminar desactivado. Advertencia al habilitar
el borrado y confirmación por venta. Configuración persistente por base de datos.

1. Persistir permisos y secuencia de identificadores, conservar historial de ediciones.
2. Editar líneas atómicamente con stock, IVA y comisión histórica; no recalcular una
   comisión real ya conciliada. Conservar la política histórica de retención.
3. Eliminar venta/cobros/pagos y vínculos de adjuntos, revertir stock una sola vez.
   Conservar las copias físicas de documentos y movimientos de inventario como respaldo.
4. Interfaz de configuración y edición con un único Guardar cambios; historial consultable.
5. Probar permisos, rollback, existencias, eliminación, no reutilización de IDs y UI.

Decisión: al modificar una venta anterior al inicio del inventario no alterar la
apertura física confirmada; la interfaz informará de ello.

## Registro de ejecución
- Configuración por base de datos: editar/anular habilitados; eliminar deshabilitado.
- Pruebas iniciales fallaron por falta de las APIs; pasan con la implementación.
- Migración 24: permisos, secuencia que evita reutilizar IDs, revisiones y marca
  de control de stock. Se conserva el respaldo automático previo a migración.
- Edición provisional de líneas; Guardar cambios confirma todo en una transacción.
- Revisión independiente: corregido el cálculo de stock al reclasificar un servicio
  mediante movimientos reales (prueba falló y luego pasó).
- Revisión independiente: corregida validación de comisión contra total nuevo
  al editar y cobrar simultáneamente (prueba falló y luego pasó).
- Verificación visual a 1230×760: detalle sin desplazamiento vertical, acciones visibles.
- Las ventas históricas sin movimientos identificables se mantienen fuera del
  control de stock; se informa en el editor y no se modifica la apertura física.
- Los documentos físicos y el registro de movimientos de inventario se conservan;
  se eliminan la venta, sus pagos, revisiones y vínculos a documentos.
