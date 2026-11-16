# Implementación de rentabilidad FIFO

Diseño aprobado: ../specs/2026-11-06-rentabilidad-fifo-design.md.
Trabajo en codex/catalogo, en la carpeta actual por autorización del usuario.

## Tareas
1. Motor de lotes por tramos, reconstrucción desde movimientos y protección de reversión.
   Pruebas primero: lotes, centavos, devolución, apertura, ajustes, referencias históricas.
2. Informe de rentabilidad por venta y período, sin duplicar gastos ni restar retenciones.
   Pruebas primero: IVA, costos tardíos, faltantes, comisiones y gastos del período.
3. Integrar pestaña y PDF, documentar límites, revisión independiente, suite y smoke.

## Contratos
El motor no escribe datos. La protección de reversión usa la transacción existente.
Los importes son centavos enteros; los lotes se representan por rangos, no por unidad.
La búsqueda limita ventas; el resultado completo del período solo se presenta sin búsqueda.
Con búsqueda se presenta el margen de las ventas encontradas, sin imputar todos los gastos a ese subconjunto.

## Verificación
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv/bin/python -m mi_negocio --smoke-test
Revisar PDF y vista previa; revisión independiente de integridad y costos desconocidos.

## Resultado de ejecución
Implementado y verificado el 6 de noviembre de 2026: 466 pruebas de la suite,
smoke de la aplicación y git diff --check sin errores. Revisión independiente
sin hallazgos importantes o críticos (26 pruebas específicas). PDF de cuatro
páginas: páginas 1 y 2 inspeccionadas; encabezados repetidos, importes legibles.

Decisión de alcance: la búsqueda limita el margen de ventas; no atribuye todos
los gastos mensuales al subconjunto encontrado. La interfaz indica que debe
limpiarse para consultar el resultado completo. El riesgo evitado es presentar
una rentabilidad por cliente artificialmente reducida por gastos no atribuibles.
No se compilaron nuevos distribuibles en este cambio.
