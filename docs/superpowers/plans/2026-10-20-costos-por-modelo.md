# Gastos por modelo y seguimiento de pedidos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar máquinas y costos unitarios por pedido, distribuir gastos manualmente y destacar conceptos pendientes.

**Architecture:** Ampliar las líneas y cabeceras existentes con asignaciones COP y estados explícitos. Calcular los indicadores desde esos datos; conservar totales originales, revisiones e idempotencia. Usar un árbol de pedidos y líneas para la consulta.

**Tech Stack:** Python, PySide6, SQLite, Decimal, pytest; sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-20-costos-por-modelo-design.md`

## Global Constraints

- Códigos históricos y conversiones COP/USD sin cambios; ningún reparto automático entre modelos.
- Esquema 9 → 10 transaccional, respaldo previo, sin pruebas con datos personales.
- Importes enteros en centavos; tasas Decimal, HALF_UP, sin float monetario.
- Pedidos anulados conservados y excluidos de totales y alertas vigentes.
- No implementar inventario, pagos, indicadores de stock ni nuevos paquetes.
- Continuar en la rama actual del proyecto, como solicitó el usuario.
- Verde solo con conceptos resueltos y asignación completa; naranja y azul acompañados por texto.

## Review Focus

- Una categoría puede tener varios cargos parciales: añadir uno no implica completarla (tarea 1).
- Mismo producto en dos líneas a distintos precios: conservar asignaciones separadas (tareas 1 y 4).
- Reintento de una solicitud anterior a la migración: no duplicar ni rechazar por nuevos campos predeterminados (tarea 2).
- Eliminar una línea o reducir un cargo: actualizar pendientes y evitar exceso sin perder el formulario (tarea 3).
- Compras históricas sin seguimiento: no inventar nacionalización pendiente ni estados completos nuevos (tareas 2 y 4).

## Tarea 1: Reglas monetarias y estados

**Files:** modificar `src/mi_negocio/purchases.py`; crear `src/mi_negocio/purchase_allocation.py`, `tests/test_purchase_allocation.py`.

**Interfaces:** Añadir al final de PurchaseLineInput `shipping_allocated_cents`, `importation_allocated_cents`, `taxes_allocated_cents`, `other_allocated_cents`, enteros cero. Añadir al final de PurchaseDraft `cost_states: dict[str,str] | None = None`, claves CATEGORIES y valores pending/recorded/not_applicable. En purchase_allocation.py definir `allocation_summary(draft: PurchaseDraft) -> dict` con `registered`, `assigned`, `remaining` (dicts por categoría), `complete` (bool); `line_unit_costs(line: PurchaseLineInput) -> dict` con `purchase_cents`, `landed_cents` (Decimal unitarios sin redondear), `approximate` (bool); `purchase_progress(draft: PurchaseDraft, cancelled: bool = False) -> dict` con `state` (cancelled/costs_pending/allocation_pending/complete), `pending_categories` (lista), `legacy` (bool). Mantener cálculo de asignaciones independiente de validación para previsualizar excesos sin recursión.

- [ ] Escribir pruebas: ejemplo A/B de la especificación produce costos unitarios 106000000 y 218000000 centavos y total 430000000; asignar 12000000 y 18000000 al envío de 30000000 deja saldo cero. Probar saldo parcial, exceso por categoría, negativos, bool, límites y división de 5 centavos entre 3 unidades sin reconstruir el total desde el promedio. Dos líneas del mismo producto conservan resultados independientes.
- [ ] Ejecutar `.venv/bin/python -m pytest tests/test_purchase_allocation.py -q` y confirmar fallo por interfaces ausentes.
- [ ] Implementar interfaces y validar en validate_purchase: estados completos con claves exactas; recorded requiere fila incluso cero; not_applicable prohíbe cargos/asignaciones; pending permite cargos. Exigir coherencia de costs_complete con los estados si no son None. No cambiar totales del pedido al asignar.
- [ ] Añadir pruebas: pending con dos cargos sigue naranja; sin pendientes y saldo positivo azul; sin saldo verde; anulada gris; histórico incompleto devuelve legacy=True sin inventar categorías. Ejecutar pruebas nuevas y `tests/test_purchases.py`, todas PASS.
- [ ] Commit de reglas y pruebas.

## Tarea 2: Migración, guardado e historial

**Files:** modificar `src/mi_negocio/database.py`, `src/mi_negocio/purchases_repository.py`, `tests/test_purchases_repository.py` y pruebas existentes que comprueban versiones de esquema.

**Interfaces:** `migrate_purchase_allocations(connection)` crea las cuatro columnas INTEGER NOT NULL DEFAULT 0 con CHECK y cost_states_json TEXT nullable. Repository get devuelve los campos de línea y `cost_states` decodificado; preserva claves actuales. Create/update aceptan el PurchaseDraft ampliado. Añadir al final de PurchasesFilter `progress: str | None = None` con valores costs_pending/shipping_pending/nationalization_pending/allocation_pending/complete.

- [ ] Escribir pruebas que creen una base real esquema 9 con compra, cargo, revisión y payload antiguos; abrir con código nuevo debe producir versión 10, respaldo, mismos totales y estados, asignaciones cero y cost_states=None. Reabrir no migra otra vez. Una solicitud antigua idéntica devuelve el mismo id; asignación diferente con ese request_id se rechaza.
- [ ] Ejecutar pruebas y confirmar fallo antes de implementar.
- [ ] Condicionar migrate_purchases a version < 9 y nueva migración a version < 10. Persistir campos dentro de la transacción existente. Normalizar campos ausentes de payloads sin alterar request_payload guardado. Incluir asignaciones y estados en snapshots nuevos; tolerar ausencia en los antiguos.
- [ ] Aplicar filtros de progreso sobre los pedidos recuperados usando purchase_progress; nacionalización incluye importation o taxes pending explícitos. Mantener combinaciones de fechas/búsqueda/anulación y semántica histórica.
- [ ] Probar rollback, revisión obsoleta, anulación, conservación de línea inactiva, filtros combinados, cambios de categoría y tasas USD. Ejecutar `tests/test_purchases_repository.py` y pruebas de migración afectadas, todas PASS.
- [ ] Commit de persistencia y pruebas.

## Tarea 3: Edición de asignaciones y conceptos

**Files:** modificar `src/mi_negocio/ui/purchase_line_editor.py`, `src/mi_negocio/ui/purchase_dialog.py`; crear `src/mi_negocio/ui/purchase_progress_editor.py`; modificar `tests/test_purchases_ui.py`.

**Interfaces:** `PurchaseProgressEditor(QWidget)` con señal changed, `set_states(states: dict | None, legacy_complete: bool)`, `states() -> dict | None`, `is_complete() -> bool`. En nueva compra inicializar cuatro pending; en histórica presentar activación voluntaria del seguimiento. PurchaseLineDialog.result_line incluirá las cuatro asignaciones. PurchaseDialog.draft/load trasladarán campos y estados sin perder line_id.

- [ ] Escribir pruebas Qt: asignar 12000000 de envío a tres unidades conserva ese total; modificar cantidad no cambia asignación. Primer clic selecciona importe. Una compra histórica se abre y guarda sin inventar estados; activar seguimiento exige resolverlos explícitamente. Nueva compra no tiene selección global contradictoria.
- [ ] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_purchases_ui.py -q`, confirmar fallos nuevos.
- [ ] Añadir grupo de cuatro gastos al editor de línea, cantidad y explicación visibles. Distribuirlo en dos columnas en pantalla amplia; conservar botones al pie y Enter para Aplicar. Añadir resumen registrado/asignado/pendiente y estados en el formulario principal; no duplicar cargos ni totales.
- [ ] Mostrar costos unitarios COP y condición provisional; importes aproximados con ≈ y explicación. Mantener originales consultables en editor. Cambiar Referencia por Factura / pedido. Extender historial con asignaciones/estados y texto de ausencia histórica.
- [ ] Probar quitar línea aumenta saldo pendiente; reducir cargo muestra exceso y bloquea guardar sin perder datos; anulación deshabilita controles nuevos; cancelar no escribe. Ejecutar pruebas de interfaz y monetarias, todas PASS.
- [ ] Commit de edición y pruebas.

