# Ventas y cobros — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Registrar ventas y sus cobros completos desde Inicio, con comisiones, envío y medios de pago configurables.

**Architecture:** Mantener MainWindow y QStackedWidget. Compartir la conexión SQLite existente entre repositorios de catálogo, configuración y ventas; centralizar migraciones. Separar cálculo monetario de persistencia y widgets.

**Tech Stack:** Python >=3.11, PySide6 >=6.8,<7, sqlite3, Decimal, pytest y pytest-qt; sin dependencias adicionales.

**Spec:** `docs/superpowers/specs/2026-10-18-ventas-cobros-design.md` (aprobado).

## Global Constraints

- Trabajar aquí en la rama actual; conservar catálogo, códigos exactos y datos personales.
- Importes como centavos enteros; Decimal y HALF_UP a dos decimales para comisión; nunca float.
- Comisión sobre total con envío cobrado. Bolt 3,59 % + $900; Addi 7,735 %; tarifas editables.
- Un cobro completo por venta; abonos, pagos mixtos, anulaciones y devoluciones quedan fuera.
- Fecha de venta distinta de fecha de cobro. No confirmar automáticamente por paso del tiempo.
- No mostrar saldo disponible, utilidad ni flujo completo mientras falten los demás movimientos.
- Pruebas y capturas solo con bases temporales; guardar una copia consistente antes de migrar bases existentes.
- Diseño horizontal, botones finales visibles; comprobar 1320 × 720 y 800 × 560.

## Review Focus

- Desbordamiento por cantidades/precios grandes: rechazar antes de escribir SQLite (tarea 1).
- Dos ventanas confirman el mismo cobro: una sola operación persiste (tarea 3).
- Se cambia o desactiva un medio mientras un formulario está abierto: validar al guardar y no sustituir silenciosamente selección/tarifa (tareas 3 y 5).
- Fallo al crear copia de seguridad o durante migración: base original intacta y error recuperable (tarea 2).
- Doble clic en Guardar o fallo de disco: sin ventas incompletas/duplicadas ni pérdida de datos del formulario (tareas 3 y 5).

## Mapa de archivos y contratos

Nuevos módulos:
- `sales.py`: dataclasses, validación y cálculo.
- `database.py`: conexión, copias y migraciones; `storage.py`: excepciones compartidas.
- `settings_repository.py`: cuentas y formas de pago.
- `sales_repository.py`: ventas, cobros, envío y consultas para Inicio.
- `ui/settings_page.py`, `ui/sales_page.py`, `ui/sale_dialog.py`, `ui/sale_detail_dialog.py`: pantallas separadas por responsabilidad.

Rutas relativas a `src/mi_negocio/`; tests correspondientes en `tests/`. Modificar `repository.py` solo para consumir apertura/migraciones comunes; conservar API CatalogRepository(path), close() y exportaciones de excepciones usadas por tests actuales. Modificar MainWindow y HomePage para integrar los módulos.

Contratos compartidos (dataclasses inmutables):
- `SaleLineInput(product_id: int, quantity: int, unit_price_cents: int)`.
- `SaleDraft(sold_on: date, invoice_ref: str, lines: tuple[SaleLineInput, ...], method_id: int, destination_account_id: int, shipping_enabled: bool, shipping_charged_cents: int, shipping_cost_cents: int)`.
- `ReceiptInput(received_on: date, account_id: int, commission_cents: int)`.
- `ShippingPaymentInput(paid_on: date, account_id: int)`; importe tomado del costo de envío de la venta.
- `Totals(subtotal_cents, total_cents, commission_cents, deposit_cents, net_after_shipping_cents)`: cinco int.
- `PaymentMethod(id: int, name: str, provider: str, rate_percent: Decimal, fixed_cents: int, enabled: bool, placement: str, default_received: bool)`; placement `primary`/`additional`.
- `Account(id: int, name: str, enabled: bool)`.
- `SaleSummary(id, sold_on, invoice_ref, total_cents, method_name, account_name, received)`; `SaleDetail(summary, lines, totals, receipt, shipping_payment)` con instantáneas históricas de líneas y comisiones.
- `SalesFilter(start: date | None = None, end: date | None = None, account_id: int | None = None, received: bool | None = None, query: str = '')`.

### Tarea 1: Reglas monetarias

Archivos: crear `sales.py`, `tests/test_sales.py`.

Interfaz: `calculate_totals(lines: tuple[SaleLineInput, ...], shipping_charged_cents: int, shipping_cost_cents: int, rate_percent: Decimal, fixed_cents: int) -> Totals`; `validate_sale(draft: SaleDraft) -> None` lanza ValidationError con campos.

- [x] Escribir tests de Bolt, Addi, envío gratuito, redondeo y límites. Ejemplo determinista:
  `calculate_totals((SaleLineInput(1, 1, 100000000),), 2000000, 2500000, Decimal('3.59'), 90000)` debe devolver total `102000000`, comisión `3751800`, depósito `98248200`, neto `95748200`.
