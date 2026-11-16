# Costos adicionales de pedidos con un solo modelo

Implementado el 6 de noviembre de 2026.

- Si todas las líneas corresponden al mismo producto, cada cargo adicional se
  reparte automáticamente por cantidad de unidades, también en líneas repetidas.
- Se convierte cada cargo a COP antes del reparto. La división acumulada en
  centavos conserva el total aun cuando no sea divisible exactamente.
- No se redistribuye la mercancía ni el IVA ya registrado en cada línea.
- El formulario actualiza el costo por unidad al cambiar/agregar/quitar cargos;
  muestra «Reparto automático · mismo modelo» en lugar del reparto manual.
- Un pedido mixto conserva la asignación manual. Al pasar desde reparto automático
  a mixto en el formulario, se limpian las asignaciones automáticas y quedan
  pendientes de distribución, sin tocar los importes de los cargos.
- Al guardar, el repositorio aplica la misma regla. Las correcciones conservan
  el estado anterior en el historial. Los pedidos existentes no se reescriben
  al abrirlos: es necesario guardar para persistir la distribución.

Verificación: pruebas de repetición de modelos, centavos, moneda USD, conceptos
personalizados, retiro/corrección de costos, historial, vista previa y transición
a varios modelos. Revisión independiente del algoritmo sin defectos materiales.

Este cambio prepara los costos para el motor FIFO. El enlace FIFO entre lotes y
ventas y el informe de rentabilidad todavía no están implementados por este cambio;
su diseño está en docs/superpowers/specs/2026-11-06-rentabilidad-fifo-design.md.
