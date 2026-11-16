# Inventario por modelo y puesta en marcha

Recoge los acuerdos del usuario del 23 de octubre: asistente inicial con dos
opciones, confirmación física recomendada, ventas históricas de prueba excluidas
y ajustes manuales desactivados por defecto. La modalidad compras/importación
queda para el futuro, igual que etiquetas por unidad y valoración contable.

## Enfoque

Se conserva el historial anterior. En vez de reconstruir silenciosamente todas
las ventas o mantener un saldo sin trazabilidad, usar un libro de movimientos por
modelo. El usuario eligió ofrecer ambas formas de inicio: saldo físico confirmado
(recomendado) y compras recibidas revisadas. No se cambian códigos del catálogo.

El asistente se ofrece al abrir el programa si falta configurar, y desde
Inventario. Puede posponerse: se avisa que las ventas no controlan existencias
hasta confirmar. Una vez confirmado no vuelve a inicializarse esa base. Mostrar
cantidades de todos los modelos, incluidos inactivos, y confirmar expresamente
los ceros. Servicios excluidos. Si cambian catálogo o recepciones durante la
revisión, rechazar y pedir actualizar. Las compras ya recibidas se marcan como
incluidas en la apertura para no duplicarlas. Nuevos modelos parten de cero.

## Movimientos y protección

- Recepciones posteriores suman unidades aunque falten costos, como hasta ahora.
- Ventas guardadas después del inicio descuentan unidades, incluso con fecha
  anterior o cobro pendiente. No se descuentan ventas guardadas antes del inicio.
- Se agregan todas las líneas de un mismo modelo al validar el disponible.
- Guardar valida y descuenta en una misma transacción; reintentos no duplican.
- Anular devuelve solo salidas efectivamente registradas, una sola vez.
- Deshacer una recepción nueva resta sus unidades solo si no deja saldo negativo.
- No deshacer recepciones incluidas en la apertura: ya forman parte de un saldo
  confirmado. Corregir existencias mediante ajuste con motivo, conservando historia.
- Ajustes habilitables en Configuración → Inventario, persistidos en la misma base
  (no solo QSettings). Confirmación muestra modelo, saldo anterior, nuevo y diferencia.
  Verificar habilitación y saldo/revisión otra vez al guardar; motivo obligatorio.
- No convertir entre producto y servicio cuando ya existan movimientos de inventario.
- Transacciones BEGIN IMMEDIATE y claves únicas previenen sobreventa concurrente.

## Interfaz

Inventario en el menú lateral; resumen de disponibles y en tránsito, búsqueda,
tabla por código/modelo y cantidades, historial y ajuste del modelo seleccionado.
Cero rojo, una/dos unidades naranja, tres o más verde; siempre incluir números y
texto. Tránsito = pedidos vigentes sin recepción activa; no se confunde con disponible.
Nueva venta muestra disponible y restante por modelo, limita cantidades sumando
líneas repetidas y vuelve a comprobar al guardar. Los servicios no tienen límite.
Antes del inicio se muestra «Inventario sin configurar», nunca stock confirmado.

## Migración y pruebas

Esquema 12 con respaldo previo; sin movimientos automáticos para datos históricos.
Pruebas de apertura única, concurrencia, cambios durante revisión, saldos cero,
ventas repetidas, servicios, anulación y reversión, ajustes protegidos y UI Qt.
Validar geometría y flujo sin afectar la base personal. Esta etapa cambia el código;
los paquetes alfa 0.2 entregados permanecen como referencia de compatibilidad.
