# Ventas Resumen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implementar las dos pestañas de Ventas aprobadas, con datos reales filtrados.
**Architecture:** Cálculos puros en sales_analytics.py; consultas de líneas históricas en SalesRepository; SalesDashboard y gráficos QtPainter separados de SalesPage. Filtros únicos para ambas vistas.
**Tech Stack:** Python, PySide6, SQLite existentes.
**Spec:** docs/superpowers/specs/2026-10-24-ventas-resumen-design.md

## Global Constraints
Sin nuevas dependencias ni migraciones. COP en centavos enteros. Ventas anuladas excluidas de indicadores. No modificar datos reales durante pruebas. Trabajar en rama actual por instrucción del usuario.

## Review Focus
- Mes parcial, febrero y cambio de año: fechas comparadas explícitas y sin incluir días futuros.
- Anuladas, servicios y varios modelos en una venta: no duplicar total ni unidades.
- Comisión real diferente a estimación: usar recibo, sin descuento doble de envío/retención.
- Filtros inválidos o fallo de consulta: limpiar cifras antiguas, mantener error visible.
- Navegación desde Inicio, cambios de pestaña y tamaños pequeños: controles accesibles y filtros conservados.

### Task 1: Cálculos y consulta
Files: src/mi_negocio/sales_analytics.py, src/mi_negocio/sales_repository.py, tests/test_sales_analytics.py.
Interfaces: summarize_sales(rows, lines, previous_rows) -> dict; comparison_dates(start,end,today,monthly) -> tuple|None; sales.list_lines(sale_ids) -> list[dict].
- [x] Pruebas RED: totales exactos, comisión real, anuladas, ranking con líneas repetidas, servicios, comparación y base cero.
- [x] Implementar y ejecutar tests/test_sales_analytics.py hasta GREEN.

### Task 2: Pestañas y gráficos
Files: src/mi_negocio/ui/sales_dashboard.py, src/mi_negocio/ui/sales_charts.py, src/mi_negocio/ui/sales_page.py, tests/test_sales_dashboard.py.
Interfaces: SalesDashboard.update_data(summary, rows, previous, dates); clear_data(); page.tabs; page.dashboard; page.last_three_months().
- [x] Pruebas RED: filtros compartidos, mes predeterminado, atajo trimestre, acciones por fila y limpieza de errores.
- [x] Implementar diseño y gráficos, pruebas GREEN; capturas con base temporal a 1440×900 y 1320×720.
- [x] Regresión completa, pruebas enfocadas en Debian y Wine, revisión independiente y commit.

## Registro
Pre-flight: Task 2 consume el dict de Task 1; nombres y semántica fijados en tests y código, sin cambios a esquema.

Task 1: completado con pruebas RED→GREEN de agregación, fechas, consulta de líneas y comisión real.
Task 2: completado con pruebas RED→GREEN de pestañas, acciones, filtros y errores; capturas a 1440×900 y 1320×720 sin scroll en Resumen.
Revisión independiente: corregida comparación de barras en rangos que cruzan meses; regresión RED→GREEN. Etiquetas semanales identifican ambos meses cuando corresponde.
