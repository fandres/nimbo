# Nimbo · Compras, primera entrega

## Objetivo y alcance

Registrar qué mercancía se compró, a quién, cuándo y cuánto ha costado hasta el
momento, conservando por separado los componentes de una importación. Esta entrega
incorpora Compras al menú lateral, un listado filtrable y un formulario para crear,
consultar y corregir compras. Trabaja con la SQLite local existente.

La recepción física, existencias por unidad, asignación de costos a unidades,
etiquetas y descuento de inventario al vender corresponden a las dos entregas
siguientes acordadas. Guardar una compra no habilita existencias ni modifica ventas.

## Decisiones propuestas

Se recomienda una compra con varios productos y una lista de costos adicionales.
Una compra de una sola máquina sería más simple, pero obligaría a repetir proveedor,
referencia y flete cuando un pedido incluya varios modelos. Un sistema completo de
órdenes, embarques y pagos sería más amplio de lo necesario para esta primera entrega.

Supuestos explícitos: un pedido puede contener varios modelos; cada producto tiene
cantidad entera y precio unitario de compra; los gastos adicionales pertenecen al
pedido. El proveedor de la compra es independiente de la marca del catálogo.
Se permite registrar compras nacionales en COP además de compras en USD.

## Formulario

Ventana amplia, coherente con Nueva venta, con encabezados numerados y fondo de
paneles diferenciado. Un único botón azul «Guardar compra» y Cancelar al pie.
Fecha y proveedor aparecen al principio; no quedan escondidos junto al título.

1. **Proveedor y fecha.** Fecha de compra (hoy como valor inicial, calendario al
   hacer clic), proveedor obligatorio y referencia de factura/pedido opcional.
   Proveedores anteriores sugeridos al escribir, conservando el texto histórico.
2. **Qué compramos.** Buscador por código o nombre del catálogo, cantidad, moneda
   COP/USD y costo unitario de compra. Se agregan líneas a una tabla con subtotal.
   El costo comienza vacío: el precio recomendado de venta no es costo de compra.
   Solo productos físicos activos en nuevas líneas; servicios no entran aquí.
   Los códigos existentes y sus ceros iniciales se conservan.
3. **Costos de la compra.** Mercancía calculada a partir de las líneas y filas
   adicionales para envío internacional, importación/gestión, impuestos y otros
   costos. Cada fila registra concepto, importe y moneda; puede incluir una nota.
   Agregar conceptos permite varios cargos de una misma categoría sin sumarlos a mano.

Un selector «Costos por completar / Costos completos» distingue un pedido cuyo
costo final todavía no se conoce. Valor inicial: por completar. La ayuda aclara
que cero significa que no hubo costo en esa fila, no que falta información.
No se considera automáticamente completo porque todas las casillas tengan números.

Los importes se seleccionan al primer clic, igual que en Ventas. Los campos USD
se muestran solo cuando corresponda. El área inferior permanece visible; se adapta
la distribución al espacio y se reserva desplazamiento para pantallas pequeñas,
no como solución predeterminada en una pantalla amplia. Se comprueba también el caso
con todos los campos opcionales visibles. Ningún dato se recorta para ocultar barras.

## Moneda, fechas y totales

La moneda de los informes y totales es COP. Se guardan los importes originales,
la tasa utilizada y el equivalente COP; no se consulta ni inventa una TRM.

- Mercancía en USD: tasa COP por USD y fecha de conversión obligatorias.
- Cada costo adicional en USD conserva su propia tasa y fecha de conversión.
- Un impuesto pagado en COP conserva su importe real en COP. Puede registrar
  opcionalmente la tasa del dólar y su fecha como referencia, sin reconvertir el
  importe COP ni sustituirlo por un cálculo.
- La fecha de conversión no confirma un pago. Esta entrega no registra movimientos
  de cuentas ni salidas de caja; esas operaciones se integrarán con el módulo financiero.
- Importes no negativos y cantidades enteras positivas. Tasas positivas con hasta
  seis decimales; dinero con dos decimales, Decimal y redondeo HALF_UP a centavos.
- Para mercancía: subtotal original = cantidad × costo unitario. Convertir y
  redondear cada subtotal de línea una sola vez. Para cargos: convertir cada fila
  una sola vez. Total COP = suma de líneas y cargos COP ya redondeados.
- Validar límites monetarios antes de persistir, sin utilizar float para dinero.

Resumen en tarjetas: **Mercancía**, **Envío e importación**, **Impuestos y otros**
y **Total registrado · COP**. Mostrar «Costo provisional» si quedan costos por
completar. No presentar costo unitario final ni utilidad hasta implementar la
asignación de gastos a unidades de inventario.

