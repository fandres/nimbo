# Estados de costos sin preselección

Solicitud explícita: los conceptos nuevos no comienzan Pendientes; aplicar un importe los marca Registrados automáticamente.

## Decisiones
- Guardar `unselected` en el JSON de seguimiento existente; mostrar «Seleccionar…» con fondo neutro.
- Solo Registrado y No aplica dan el concepto por revisado. Un estado vacío no certifica que los costos están completos, ni se confunde con Pendiente explícito en los filtros por concepto.
- Agregar o editar un cargo marca su concepto Registrado. Si se quita el último cargo de un concepto Registrado, volver a Sin seleccionar. Con varios cargos, conservar Registrado.
- Cargar pedidos existentes conserva sus decisiones, incluidos Pendientes con importes; no sobrescribir historial al abrir.
- Nuevos conceptos agregados desde Configuración empiezan Sin seleccionar.
- Mostrar Sin seleccionar en el detalle, listado, recepción e historial. No modificar importes ni cuentas.

## Pasos y evidencia
- [x] Pruebas iniciales fallan por defecto Pendiente y ausencia de registro automático.
- [x] Modelo y controles admiten Sin seleccionar; validación de completitud explícita.
- [x] Actualización al aplicar cargo, cambio de concepto y eliminación del último cargo.
- [x] Verificar suite completa, persistencia, avisos de recepción y conceptos nuevos.
- [x] Registrar commit del cambio.

Verificación: suite completa 479 pruebas correctas; diff revisado sin errores de formato.
