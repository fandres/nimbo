# Inventario Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** confirmar existencias y controlar entradas/salidas sin alterar históricos.
**Architecture:** SQLite ledger, apertura explícita por base, operaciones atómicas,
UI PySide6 con repositorio compartido. Sin nuevas dependencias.
**Spec:** ../specs/2026-10-23-inventario-design.md

## Global constraints
Códigos actuales intactos; servicios libres; apertura una vez; ajustes deshabilitados.
No tocar bases personales ni reconstruir binarios en este cambio.

## Review focus
Concurrencia entre apertura/recepción/venta; líneas duplicadas; reversión de compras
previas al inicio; cambio de tipo del catálogo; formularios abiertos con saldo obsoleto.

## Tasks
- [x] Escribir pruebas de repositorio que fallen: apertura manual/recepciones,
  exclusión histórica, ventas limitadas, cancelación, reversión, ajustes y concurrencia.
- [x] Crear inventory_repository.py (preview, initialize, rows, history, adjust,
  settings; helpers internos para hooks transaccionales), migración 12 e integrar
  sales_repository.py, purchase_receipts_repository.py y protección catalog.update.
- [x] Ejecutar pruebas focalizadas y de migraciones; corregir fallos.
- [x] Escribir pruebas Qt de asistente, configuración, navegación, límites de venta.
- [x] Crear ui/inventory_page.py con asistente y ajustes; integrar SettingsPage,
  MainWindow, inicio de app y SaleDialog, con avisos antes de configurar.
- [x] Ejecutar suite completa, inspeccionar captura sintética, revisar cambios,
  documentar comportamiento y guardar en Git.

## Resultado

220 pruebas correctas en entorno local, Debian 13 y Python Windows bajo Wine.
Revisión independiente completada sin hallazgos importantes; comprobó migración,
transacciones y exclusión histórica. Capturas sintéticas inspeccionadas a 1440×900
y 980×660 en docs/capturas/inventario-modelos.png y asistente-inventario.png.
No se accedió a la base personal ni se reconstruyeron los paquetes alfa 0.2.