- [x] Ejecutar `.venv/bin/python -m pytest tests/test_sales.py -q`; comprobar fallo por API ausente.
- [x] Implementar dataclasses y reglas. Cantidades enteras positivas, al menos una línea, importes no negativos, porcentaje 0–100; comprobar resultados dentro de entero SQLite de 64 bits. Envío desactivado implica ambos importes cero. Comisión no supera total; neto tras envío puede ser negativo.
- [x] Ejecutar tests; deben pasar, incluidos Addi 7,735 % sobre $1.000.000 = $77.350, redondeo de medio centavo y desbordamiento de suma/producto.
- [x] Commit `feat: add sale calculations and validation`.

### Tarea 2: Migración y configuración persistente

Archivos: crear `database.py`, `storage.py`, `settings_repository.py`, `tests/test_database.py`, `tests/test_settings_repository.py`; modificar `repository.py`.

Interfaces: `open_database(path: Path) -> sqlite3.Connection`; `SettingsRepository(connection)` con `list_methods(include_disabled=False) -> list[PaymentMethod]`, `save_method(method: PaymentMethod) -> PaymentMethod`, `list_accounts(include_disabled=False) -> list[Account]`, `save_account(account: Account) -> Account`. id=0 significa crear; otras IDs deben existir.

- [x] Tests: migrar catálogo v2 conservando datos/listas/códigos; backup reabrible; versiones futuras rechazadas; fallo de backup/migración deja v2 intacto. Métodos iniciales exactos y cambios conservados al reabrir.
- [x] Ejecutar `.venv/bin/python -m pytest tests/test_database.py tests/test_settings_repository.py -q`; verificar fallo esperado.
- [x] Centralizar migraciones v1/v2 existentes y añadir v3 transaccional con cuentas, formas, ventas, líneas, cobros y pagos de envío. Antes de migrar archivo existente no vacío, usar SQLite backup a archivo hermano único; abortar si falla. Configurar claves foráneas y Row; conservar casefold para catálogo.
- [x] Crear restricciones de tipos, valores y relaciones. UNIQUE(sale_id) para cobros y pagos de envío. Ventas incluye clave de solicitud única y copias de nombre/tarifas de método. Líneas conserva código/nombre/precio. Mantener estimación separada de comisión real. Guardar fechas ISO. Nombres no vacíos y únicos sin distinguir mayúsculas; no borrar registros. Sembrar Efectivo y Cuenta principal, cuatro formas y valores aprobados solo una vez.
- [x] Ejecutar tests nuevos y `tests/test_repository.py tests/test_app.py`; todo debe pasar.
- [x] Commit `feat: migrate storage for sales and payment settings`.

### Tarea 3: Ventas y cobros atómicos

Archivos: crear `sales_repository.py`, `tests/test_sales_repository.py`.

Interfaces `SalesRepository(connection)`:
- `create(draft: SaleDraft, *, request_id: str, expected_method: PaymentMethod, receipt: ReceiptInput | None = None, shipping_payment: ShippingPaymentInput | None = None) -> SaleDetail`.
- `get(sale_id: int) -> SaleDetail`, `list_sales(filters: SalesFilter) -> list[SaleSummary]`.
- `confirm_receipt(sale_id: int, receipt: ReceiptInput) -> SaleDetail`.
- `pay_shipping(sale_id: int, payment: ShippingPaymentInput) -> SaleDetail`.
- `update_invoice(sale_id: int, reference: str) -> None`.
- `home_summary(today: date) -> dict`: claves `month_subtotal_cents`, `month_shipping_cents`, `pending_total_cents`, `pending_count`, `recent_sales`.

- [x] Tests de venta pendiente/recibida, fechas diferentes, comisión corregida, pago de envío independiente, instantáneas tras cambios y filtros inclusivos. Confirmar envío pagado no modifica neto depositado.
- [x] Ejecutar `.venv/bin/python -m pytest tests/test_sales_repository.py -q`; verificar fallos esperados.
- [x] Implementar transacciones explícitas: validar productos activos, cuentas y medio; comparar expected_method con la configuración vigente para pedir revisión si cambió. Comprobar fechas válidas, no futuras para movimientos ya realizados y cobro no anterior a venta. Guardar histórico y operaciones como unidad.
- [x] Añadir tests y control de concurrencia con dos conexiones; unicidad de cobros/envío y request_id. Repetir solicitud idéntica devuelve venta existente; misma clave con contenido diferente rechaza. Una excepción entre líneas revierte todo. Un medio histórico desactivado no impide cobrar pendientes; cuenta destino nueva debe estar activa.
- [x] Ejecutar pruebas nuevas más tareas 1–2; todo debe pasar.
- [x] Commit `feat: persist sales receipts and shipping payments`.

### Tarea 4: Configuración editable

Archivos: crear `ui/settings_page.py`, `tests/test_settings_ui.py`; modificar `ui/main_window.py`.

Interfaz: `SettingsPage(repository: SettingsRepository, parent=None)`, señal `settings_changed()`.

