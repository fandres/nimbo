# Conceptos configurables de costos de compras

Solicitud: administrar desde Configuración los conceptos del punto 3 de compras:
agregar, editar, quitar y eliminar. Los cuatro conceptos existentes dejan de estar
fijos en la interfaz. En esta versión se mantienen como opciones iniciales; la
solicitud de comenzar una lista limpia para cada emprendedor queda en futuras-versiones.md.

## Uso

Configuración → Costos de compras muestra nombre, grupo del resumen y disponibilidad.
Permite crear, renombrar, desactivar/reactivar y quitar. Los conceptos personalizados
sin uso se eliminan; los usados o predefinidos se desactivan. El grupo es Envío e
importación o Impuestos y otros, para mantener la lectura del resumen existente.

Cada compra nueva toma una copia de los conceptos habilitados. Los pedidos guardados
conservan sus nombres y grupos aunque después se modifique Configuración. La lista
puede quedar vacía. No modifica ventas, gastos operativos ni pagos realizados.

## Datos y garantías

Migración 16 transaccional con respaldo: catálogo purchase_concepts, copia de
conceptos en purchases y asignaciones de conceptos personalizados en purchase_lines.
Se elimina la restricción antigua de cuatro claves en purchase_costs preservando
IDs e importes. Las cuatro columnas históricas de asignación se conservan.

Los nuevos conceptos tienen seguimiento pendiente/registrado/no aplica, conversión
a COP y distribución manual entre modelos. La distribución no crea otro cargo.
Los costos por unidad y las advertencias del listado/recepción usan los conceptos
del propio pedido. El historial mantiene nombres e importes de cada revisión.

## Verificación

Pruebas de configuración, duplicados, conceptos personalizados con importes,
distribución, guardar/reabrir, renombrar/desactivar sin afectar el pasado, lista
vacía y migración desde 15 con rollback. Revisión independiente y suites de Qt.

Resultado: 332 pruebas completas en Linux; 38 específicas en Debian 13 y 38 con
Python Windows mediante Wine. Revisión independiente: se corrigieron conservación
del índice de costos y normalización de solicitudes antiguas para reintentos.
Captura sintética de Configuración revisada a 1000 × 720.
