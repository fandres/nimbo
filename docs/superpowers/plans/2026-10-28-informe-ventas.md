# Exportación de ventas Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Exportar el listado filtrado de Ventas a PDF con retención informativa.
**Architecture:** Refrescar la vista antes de exportar y usar la misma instantánea de filas y etiquetas de filtros. Reutilizar el escritor PDF Qt atómico de Dinero con título configurable.
**Tech Stack:** Python/PySide6, sin cambios de base ni dependencias nuevas.
**Spec:** Continuación autorizada del informe de ventas con retención; decisiones y criterios abajo.

## Diseño y restricciones
Botón Exportar PDF en Movimientos junto a totales, sin saturar barra de filtros.
Informe A4 horizontal: filtros completos, fecha de generación, total vendido,
recibido bruto, pendiente bruto y retención informativa. Tabla con fecha, cliente,
identificación, factura, forma/cuenta de pago, estado, total y retención.
El importe con retención es el almacenado/calculado por el repositorio (2,5 %
sobre total incluyendo envío cobrado); no se descuenta ni se considera certificado.
Ventas anuladas visibles según filtro y excluidas de todos los totales.
Respetar fechas, estado, cuenta, búsqueda, vigencia, retención y límites de importe.
No exportar filas antiguas cuando el filtro es inválido. Cancelar no escribe y un
fallo no debe destruir un informe previo. Confirmar si al añadir .pdf ya existe.
Qt existente es preferible a otra biblioteca: sin añadir dependencias de empaquetado.

## Review Focus
Filtros inválidos, anuladas con retención, HTML/nombres largos, falta de identificación,
archivos ya existentes y encabezados repetidos en varias páginas.

## Tareas
- [x] Escribir pruebas y observar fallo: totales, retención, escape, filtros activos, cancelación y errores.
- [x] Añadir sales_report.py y título opcional al escritor compartido.
- [x] Integrar botón y exportación en sales_page.py usando refresh_sales.
- [x] Validar suite, PDF multipágina y pruebas específicas en Windows/Debian.
- [x] Revisar, documentar y guardar commit.

## Verificación
363 pruebas locales; 32 de formularios/informes Windows bajo Wine; 12 de informes Debian 13.
PDF sintético multipágina renderizado y revisado (cabecera, continuación, última página).
Revisión independiente sin hallazgos importantes pendientes.