- [x] Tests de crear/editar/desactivar método y cuenta; cambiar porcentaje a tres decimales y principal/adicional; preservar selección tras error.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_settings_ui.py -q`; verificar fallo.
- [x] Implementar dos secciones Formas de pago y Cuentas, editores compactos y validación junto al campo. Mostrar nombre comercial y proveedor por separado. Añadir selección de estado inicial propuesto recibido/pendiente por método; valores iniciales de la especificación. Habilitar Configuración en menú.
- [x] Ejecutar tests de configuración y navegación. No introducir controles de abonos que todavía no funcionan.
- [x] Commit `feat: configure payment methods and accounts`.

### Tarea 5: Venta rápida y detalle de cobro

Archivos: crear `ui/sale_dialog.py`, `ui/sale_detail_dialog.py`, `tests/test_sales_ui.py`.

Interfaces: `SaleDialog(catalog: CatalogRepository, settings: SettingsRepository, sales: SalesRepository, parent=None)`; `SaleDetailDialog(sale_id: int, settings: SettingsRepository, sales: SalesRepository, parent=None)`; ambos emiten `saved(sale_id: int)` tras persistir.

- [x] Tests: elegir producto, modificar cantidad/precio, añadir servicio; total y comisión con envío; adicionales apagadas/encendidas y limpieza de Addi al ocultar. Guardar sin método debe señalar error.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_sales_ui.py -q`; verificar fallo.
- [x] Implementar diálogo en dos columnas, pie fijo y respaldo desplazable. Sin medio preseleccionado; al elegir medio proponer estado recibido/pendiente visible, sin sobrescribir un estado ya elegido manualmente. Mostrar estimación y permitir comisión real para recibido. Envío tiene costo, cobro al cliente y pago realizado opcional con fecha/cuenta.
- [x] Implementar detalle con revisión de importes, referencia editable, confirmar cobro y registrar pago de envío; sin edición monetaria destructiva. Antes de guardar señalar que importes no podrán editarse en esta versión. Fechas por defecto hoy, editables.
- [x] Tests de configuración cambiada con diálogo abierto, doble clic, guardado fallido preservando campos, cierre sin guardar y navegación por teclado. Un UUID por intento lógico de venta; Guardar deshabilitado durante persistencia y cerrar después de éxito.
- [x] Ejecutar tests y capturar diálogos con datos temporales a tamaños normal y mínimo; pie accesible y texto sin cortes.
- [x] Commit `feat: add quick sale and receipt dialogs`.

### Tarea 6: Lista de ventas e integración con Inicio

Archivos: crear `ui/sales_page.py`, `tests/test_sales_navigation.py`; modificar `ui/main_window.py`, `ui/home_page.py`, `tests/test_navigation.py`, `README.md`; crear `docs/verificacion-ventas.md` y capturas de ventas.

Interfaces: `SalesPage(catalog, settings, sales, parent=None)` con `open_new_sale()`, `refresh_sales()`, `show_pending()` y señal `sales_changed()`; HomePage recibe SalesRepository opcional y expone señales `new_sale_requested()` y `pending_requested()`.

- [x] Tests: nueva venta desde Inicio y Ventas usa mismo flujo; Cobrar muestra pendientes; filtro fechas/cuenta/estado/texto; volver conserva filtros; Inicio refleja venta y cobro sin saldo inventado.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_sales_navigation.py -q`; comprobar fallos esperados.
- [x] Implementar lista/detalle y conectar señales. Refrescar catálogo antes de elegir productos. En Inicio mostrar subtotal comercial mensual y envío cobrado separado, pendientes por total comercial y últimas ventas. Etiquetar importes correctamente. Actualizar tests que esperaban Ventas/Configuración deshabilitados; conservar inaccesibles Compras/Dinero/Informes.
- [x] Mantener Ctrl+N de catálogo aislado y añadirlo a ventas solo cuando esa página esté activa. Cambiar página no cierra silenciosamente una venta sin guardar. Actualizar README con funciones y limitaciones reales.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` y `git diff --check`; todos pasan. Revisar capturas a 1320 × 720 y 800 × 560, incluidos cero ventas, venta pendiente y error de acceso. Documentar resultados exactos y límites de verificación offscreen.
- [x] Revisión final de cálculo, atomicidad, migración, permisos y preservación del catálogo; resolver hallazgos y repetir solo comprobaciones afectadas.
- [x] Commit `feat: connect sales and receipts to the home dashboard`.

## Revisión del plan

Cobertura: configuración y persistencia (2,4), venta rápida (1,3,5), envío/comisiones (1,3,5), cobro e historial (3,5), lista/Inicio (6), conservación de datos (2,3), accesibilidad y pruebas visuales (4–6). Riesgos de Review Focus cubiertos en las tareas indicadas. No se añaden librerías ni subsistemas financieros completos.

## Ejecución propuesta

Implementación secuencial en esta conversación, conservando la carpeta y rama actuales. Cada tarea termina con pruebas y un commit; revisión final del conjunto. Alternativa: implementación y revisión por subagentes por tarea. Plan aprobado; ejecución secuencial elegida e implementada. Evidencia y ajustes en docs/verificacion-ventas.md.
