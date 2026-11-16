# Próxima etapa: recepción, inventario y disponibilidad al vender

Requisitos recopilados del usuario, 21 de octubre de 2026. Diseño e implementación por modelo desarrollados el 23 de octubre; ver
[el diseño acordado](2026-10-23-inventario-design.md). Las etiquetas individuales
siguen pendientes; no se incluyen en los binarios alfa 0.2 ya entregados.

- Distinguir cantidades compradas, en tránsito y recibidas disponibles. Registrar
  únicamente recepción completa por pedido (confirmado por el usuario); una compra no equivale a stock disponible.
- Mostrar disponible / cantidad a vender / restante junto al producto de la venta.
- Si hay tres máquinas disponibles, permitir como máximo tres. Cero disponibles
  impide añadir el producto; los servicios no se limitan por existencias.
- Acumular todas las líneas del mismo producto en la venta: no eludir el límite
  agregando dos líneas de dos unidades cuando solo quedan tres.
- Ajustar el máximo al modificar cantidades o quitar líneas, sin descartar
  silenciosamente datos ya ingresados. Mostrar el motivo de un rechazo.
- Revalidar existencias y descontarlas en una misma transacción al guardar;
  una validación visual sola no protege frente a cambios concurrentes.
- Definir el ajuste de existencias al editar/anular ventas, evitando descontar
  dos veces al reintentar un guardado y conservando trazabilidad.
- No descontar ventas históricas automáticamente al activar esta etapa; diseñar
  cómo establecer el inventario inicial y vincular recepciones anteriores.
- Mantener el código de producto del catálogo/facturación; separar las unidades
  individuales para las futuras etiquetas y códigos de barras.

Orden propuesto: recepción y existencias iniciales, vista de inventario, conexión
con venta rápida y validación transaccional. El diseño debe resolver el cierre de
costos para disponibilidad y las correcciones posteriores de compras recibidas.

Confirmación: recibir no exige costos completos ni reparto terminado. Una alerta
recordará los valores pendientes de anotar, sin impedir la recepción. No confirmar
pagos automáticamente: recibir y registrar pagos son operaciones distintas.
