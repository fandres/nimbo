# Costos por subtipo Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Configurar costos por subtipo con selección propia por producto y aplicarlos sin pérdida de datos.
**Architecture:** Migración 25, reglas por identificadores estables; repositorio resuelve herencia/unión; editor de reglas separado dentro de Configuración; compras nuevas sincronizan conceptos y las guardadas solo bajo actualización explícita.
**Tech Stack:** Python, SQLite, PySide6.
**Spec:** docs/superpowers/specs/2026-11-05-costos-por-subtipo-design.md

## Restricciones
Conservar importes e historial. Selección vacía distinta de herencia. Mantener exclusión de IVA. No repartir cargos automáticamente.

## Tareas
- [x] Pruebas de repositorio: herencia, excepciones, selección vacía, unión, renombrado. Migración aditiva y resolución en purchase_cost_rules.py.
- [x] Editor con selector subtipo/producto, búsqueda, casilla heredar y lista de costos; integrar en purchase_concepts_editor.py. Probar guardar/restaurar herencia.
- [x] Sincronizar conceptos en PurchaseDialog para compras nuevas; conservar cargos/asignaciones y avisar. Actualización explícita para compras históricas. Probar pedidos mixtos, vacíos, preservación e IVA.
- [x] Ejecutar suite completa, revisar diff y documentar prueba manual. Guardar en Git.

## Revisión
Considerar conceptos desactivados, productos sin subtipo, cambios de subtipo, cargos sin productos y asignaciones cuyo concepto dejó de aplicar. Cambios de configuración no deben cambiar el historial al abrir compras.

## Validación realizada
- Suite completa: 410 pruebas aprobadas (Qt offscreen, Linux).
- Revisión independiente: corregida la selección textual de otro producto sin confirmar, con prueba de regresión.
- Inspección visual de Configuración a 1050 × 650.
- Migración 24 → 25 probada con compras existentes; compras sin costos, snapshots históricos, herencia, excepciones y preservación de cargos/asignaciones cubiertos.
- No se recompilaron AppImage ni Windows en esta tarea.

## Prueba manual sugerida
1. En Configuración → Costos de compras → Aplicación por producto, elegir Subtipos y Resinas (o un subtipo existente).
2. Desmarcar «Usar todos los conceptos activos»; dejar solo Impuestos y guardar.
3. En Excepciones por producto, elegir una resina, desmarcar «Heredar del subtipo», marcar un costo adicional y guardar.
4. Crear una compra con ambos productos: comprobar la unión de conceptos, sin duplicados.
5. Registrar un cargo, quitar el producto que lo hacía aplicable y comprobar que el importe se conserva con aviso.
6. Abrir una compra anterior: comprobar que solo cambia su lista al pulsar Actualizar conceptos y que los importes se conservan.

Ruling: Sin productos, los controles de costos quedan ocultos/inactivos con indicación de agregarlos primero; las pruebas de interacción anteriores se adaptaron para incluir mercancía.
