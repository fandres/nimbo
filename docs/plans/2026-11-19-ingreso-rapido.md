# Ingreso rápido de ventas y gastos

Diseño aprobado: botón pastel junto al registro individual, tabla editable con una operación por fila, pegado desde hojas de cálculo, duplicar y quitar filas. Guardar permite datos incompletos: quedan pendientes en rojo, con motivo y posibilidad de completar. Las operaciones completas usan las mismas reglas contables del formulario individual. Configuración permite mostrar importes provisionales por separado en informes; por defecto se excluyen. Nunca afectan caja ni existencias hasta completar.

## Implementación y verificación
1. Persistencia de pendientes y preferencia (esquema 29); publicación atómica e idempotente usando repositorios existentes. Probar reinicio, reintentos, errores y ausencia de efectos de filas incompletas.
2. Tabla compartida con opciones de catálogo, teclado, pegado y recuperación; accesos en Ventas/Gastos y pendientes visibles en Movimientos.
3. Configuración e informes provisionales separados con filtros. Probar importes y transición a operación registrada sin doble conteo.
4. Pruebas de interfaz y regresión, revisión independiente y documentación. No generar una nueva beta en esta tarea.

## Registro
- Inicio: base 61d7b55, rama codex/catalogo, árbol limpio.
- Decisión: las filas vacías se ignoran. Fechas aceptan ISO o día/mes/año; importes usan formato monetario existente. Solo se publican operaciones válidas; los errores de validación se guardan como motivo del pendiente.
- Implementado: esquema 29, preferencia en base de datos, tabla compartida, pegado TSV, duplicado, guardado independiente, paneles de pendientes y apartado provisional en informes/PDF.
- Revisión independiente: cuatro hallazgos importantes, corregidos con pruebas que fallaron antes de la corrección: pendientes intactos no se reprocesan al guardar; los conflictos no interrumpen otras filas; una fila publicada con otro contenido rechaza ediciones concurrentes; fecha de pago incompatible con No conserva el pendiente; se mantiene validación completa de respaldos v28.
- Decisión: reintentar pendientes sin editar requiere una acción explícita. El listado de pendientes de Movimientos indica que comprende todos los períodos; los informes provisionales sí respetan sus filtros y separan las filas sin fecha válida.
- Verificación final (20/11/2026): 523 pruebas aprobadas con QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q. Incluye restauración de pendientes/preferencia, migración real desde v28, idempotencia, rollback, concurrencia, pegado y guardado de celda activa. Inspección visual offscreen realizada; encabezados compactados y motivo de pendiente visible al seleccionar la fila. No se generaron paquetes beta.