Ejemplo: dos máquinas a USD 300 cada una, tasa 4.200, equivalen a $2.520.000 COP.
Un envío de USD 50 a tasa 4.250 agrega $212.500. Impuestos de $400.000 COP producen
un total registrado de $3.132.500 COP. Cambiar una tasa no cambia las otras.

## Listado, correcciones y conservación

Columnas: fecha, proveedor, referencia, unidades compradas, total registrado COP y
estado de costos. Buscar por proveedor, referencia y código/nombre de productos;
filtrar por fechas, costos completos/por completar y vigentes/anuladas/todas.
No llamar «disponibles» a las unidades de este listado.

Doble clic o «Ver / editar compra» abre los datos. Se pueden completar cargos y
corregir líneas mientras la compra no esté anulada. Para esta fase aún no hay
recepciones ni movimientos de inventario que invalidar. Guardar correcciones
conserva una revisión anterior completa, fecha de modificación y número de revisión.
Rechazar un guardado si el registro cambió desde que se abrió; permitir recargar.

«Anular compra» solicita confirmación y motivo; conserva historial y excluye el
pedido de los totales vigentes. Una compra anulada solo se consulta. No se borra
físicamente ni se ejecutan reembolsos. Cancelar el diálogo no escribe nada.

## Integración técnica

- `purchases.py`: entradas y validación, moneda y cálculos independientes de Qt.
- `purchases_repository.py`: creación, consulta, filtros, correcciones y anulación.
- `ui/purchases_page.py` y `ui/purchase_dialog.py`: listado y formulario.
- Reutilizar los campos monetarios, calendario y estilos existentes; no añadir
  dependencias nuevas para esta entrega.
- Habilitar Compras en MainWindow y el acceso «Comprar o importar» de Inicio.
  Ctrl+N crea una compra únicamente cuando está activa esa sección.
- Compartir conexión y manejo de errores existentes. Migración transaccional de
  esquema 8 a 9, con respaldo SQLite previo, preservando catálogo, ventas y ajustes.
  Condicionar también la migración de anulación de ventas a version < 8 para evitar
  repetir ALTER TABLE al abrir una base que ya está en esquema 8.
- Tablas nuevas: purchases (cabecera, estado, revisión e identificador único de
  solicitud), purchase_lines (producto referenciado y copia de código/nombre/costo),
  purchase_costs (conceptos, monedas, tasas y fechas) y purchase_revisions (instantánea
  anterior y fecha). Proveedores sugeridos desde compras existentes, sin tabla de
  configuración adicional por ahora.
- Claves foráneas, comprobación de importes/cantidades y restricciones en SQLite.
  Crear o actualizar cabecera, líneas, costos y revisión en una sola transacción.
- Solicitudes repetidas no duplican compras. Errores de validación o almacenamiento
  conservan el formulario y sus datos; Guardar se deshabilita durante la operación.
- Los cambios posteriores del catálogo no reescriben compras históricas. Se admite
  conservar una línea existente cuyo producto fue desactivado, pero no agregar una
  línea nueva con un producto desactivado.

## Verificación antes de entrega

- Fórmulas con COP y USD, tasas distintas por cargo, redondeos, límites, ceros y
  valores incompletos; el ejemplo monetario anterior debe coincidir exactamente.
- Creación con varias líneas, consultas, filtros, correcciones con revisión,
  anulación, idempotencia, conflictos y rollback ante errores.
- Migración desde esquema 8 con datos existentes, respaldo, reapertura y rechazo
  de esquemas futuros. Pruebas anteriores de catálogo y ventas siguen pasando.
- UI: búsqueda, alta/corrección, campos USD condicionales, primer clic en dinero,
  cálculo de tarjetas, un único guardado y acceso desde menú/Inicio.
- Revisar con datos temporales a 1440×900 y 1280×720, además de accesibilidad a
  800×560 y escala 150 %. Nunca usar la base personal en pruebas.

## Entrega y siguientes fases

Primero se implementa y revisa esta función en el código de desarrollo; los paquetes
alpha.1 compartidos permanecen identificables. Al aprobar la función se prepara una
nueva versión de paquetes, sin sobrescribir los archivos entregados anteriormente.

La siguiente fase incorporará recepción, tránsito y existencias; deberá definir
recepciones parciales y reparto de costos antes de anunciar costos por unidad.
Después se enlazarán unidades y ventas, con etiquetas de código de barras. Ninguna
venta histórica descontará inventario automáticamente durante esta primera entrega.
