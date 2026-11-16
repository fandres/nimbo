# Retenciones descontadas del depósito
Autorizado por el usuario: solo nuevas ventas. Mantener 2,5 % y base actual (total). No alterar ventas anteriores.
Nueva política por venta persistida, con migración que conserva política informativa antigua. Retención al cobrar reduce depósito y genera movimiento derivado en cuenta auxiliar «Retenciones de renta», excluida de disponible/flujo de caja. No es gasto. Anular elimina ambos movimientos efectivos. Editar la marca actualiza ambos atómicamente y valida comisión + retención <= total.
Cuenta auxiliar de consulta, no destino de pagos ni transferencias; saldo automático, sin saldo inicial manual.
Actualizar formulario, detalle e informes distinguiendo histórico informativo. Pruebas de cobro, cancelación, histórico, edición y totales.
Beta 2: revisar colores de botones.

Completado: migración 22, política histórica, descuento, cuenta auxiliar automática, UI y reportes. Revisión independiente: detectó exposición de cuenta auxiliar en selectores y saldo inicial; corregido, prueba dedicada aprobada. Suite final 382 aprobadas; Debian 13: 33 pruebas de retenciones/dinero/ventas aprobadas. Mantener rama actual y commit local conforme a autorización previa.
