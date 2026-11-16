# Recepción completa de compras — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recibir un pedido completo una sola vez, con trazabilidad y advertencias de costos no bloqueantes.

**Architecture:** Añadir un repositorio de recepción sobre la conexión SQLite existente, con entradas por línea. Integrarlo en Compras y proteger modificaciones posteriores. No conectar aún salidas de ventas ni presentar entradas acumuladas como stock actual.

**Tech Stack:** Python, PySide6, SQLite, pytest; sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-21-recepcion-compras-design.md` (aprobado por el usuario).

## Global Constraints

- Recepción completa, nunca parcial; costos pendientes permitidos con advertencia.
- Esquema 10 → 11, respaldo previo y migración transaccional.
- No generar entradas para compras antiguas ni descontar ventas históricas automáticamente.
- Códigos históricos preservados; entradas agregadas por línea, no etiquetas individuales.
- Continuar en la rama actual, ejecución directa aprobada previamente.
- Fecha entre compra y hoy; ningún movimiento de caja ni pago confirmado al recibir.

## Review Focus

- Doble confirmación desde dos diálogos: una sola recepción vigente (tarea 1).
- Cambio de cantidades mientras el diálogo está abierto: revisión obsoleta rechazada (tarea 1).
- Reordenar líneas recibidas sin cambiar identidad/cantidad: permitido (tarea 2).
- Costos incompletos en compra histórica: aviso sin inventar conceptos (tarea 3).
- Revertir y recibir de nuevo: conservar historial, no acumular entradas vigentes duplicadas (tarea 1).

## Tarea 1: Datos y operaciones de recepción

**Files:** crear `src/mi_negocio/purchase_receipts_repository.py`, `tests/test_purchase_receipts_repository.py`; modificar `src/mi_negocio/database.py` y pruebas de esquema.

**Interfaces:** `PurchaseReceiptsRepository(connection)`; `receive(purchase_id: int, received_on: date, *, expected_revision: int) -> dict`; `reverse(receipt_id: int, reason: str, *, expected_revision: int) -> dict`; `current(purchase_id: int) -> dict | None`; `history(purchase_id: int) -> list[dict]`. Dict de recepción incluye cabecera y `lines` con cantidades/código/nombre/product_id/purchase_line_id.

- [ ] Escribir pruebas RED para compra de dos modelos (2 y 1 unidades): receive genera tres unidades en dos líneas; misma solicitud y fecha devuelve mismo id; distinta fecha rechazada. Costos pendientes no impiden recibir. Anulada, fecha futura/anterior y revisión obsoleta producen error sin entradas.
- [ ] Ejecutar `.venv/bin/python -m pytest tests/test_purchase_receipts_repository.py -q`; confirmar fallos por funcionalidad ausente.
- [ ] Crear tablas y único parcial según spec; condicionar migración de asignaciones a version < 10. Todas las migraciones bajo transacción y respaldo existentes. Normalizar get/history para fechas almacenadas ISO.
- [ ] Implementar receive/reverse en transacción, snapshot anterior y aumento de revisión de compra. Primero detectar recepción vigente para reintento idéntico; después verificar revisión para nuevas entradas. Una reversión requiere motivo, compra vigente y revisión actual. No borrar registros: reversed_at invalida sus entradas.
- [ ] Probar recepción tras reversión, rollback con trigger que falle al insertar segunda línea, dos conexiones intentando recibir y reapertura. Migración desde esquema 10 deja cero recepciones y conserva compras, asignaciones, revisiones y costos.
- [ ] Ejecutar pruebas nuevas y de base de datos, todas PASS; commit.

## Tarea 2: Proteger compras recibidas y exponer estado

**Files:** modificar `src/mi_negocio/purchases_repository.py`, `src/mi_negocio/purchases.py`, `tests/test_purchases_repository.py`.

**Interfaces:** get/list incluyen `receipt` vigente o None y `received_quantity`. Añadir al final de PurchasesFilter `received: bool | None = None`.

- [ ] Escribir pruebas RED: update de líneas recibidas rechaza cambios de producto/cantidad, nuevas líneas y líneas eliminadas, pero acepta reordenar líneas con los mismos ids y corregir importes/gastos. Cancel rechaza compra recibida; tras reverse permite cancel.
- [ ] Ejecutar las pruebas y confirmar fallos antes de implementar.
- [ ] Verificar identidad/cantidad contra la recepción vigente antes de escribir; conservar transacciones y control de revisión. No introducir importaciones circulares: consultas auxiliares de recibos independientes del repositorio de compras.
- [ ] Añadir filtro recibido mediante EXISTS y cantidad derivada solo de entradas de recepción vigente. Probar filtros combinados, pedido anulado tras reversión y total de inversión sin cambios.
- [ ] Ejecutar pruebas de compras/recepción, todas PASS; commit.

## Tarea 3: Confirmación y consulta en interfaz

**Files:** crear `src/mi_negocio/ui/purchase_receipt_dialog.py`, `tests/test_purchase_receipts_ui.py`; modificar `src/mi_negocio/ui/purchases_page.py`, `src/mi_negocio/ui/purchase_dialog.py`.

**Interfaces:** `PurchaseReceiptDialog(purchases, receipts, purchase_id, parent=None)` con señal `saved(int)`; fecha, resumen de líneas, aviso y botón de confirmación. Integración por purchase_id, incluso selección de fila hija.

- [ ] Escribir pruebas RED para recibir una compra con costos pendientes: aviso visible, confirmación habilitada y fecha hoy. Cancelar no escribe. Seleccionar hijo abre pedido correcto; doble guardado no duplica. Probar error de revisión sin cierre ni pérdida de fecha.
- [ ] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_purchase_receipts_ui.py -q`; confirmar fallo inicial.
- [ ] Añadir botón «Recibir maquinaria y confirmar stock», filtro de recepción y fecha recibida independiente de los colores de costos. El diálogo deja claro que registra entradas y que ventas aún no las descuentan. Advertir antes de confirmar compras antiguas que no se reingresen máquinas ya vendidas.
- [ ] Para recibidas, permitir completar costos pero bloquear cambios estructurales; ofrecer «Deshacer recepción» con motivo obligatorio y confirmación. Mostrar historial de recepciones y reversión, con fecha y motivo. Botones siempre accesibles.
- [ ] Probar aviso histórico sin categorías inventadas, anulación, recarga de estado tras recibir/revertir y controles deshabilitados correctamente. Verificar geometría 1280×720, 1440×900 y respaldo en pantalla pequeña.
- [ ] Ejecutar pruebas nuevas y navegación existente, todas PASS; commit.

## Tarea 4: Verificación y entrega

**Files:** actualizar `README.md`, `docs/releases/compras-validacion.md` y captura sintética en `docs/capturas/`.

- [ ] Ejecutar suite completa `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`; corregir regresiones. No usar base personal.
- [ ] Capturar y revisar recepción, pedido recibido con costos pendientes y reversión. Comprobar importes e inversión sin cambios y que la UI no diga stock disponible como si ventas ya lo descontaran.
- [ ] Ejecutar suites disponibles de Debian 13 y Windows/Python bajo Wine con wrappers existentes; documentar cualquier bloqueo. Wine no sustituye Windows 11 real.
- [ ] Revisar diff contra spec, migración y concurrencia, registrar resultados y límites. Mantener paquetes anteriores sin reconstruir y advertir incompatibilidad con nuevo esquema.
- [ ] `git diff --check`, commit final y entregar instrucciones para reiniciar desde el script.