## Tarea 4: Listado agrupado y alertas

**Files:** modificar `src/mi_negocio/ui/purchases_page.py`, `tests/test_purchases_navigation.py`; crear `tests/test_purchase_grouped_list.py`.

**Interfaces:** sustituir tabla plana por QTreeWidget, cabeceras de pedido y líneas hijas expandidas inicialmente. Guardar purchase_id en Qt.UserRole en ambos niveles. Mantener open_new_purchase/open_detail/refresh_purchases y señales existentes; no depender de índices de self.rows para abrir.

- [ ] Escribir pruebas: dos pedidos y tres líneas muestran dos cabeceras; códigos con ceros intactos; doble clic o botón sobre hijo abre su compra; búsqueda de un modelo conserva todas las líneas del pedido; colapsar no altera sumas; no hay columna principal Referencia.
- [ ] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_purchase_grouped_list.py -q` y confirmar fallo.
- [ ] Mostrar cabecera y columnas de producto/cantidad/compra unitaria/costo unitario con gastos; usar texto multilínea y ajuste de alturas para nombres. Añadir filtro de progreso y contador de costos pendientes vigentes en esta vista. Colorear cabeceras naranja, azul, verde o gris con texto explícito y conceptos pendientes.
- [ ] Probar nacionalización filtra importation/taxes pending; histórico incierto no aparece allí pero sí en pendientes generales; anulados nunca incrementan contador ni total; dos líneas del mismo producto siguen separadas. Comprobar que selección/resaltado no oculta texto de estado.
- [ ] Ejecutar pruebas de listado y navegación, todas PASS; commit.

## Tarea 5: Validación integrada y documentación

**Files:** actualizar `docs/releases/compras-validacion.md`, README y captura sintética en `docs/capturas/`.

- [ ] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` y corregir regresiones sin debilitar pruebas. Todas deben pasar.
- [ ] Capturar con base temporal pedido mixto, asignación parcial, nacionalización pendiente, histórico y anulado. Inspeccionar 1440×900, 1280×720, 800×560 y escala 150%; datos completos accesibles y botones visibles, sin scroll horizontal innecesario ni recortes. Reusar el patrón de captura existente, sin la base personal.
- [ ] Ejecutar suite con `bash packaging/in_debian13.sh /usr/bin/env QT_QPA_PLATFORM=offscreen /opt/nimbo-build/bin/python -m pytest -q -o cache_dir=/tmp/pytest-cache` y `QT_QPA_PLATFORM=offscreen bash packaging/in_wine.sh -m pytest -q` si esos entornos siguen disponibles. Documentar límites si no lo están; Wine no valida Windows 11 real.
- [ ] Revisar diff contra la especificación, migración y coherencia monetaria; registrar resultados de pruebas y límites, advertencia de incompatibilidad de paquetes antiguos con esquema 10. No reconstruir paquetes en esta etapa.
- [ ] Ejecutar `git diff --check`, guardar documentación y correcciones en commit. Informar cambios visibles al reiniciar `./abrir.sh`, verificaciones y stock aún pendiente.
