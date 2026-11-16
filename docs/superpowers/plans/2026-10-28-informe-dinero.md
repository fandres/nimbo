# Informe de movimientos Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Exportar los movimientos filtrados de Dinero a un PDF legible.
**Architecture:** Obtener una instantánea del repositorio, calcular los totales del filtro y renderizar un documento Qt con guardado atómico. Integrar un botón en Movimientos.
**Tech Stack:** Python, PySide6 QtGui/QtCore, SQLite existente.
**Spec:** docs/superpowers/specs/2026-10-28-informe-dinero-design.md

## Global Constraints
COP en centavos enteros; sin migraciones ni dependencias nuevas; conservar la rama actual y datos reales intactos.

## Review Focus
Transferencias y tarjetas no inflan caja; búsqueda y fechas son exactas; texto HTML y nombres largos son seguros; PDF multipágina no recorta; cancelación o error no reemplaza archivos.

### Task 1: Documento e integración
Files: src/mi_negocio/ui/money_report.py, src/mi_negocio/ui/money_page.py, tests/test_money_report.py.
- [x] Probar totales con tarjetas/transferencias/sin cuenta, filtros UI, contenido vacío, escape HTML y escritura PDF.
- [x] Ejecutar pruebas y comprobar el fallo inicial.
- [x] Implementar build_money_report(rows,start,end,account_name,query,account_id) y write_money_pdf(path,html), con validación de fechas y guardado QSaveFile.
- [x] Integrar Exportar PDF, consultando repositorio al pulsar y manejando errores sin dialogar sobre datos personales.
- [x] Ejecutar pruebas locales, renderizar PDF sintético multipágina y revisar páginas.
- [x] Ejecutar suite y pruebas Windows pertinentes; documentar y guardar commit.

## Verificación
357 pruebas completas Linux; 11 pruebas Dinero/exportación Windows bajo Wine y 11 en Debian 13.
PDF sintético de 70 movimientos y 10 páginas revisado en primera y última página, con encabezados repetidos, caracteres acentuados y referencia sin espacios.
Revisión independiente sin hallazgos importantes pendientes. Protección adicional al añadir extensión .pdf y validación de fallo de render conservando el destino previo.
