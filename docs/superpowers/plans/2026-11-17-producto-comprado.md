# Producto comprado: interfaz y desglose

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Implementar en esta rama, según preferencia vigente del usuario.

**Goal:** Aplicar el diseño aportado a Producto comprado conservando cálculo y persistencia.
**Architecture:** Controles específicos de compras reutilizan las interfaces de IVA y moneda existentes. La tarjeta usa la misma conversión y redondeo que PurchaseLineInput.
**Tech Stack:** Python, PySide6, pytest-qt.
**Spec:** docs/superpowers/specs/2026-11-17-iva-total-compras-design.md

## Global Constraints
No modificar ventas ni los datos del usuario. Mantener importes exactos al alternar total/unidad, bloqueo contra doble IVA y fecha de conversión. El IVA totalizado e informe corresponden al siguiente bloque del diseño general.

## Review Focus
- USD con tasa incompleta: no mostrar totales anteriores.
- Tres unidades y centavos indivisibles: conservar total exacto.
- IVA bloqueado por el pedido: no permitir activarlo desde botones nuevos.
- Tarifas personalizadas históricas: conservar al editar.
- Tamaño 1280 × 800: controles y pie accesibles.

### Task 1: Controles y resumen
Files: src/mi_negocio/ui/purchase_line_editor.py; src/mi_negocio/ui/purchase_line_fields.py; tests/test_purchase_line_design.py.
Interfaces: PurchaseLineDialog conserva product, quantity, amount, cost_mode, vat y exchange. El resumen expone base_summary, vat_summary y total_summary.
- [x] Añadir pruebas de 850 USD, tasa 4100, dos unidades y 19 %: base 348500000, IVA 66215000, total 414715000 centavos; tarifa 5 %; incluido; no aplica; bloqueo y reapertura.
- [x] Ejecutar pruebas y observar fallo por controles ausentes.
- [x] Implementar distribución y controles reutilizando values()/set_values() existentes.
- [x] Ejecutar pruebas focalizadas y suite completa; capturar interfaz con datos ficticios en COP/USD y revisar dimensiones.
- [x] Revisar diff y registrar commit del bloque visual.

## Registro
Ejecución directa autorizada por petición de aplicar la referencia; no repetir autorización de cambios reversibles. Este plan divide el cambio visual del cálculo totalizado del pedido para verificar ambos sin mezclar errores.

## Verificación final
Pruebas iniciales fallaron por ausencia de los controles nuevos. Suite completa: 474 pruebas correctas; capturas COP/USD revisadas a 820 × 760. Revisión independiente sin errores bloqueantes; corregida la apariencia habilitada de los botones de cantidad en compras recibidas.
